import zipfile
from pathlib import Path
from uuid import uuid4
from openheart.database import File
import pyxnat
from datetime import datetime
import os
import ismrmrd
from openheart.utils import utils
from zipfile import ZipFile, is_zipfile
from flask import current_app
from flask_login import current_user

from itertools import chain


def get_xnat_connection() -> pyxnat.Interface:
    '''
    Establish a connetion to the XNAT server at current_app.config['XNAT_SERVER'] using the
    username current_app.config['XNAT_ADMIN_USER'] and the password current_app.config['XNAT_ADMIN_PW']

    To verify the connection was successful, check that
        input: None
        output: pyxnat.Interface object
    '''
    # Get connection to xnat server
    xnat_server = pyxnat.Interface(server=current_app.config['XNAT_SERVER'], user=current_app.config['XNAT_ADMIN_USER'], password=current_app.config['XNAT_ADMIN_PW'])

    # Get all projects available on xnat server
    projects = xnat_server.select.projects().get()
    if len(projects) == 0:
        raise ConnectionError('No projects on xnat server found. Is server running?')
    return xnat_server


def get_xnat_project(xnat_server: pyxnat.Interface, name_project: str):
    '''
    Auxiliary function accessing a project on an XNAT server
        input:
            xnat_server: a pyxnat.Interface object
            name_project: a key to the current_app.config dictionary where the name of the project is stored
        output:
            xnat_project: pyxnat project with name app.config['name_project']
    '''
    xnat_project = xnat_server.select.project(current_app.config[name_project])

    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {current_app.config[name_project]} not available on server.')
    else:
        current_app.logger.info(f'Project {name_project} found on xnat server.')

    return xnat_project


def get_xnat_vault_project(xnat_server):
    return get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_VAULT')


def get_xnat_open_project(xnat_server):
    return get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_OPEN')


def upload_raw_mr_to_vault(list_files:list):
    return upload_raw_mr(list_files, 'XNAT_PROJECT_ID_VAULT')


def set_xnat_ids_in_files(list_files: list) -> list:
    '''
    Preparing the database. File objects by setting appropriate experiment_id and scan_id
    input:
        list of database.File objects
    output:
        list of database.File objects
    '''
    digits_experiment_id = 8
    for idx, f in enumerate(list_files):
        experiment_id = utils.create_md5_from_string(f.subject_unique)
        experiment_id = f"Exp-{experiment_id[:digits_experiment_id]}"
        scan_id = f'Scan_{uuid4()}'

        f.xnat_subject_id = f.subject_unique
        f.xnat_experiment_id = experiment_id
        f.xnat_scan_id = scan_id

        current_app.logger.info(f'Xnat parameters for {f.name}:')
        current_app.logger.info(f'   subject_id: {f.xnat_subject_id}')
        current_app.logger.info(f'   experiment_id: {f.xnat_experiment_id}')
        current_app.logger.info(f'   scan_id: {f.xnat_scan_id}')

    return list_files


def upload_raw_mr(list_files: list, project_name: str):
    '''
    Function to upload mr rawdata files to the XNAT server and add them to project project_name
    input:
        list_files: list filenames for ismrmrd.h5 to be uploaded
        project_name: key to the app.config dict containing the project ID
    output:
        Boolean if upload was successful
    '''
    experiment_date = datetime.utcnow().strftime('%Y-%m-%d')
    xnat_server = get_xnat_connection()
    xnat_project = get_xnat_project(xnat_server, project_name)

    list_files = set_xnat_ids_in_files(list_files)
    list_xnat_dicts = get_xnat_dicts_from_file_list(list_files)

    for xnat_dict, f in zip(list_xnat_dicts, list_files):

        xnat_dict["experiment_date"] = experiment_date
        xnat_hdr = get_xnat_hdr_from_h5_file(f.name_unique)
        create_xnat_scan(xnat_project, xnat_hdr, xnat_dict)
        upload_rawdata_file_to_scan(xnat_project, xnat_dict, [f.name_unique])
        f.transmitted =  True

    current_app.logger.info('Finished uploading of of data to xnat. Disconnecting xnat server.')
    xnat_server.disconnect()

    return True


def get_xnat_hdr_from_h5_file(filename_with_ext: str):
    '''
    Auxiliary function to fill XNAT file header from an ISMRMRD rawdata file
        input: full filename of ISMRMRD rawdata
        output: dict containing keys describing a xnat:mrScanData file
    '''
    dset = ismrmrd.Dataset(filename_with_ext, 'dataset', create_if_needed=False)
    header = ismrmrd.xsd.CreateFromDocument(dset.read_xml_header())
    xnat_hdr = utils.ismrmrd_2_xnat(header)
    dset.close()
    current_app.logger.info(f'Xnat file header extracted from {filename_with_ext}.')

    return xnat_hdr


def create_xnat_scan(xnat_project, scan_hdr, xnat_file_dict):

    subject_id, experiment_id, scan_id = get_ids_from_dict(xnat_file_dict)
    experiment_date = xnat_file_dict.get("experiment_date", "1900.01.01")
    xnat_subject = xnat_project.subject(subject_id)

    if xnat_subject.exists():
        current_app.logger.info(f'Subject {subject_id} already exists.')

    experiment = xnat_subject.experiment(experiment_id)

    if experiment.exists():
        current_app.logger.info(f'Experiment {experiment_id} already exists.')
    else:
        experiment.create(**{'experiments': 'xnat:mrSessionData', 'xnat:mrSessionData/date': experiment_date})
        current_app.logger.info(f'Experiment {experiment_id} created in {subject_id}.')

    scan = experiment.scan(scan_id)

    if scan.exists():
        raise NameError(f'The scan {scan_id} already exists for subject {subject_id} and experiment {experiment_id}.')
    else:
        scan.create(**scan_hdr)
        current_app.logger.info(f'Scan {scan_id} created in {subject_id} | {experiment_id}')

    return True


def get_ids_from_dict(xnat_file_dict: dict):
    '''
    Auxiliary function to extract XNAT file IDs from a dictionary

        input: dictionary containing keys for xnat subject_id, experiment_id and scan_id
        output: tuple with the values to the above-mentioned keys the dictionary 
    '''
    subject_id = xnat_file_dict["subject_id"]
    experiment_id = xnat_file_dict["experiment_id"]
    scan_id = xnat_file_dict["scan_id"]
    current_app.logger.info(f'Extracted: {subject_id} | {experiment_id} | {scan_id}')

    return subject_id, experiment_id, scan_id


def upload_rawdata_file_to_scan(xnat_project, xnat_file_dict, list_filenames_rawdata):

    subject_id, experiment_id, scan_id = get_ids_from_dict(xnat_file_dict)

    scan = get_scan_from_project(xnat_project, subject_id, experiment_id, scan_id)
    scan_resource = scan.resource('MR_RAW')
    current_app.logger.info(f'Started upload of {list_filenames_rawdata} to {subject_id} | {experiment_id} | {scan_id}.')
    scan_resource.put(list_filenames_rawdata, format='HDF5', label='MR_RAW', content='RAW', **{'xsi:type': 'xnat:mrScanData'})
    current_app.logger.info(f'Upload of {list_filenames_rawdata} finished.')

    return True, scan


def download_dcm_from_scan(xnat_project, xnat_file_dict, fpath_output):
    '''
    If dicom images have been reconstructed, they are downloaded as a zip file and
    extracted.
    To enable viewing of the dicom images on the xnat server with the ohif viewer, the
    dicom uid is added as a xnat scan parameter.
    '''
    fpath_output = Path(fpath_output)
    scan = get_scan_from_project(xnat_project, *get_ids_from_dict(xnat_file_dict))

    if check_if_scan_was_reconstructed(scan):

        # Download dicom
        try:
            current_app.logger.info(f'Trying to download dicom files for {scan}.')
            fname_dcm_zip = Path(scan.resource('DICOM').get(str(fpath_output)))

            # Extract zip file
            with ZipFile(fname_dcm_zip, 'r') as zip:
                zip.extractall(str(fpath_output))

                # Update scan uid with (0020,000E) 	Series Instance UID
                dcm_header = utils.get_dicom_header(fpath_output)
                scan.attrs.set('xnat:mrScanData/UID', str(dcm_header[0][0x0020, 0x000e].value))
                current_app.logger.info(f'Dicom UID updated to {str(dcm_header[0][0x0020, 0x000e].value)}.')

            delete_files_from_path(fpath_output, {".zip"})
            current_app.logger.info(f'Dicom files successfully downloaded.')
            return True

        except Exception as e:
            current_app.logger.info(f'Downloading reconstructed dicom images failed: {e}.')
            return False
    else:
        return False


def create_gif_from_downloaded_recon(fpath_dicoms:Path, filename_output_with_ext:Path):

    # Create gif
    utils.create_qc_gif(fpath_dicoms, filename_output_with_ext)
    current_app.logger.info(f'Quality control image {filename_output_with_ext} created.')
    delete_files_from_path(Path(fpath_dicoms), {".dcm"})

    return True


def delete_files_from_path(fpath, list_extensions):

    files_to_remove = list(chain.from_iterable([sorted(fpath.glob(f"*{ext}")) for ext in list_extensions]))
    for f in files_to_remove:
        os.remove(str(f))


def share_list_of_scans(xnat_server, list_xnat_dicts):

    name_xnat_dst_project = current_app.config['XNAT_PROJECT_ID_OPEN']
    xnat_vault = get_xnat_vault_project(xnat_server)
    xnat_open = get_xnat_open_project(xnat_server)

    # Get subjects and corresponding experiments to be shared
    lookup_subject_experiments = create_subject_experiment_lookup(xnat_vault, list_xnat_dicts)

    for subj in lookup_subject_experiments:
        share_subjects_and_experiments(xnat_vault, xnat_open, name_xnat_dst_project, subj,
                                       lookup_subject_experiments[subj])
        current_app.logger.info(f'Subject {subj} shared with open xnat project.')

    return True


def create_subject_experiment_lookup(project, list_xnat_dicts):
    '''
    Function to create a dictionary to relate XNAT subject-ids to multiple experiment-ids
    input:
        project: xnat-project
        list_xnat_dicts: list of dictionaries containing subject_id, experiment_id and scan_id as keys
    output:
        dictionary that holds all different experiment id-s for one subject_id in the list_xnat_dicts
    '''
    list_subjects = []

    for xd in list_xnat_dicts:
        sid = xd["subject_id"]
        list_subjects.append(sid)
        get_scan_from_project(project, sid, xd["experiment_id"], xd["scan_id"])

    list_subjects = set(list_subjects)

    lookup_subject_experiments = {}

    for subj in list_subjects:
        lookup_subject_experiments[subj] = []

    for xd in list_xnat_dicts:
        lookup_subject_experiments[xd["subject_id"]].append(xd["experiment_id"])

    for subj in lookup_subject_experiments:
        lookup_subject_experiments[subj] = set(lookup_subject_experiments[subj])

    return lookup_subject_experiments


def share_subjects_and_experiments(src_project, dst_project, name_xnat_dst_project, subject_id, list_experiment_ids, primary=True):

    if not src_project.exists():
        raise NameError(f'Project {src_project} not available on server.')

    if not dst_project.exists():
        raise NameError(f'Project {dst_project} not available on server.')

    current_app.logger.info(f'Trying to share into project {name_xnat_dst_project}')

    xnat_subject = src_project.subject(subject_id)

    dst_subject = dst_project.subject(subject_id)
    if not dst_subject.exists():
        for eid in list_experiment_ids:
            cexp = xnat_subject.experiment(eid)
            cexp.share(name_xnat_dst_project, primary=primary)
        xnat_subject.share(name_xnat_dst_project, primary=primary)
    else:
        current_app.logger.error(f'The destination project already contains a subject with the id {subject_id}. Skipping the sharing to destination project.')

    return True


def download_dcm_images(file_list):

    # Connect to server
    xnat_server = get_xnat_connection()
    list_xnat_dicts = get_xnat_dicts_from_file_list(file_list)
    xnat_project = get_xnat_vault_project(xnat_server)

    for xnd, f in zip(list_xnat_dicts, file_list):
        create_gif_for_file(xnat_project, xnd, f)

    xnat_server.disconnect()
    return file_list


def create_gif_for_file(xnat_project, xnat_id_dict, f):

    if f.reconstructed:
        return True

    user_folder = 'Uid' + str(current_user.id)
    oh_data_path_user = Path(current_app.config['DATA_FOLDER'] + user_folder)
    oh_app_path_user = Path(current_app.config['OH_APP_PATH'] + '/src/openheart/static/' + user_folder)

    tmp_path_file = oh_data_path_user / f"temp_file_{f.id}"
    tmp_path_file.mkdir(parents=True, exist_ok=True)

    download_dcm_from_scan(xnat_project, xnat_id_dict, tmp_path_file)

    filepath_output = oh_app_path_user / "animations"
    filepath_output.mkdir(parents=True, exist_ok=True)
    filename_output = filepath_output / f"animation_file_{f.id}.gif"

    # It may take some time to unzip the files s.t. this function is called before
    if len(sorted(tmp_path_file.glob("*.dcm"))) > 0:
        create_gif_from_downloaded_recon(tmp_path_file, filename_output)
        f.reconstructed = True
        return True
    else:
        return False


def check_if_scan_was_reconstructed(scan):

    # Check if dicom exists
    if scan.resource('DICOM').exists():
        return True
    else:
        return False


def get_xnat_dicts_from_file_list(list_files):
    return [{"subject_id":f.xnat_subject_id,"experiment_id":f.xnat_experiment_id,"scan_id":f.xnat_scan_id} for f in list_files]


def get_xnat_subject(xnat_project, xnat_subject_id):

    xnat_subject = xnat_project.subject(xnat_subject_id)
    if not xnat_subject.exists():
        raise NameError(f'Subject {xnat_subject_id} does not exist.')

    return xnat_subject


def get_xnat_experiment(xnat_subject, experiment_id):

    xnat_experiment = xnat_subject.experiment(experiment_id)
    if not xnat_experiment.exists():
        raise NameError(f'Experiment {experiment_id} does not exist.')

    return xnat_experiment


def get_xnat_scan(xnat_experiment, scan_id):
    xnat_scan = xnat_experiment.scan(scan_id)
    if not xnat_scan.exists():
        raise NameError(f'Scan {xnat_scan} does not exist.')

    return xnat_scan


def get_scan_from_project(xnat_project, subject_id: str, experiment_id: str, scan_id: str):
    '''
    Getter for a xnat scan object defined by a database.File object
    input: 
        xnat_project: pyxnat project
        subject_id: xnat subject id for scan
        experiment_id: xnat experiment id for scan
        scan_id: xnat scan id for scan
    output:
        xnat scan object
    '''
    subject = get_xnat_subject(xnat_project, subject_id)
    experiment = get_xnat_experiment(subject, experiment_id)
    scan = get_xnat_scan(experiment, scan_id)

    return scan


def add_snapshot_images(list_files_to_commit):

    # Get path to animations
    user_folder = 'Uid' + str(current_user.id)
    oh_app_path_user = Path(current_app.config['OH_APP_PATH'] + '/src/openheart/static/' + user_folder)
    filepath_output = oh_app_path_user / "animations"

    # Add snapshots
    xnat_server = get_xnat_connection()
    xnat_vault = get_xnat_vault_project(xnat_server)
    list_xnat_dicts = get_xnat_dicts_from_file_list(list_files_to_commit)

    for xnd, f in zip(list_xnat_dicts, list_files_to_commit):
        scan = get_scan_from_project(xnat_vault, *get_ids_from_dict(xnd))

        scan_resource = scan.resource('SNAPSHOTS')
        scan_resource.put([str(filepath_output / f'animation_file_{f.id}_snapshot_t.gif'), ], format='gif',
                          content='THUMBNAIL')
        current_app.logger.info(f'Snapshot animation_file_{f.id}_snapshot_t.gif added to scan {scan}.')
        scan_resource.put([str(filepath_output / f'animation_file_{f.id}_snapshot.gif'), ], format='gif',
                          content='ORIGINAL')
        current_app.logger.info(f'Snapshot animation_file_{f.id}_snapshot.gif added to scan {scan}.')
    xnat_server.disconnect()


def commit_subjects_to_open(list_files_to_commit):

    xnat_server = get_xnat_connection()
    list_xnat_dicts = get_xnat_dicts_from_file_list(list_files_to_commit)
    success = share_list_of_scans(xnat_server, list_xnat_dicts)

    xnat_server.disconnect()

    return success


def delete_scans_from_vault(list_files_to_delete: list):
    '''
    Function deleting files from the XNAT server project defined by app.config['XNAT_PROJECT_ID_VAULT']
    input: list of database.File objects
    output: True
    '''
    # Connect to server
    xnat_server = get_xnat_connection()
    xnat_vault = get_xnat_vault_project(xnat_server)

    list_xnat_dicts = get_xnat_dicts_from_file_list(list_files_to_delete)
    lookup_subject_experiments = create_subject_experiment_lookup(xnat_vault, list_xnat_dicts)

    # Delete all subjects which are not committed to the open xnat project
    for subj in lookup_subject_experiments:
        try:
            subject = get_xnat_subject(xnat_vault, subj)
            subject.delete()
            current_app.logger.info(f'Subject {subj} removed from vault project.')
        except Exception as e:
            raise NameError(f'Deleting of subject with id {subj} failed. \n The error is: {e}')

    xnat_server.disconnect()

    return True