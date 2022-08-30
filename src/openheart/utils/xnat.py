from pathlib import Path
import pyxnat
from datetime import datetime
import os
import ismrmrd
from openheart.utils import utils
from zipfile import ZipFile
from flask import current_app
import sys

from itertools import chain

def get_xnat_connection():
    xnat_server = pyxnat.Interface(server=current_app.config['XNAT_SERVER'], user=current_app.config['XNAT_ADMIN_USER'], password=current_app.config['XNAT_ADMIN_PW'])
    return xnat_server

def get_xnat_project(xnat_server, name_project):

    xnat_project = xnat_server.select.project(current_app.config[name_project])

    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {current_app.config[name_project]} not available on server.')

    return xnat_project

def get_xnat_vault_project(xnat_server):
    return get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_VAULT')

def get_xnat_open_project(xnat_server):
    return get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_OPEN')

def upload_raw_mr(list_files, server_address, username, pw, project_name):

    experiment_date = datetime.utcnow().strftime('%Y-%m-%d')

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Ensure to use unique subjects
    all_subjects = get_subject_uniques(list_files)

    for subj_id in all_subjects:
        current_app.logger.info(f"We will upload files for {subj_id}.")

        subject_files = [f for f in list_files if f.subject_unique == subj_id]
        xnat_subject = xnat_project.subject(subj_id)

        if xnat_subject.exists():
            current_app.logger.warning(f'Subject {subj_id} already exists.')
            xnat_server.disconnect()
            raise NameError(f'Subject {subj_id} already exists.')

        # Add exam
        time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
        experiment_id = f"Exp-{time_id}"
        experiment = xnat_subject.experiment(experiment_id)

        if not experiment.exists():
            experiment.create(
                **{'experiments': 'xnat:mrSessionData',
                    'xnat:mrSessionData/date': experiment_date})

        for idx, sf in enumerate(subject_files):
            scan_id = f'Scan_{idx}'
            scan = experiment.scan(scan_id)
            if scan.exists():
                current_app.logger.error(f'Scan generated from {scan_id} already exists.')
            else:

                current_app.logger.info(f"Starting with upload of {sf.name}, aka. {sf.name_unique}")
                # Get ISMRMRD header to populate MrScanData fields
                dset = ismrmrd.Dataset(sf.name_unique, 'dataset', create_if_needed=False)
                header = ismrmrd.xsd.CreateFromDocument(dset.read_xml_header())
                xnat_hdr = utils.ismrmrd_2_xnat(header)
                dset.close()

                scan.create(**xnat_hdr)
                scan_resource = scan.resource('MR_RAW')
                scan_resource.put([sf.name_unique], format='HDF5', label='MR_RAW', content='RAW', **{'xsi:type': 'xnat:mrScanData'})

                current_app.logger.info(f"Finished uploading of {sf.name}, aka. {sf.name_unique}")

                sf.transmitted =  True

                sf.xnat_subject_id = subj_id
                sf.xnat_experiment_id = experiment_id
                sf.xnat_scan_id = scan_id


    current_app.logger.info(f"Finished uploading of of data to xnat. Disconnecting...")
    xnat_server.disconnect()

    return list_files

def create_xnat_scan(xnat_sever, name_project, scan_hdr, xnat_file):

    xnat_project = get_xnat_project(xnat_sever, name_project)

    subject_id = xnat_file["subject_id"]
    experiment_id = xnat_file["experiment_id"]
    scan_id = xnat_file["scan_id"]

    experiment_date = xnat_file["experiment_date"]

    xnat_subject = xnat_project.subject(subject_id)

    if xnat_subject.exists():
        current_app.logger.warning(f'Subject {subject_id} already exists.')

    experiment = xnat_subject.experiment(experiment_id)

    if not experiment.exists():
        experiment.create(
            **{'experiments': 'xnat:mrSessionData',
                'xnat:mrSessionData/date': experiment_date})

    scan = experiment.scan(scan_id)

    if scan.exists():
        current_app.logger.error(f'Scan {scan_id} in experiment {experiment_id} in subject {subject_id} already exists.')
        raise NameError(f"The scan {scan_id} already exists for subject {subject_id} and experiment {experiment_id}")
    else:
        scan.create(**scan_hdr)

    return True

def upload_rawdata_file_to_scan(xnat_sever, name_project, xnat_file_dict, list_filenames_rawdata):

    xnat_project = get_xnat_project(xnat_sever, name_project)
    subject_id = xnat_file_dict["subject_id"]
    experiment_id = xnat_file_dict["experiment_id"]
    scan_id = xnat_file_dict["scan_id"]

    __, __, scan = check_xnat_file_existence(xnat_project, subject_id, experiment_id, scan_id)

    scan_resource = scan.resource('MR_RAW')
    scan_resource.put(list_filenames_rawdata, format='HDF5', label='MR_RAW', content='RAW', **{'xsi:type': 'xnat:mrScanData'})

    return True, scan


def download_dcm_from_scan(xnat_server, name_project, xnat_file_dict, fpath_output):

    fpath_output = Path(fpath_output)

    xnat_project = get_xnat_project(xnat_server, name_project)
    subject_id = xnat_file_dict["subject_id"]
    experiment_id = xnat_file_dict["experiment_id"]
    scan_id = xnat_file_dict["scan_id"]

    __, __, scan = check_xnat_file_existence(xnat_project, subject_id, experiment_id, scan_id)

    if check_if_scan_was_reconstructed(scan):

        # Download dicom and extract it
        fname_dcm_zip = Path(scan.resource('DICOM').get(str(fpath_output)))
        with ZipFile(fname_dcm_zip, 'r') as zip:
            zip.extractall(str(fpath_output))

        remove_files_from_path(fpath_output, {".zip"})

        return True
    else:
        return False

def create_gif_from_downloaded_recon(fpath_dicoms, qc_im_path, filename_output):

    # Create gif
    qc_im_full_filename = utils.create_qc_gif(str(fpath_dicoms), str(qc_im_path), str(filename_output))
    current_app.logger.info(f'QC image {qc_im_full_filename} created')
    remove_files_from_path(Path(fpath_dicoms), {".dcm"})

    return True, qc_im_full_filename

def remove_files_from_path(fpath, list_extensions):
    files_to_remove = list(chain.from_iterable([sorted(fpath.glob(f"*{ext}")) for ext in list_extensions]))
    for f in files_to_remove:
        os.remove(str(f))

def share_list_of_scans(xnat_server, list_xnat_dicts):

    assert xnat_open.exists(), f"The project {key_open_project} does not exist on the XNAT server."

    xnat_vault = get_xnat_vault_project(xnat_server)
    xnat_open = get_xnat_open_project(xnat_server)

    #check if all are in 
    lookup_subject_experiments = create_subject_experiment_lookup(xnat_vault, list_xnat_dicts)
    print(f"We found {lookup_subject_experiments}")

    for subj in lookup_subject_experiments:
        share_subjects_and_experiments(xnat_vault, xnat_open, subj, lookup_subject_experiments[subj])

    return True

def create_subject_experiment_lookup(project, list_xnat_dicts):
    list_subjects = []

    for xd in list_xnat_dicts:
        sid = xd["subject_id"]
        list_subjects.append(sid)

        check_xnat_file_existence(project, sid, xd["experiment_id"], xd["scan_id"])

    list_subjects = set(list_subjects)

    lookup_subject_experiments = {}

    for subj in list_subjects:
        lookup_subject_experiments[subj] = []

    for xd in list_xnat_dicts:
        lookup_subject_experiments[xd["subject_id"]].append(xd["experiment_id"])

    for subj in lookup_subject_experiments:
        lookup_subject_experiments[subj] = set(lookup_subject_experiments[subj])


    return lookup_subject_experiments

def share_subjects_and_experiments(src_project, dst_project, subject_id, list_experiment_ids, primary=True):

    if not src_project.exists():
        raise NameError(f'Project {src_project} not available on server.')

    if not dst_project.exists():
        raise NameError(f'Project {dst_project} not available on server.')

    name_xnat_dst_project = dst_project.aliases()['ID'] 


    xnat_subject = src_project.subject(subject_id)

    dst_subject = dst_project.subject(subject_id)
    if not dst_subject.exists():
        xnat_subject.share(name_xnat_dst_project, primary=primary)

        for eid in list_experiment_ids:
            cexp = xnat_subject.experiment(eid)
            cexp.share(name_xnat_dst_project, primary=primary)
    else:
        current_app.logger.warning(f"The destination project already contains a subject with the id {subject_id}. Skipping the sharing to destination project.")

    return True

def check_xnat_file_existence(xnat_project, subject_id, experiment_id, scan_id):

    xnat_subject = xnat_project.subject(subject_id)
    if not xnat_subject.exists():
        raise NameError(f"The subject {subject_id} does not exist in project {xnat_project}.")

    experiment = xnat_subject.experiment(experiment_id)
    if not experiment.exists():
        raise NameError(f"The subject {subject_id} does not exist in project {xnat_project}.")

    scan = experiment.scan(scan_id)
    if not scan.exists():
        raise NameError(f"The subject {subject_id} does not exist in project {xnat_project}.")

    return xnat_subject, experiment, scan

def get_unique_attribute(list_of_objects, attribute):
    return set([getattr(obj,attribute) for obj in list_of_objects])

def get_subject_uniques(list_files):
    return get_unique_attribute(list_files, 'subject_unique')

def get_unique_xnat_subject_id(list_files):
    return get_unique_attribute(list_files, 'xnat_subject_id')

def get_unique_xnat_exp_id(list_files, subj_id=None):
    if subj_id is None:
        return get_unique_attribute(list_files, 'xnat_experiment_id')
    else:
        list_files_of_subj = [f for f in list_files if f.xnat_subject_id == subj_id]
        return get_unique_attribute(list_files_of_subj, 'xnat_experiment_id')



def download_dcm_images(file_list, server_address, username, pw, project_name, tmp_path, qc_im_path):

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    for f in file_list:
        if f.reconstructed:
            continue
        # Check if dicom exists
        recon_performed, scan = check_if_scan_was_reconstructed(xnat_server, f, project_name)
        if recon_performed:

            tmp_path_file = Path(tmp_path) / f"temp_file_{f.id}"
            tmp_path_file.mkdir(parents=True, exist_ok=True)

            # Download dicom and extract it
            fname_dcm_zip = Path(scan.resource('DICOM').get(str(tmp_path_file)))
            with ZipFile(fname_dcm_zip, 'r') as zip:
                zip.extractall(str(tmp_path_file))

            # Create gif
            cfile = f"animation_file_{f.id}"
            qc_im_full_filename = utils.create_qc_gif(str(tmp_path_file), qc_im_path, cfile)
            current_app.logger.info(f'QC image {qc_im_full_filename} created')
            current_app.logger.info(f"Trying to clean up {tmp_path_file}")

            files_to_remove = list(chain.from_iterable([sorted(tmp_path_file.glob(f"*{ext}")) for ext in {".zip", ".dcm"}]))
            for tempfiles in files_to_remove:
                os.remove(str(tempfiles))

            os.rmdir(str(tmp_path_file))

            f.reconstructed = True

    xnat_server.disconnect()

    return file_list

def check_if_scan_was_reconstructed(scan):

    # Check if dicom exists
    if scan.resource('DICOM').exists():
        return True
    else:
         return False

def commit_subjects_to_open(list_files_to_commit, server_address, username, pw, project_name, project_name_open):

    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    list_xnat_subject_id = get_unique_xnat_subject_id(list_files_to_commit)

    # Verify project exists
    for xnsid in list_xnat_subject_id:
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnsid)
        if not xnat_subject.exists():
            current_app.logger.warning(f"The subject with id {xnsid} does not exist.")
            continue
        list_xnat_exp_id = get_unique_xnat_exp_id(list_files_to_commit, subj_id = xnsid)

        xnat_subject.share(project_name_open, primary=True)

        for xneid in list_xnat_exp_id:
            experiment = xnat_subject.experiment(xneid)
            if not experiment.exists():
                current_app.logger.warning(f"The experiment with id {xneid} does not exist.")
                continue
            experiment.share(project_name_open, primary=True)

    xnat_server.disconnect()

    return True

def get_list_subjects_and_experiments(list_files_to_commit, server_address, username, pw, project_name):
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')


def delete_scans_from_vault(list_files, server_address, username, pw, project_name):

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    for f in list_files:
        __, __, __, scan = verify_file_existence(xnat_server, f, project_name)
        scan.delete()

    xnat_server.disconnect()
    return(True)

def delete_subjects_from_project(list_xnat_subject_id, server_address, username, pw, project_name):

    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    for xnsid in list_xnat_subject_id:
        xnat_project = xnat_server.select.project(project_name)
        if not xnat_project.exists():
            xnat_server.disconnect()
            raise NameError(f'Project {project_name} not available on server.')

        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnsid)
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {xnsid} does not exist.')

        xnat_subject.delete()

    xnat_server.disconnect()

    return True

def delete_from_vault(file, server_address, username, pw, project_name):
    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    try:
        __, xnat_subject, experiment, scan = verify_file_existence(xnat_server, file, project_name)
        # Delete subject and experiment
        xnat_subject.delete()
    except NameError:
        current_app.logger.error(f"The subject/experiment/scan {file.xnat_subject_id}/{file.xnat_experiment_id}/{file.xnat_scan_id} you tried to delete from vault does not exist." \
                                  "The subject was deleted probaly already as a whole.")
    xnat_server.disconnect()
    return(True)

def verify_file_existence(xnat_server, file, project_name):

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Verify that subject and experiment exists
    xnat_subject = xnat_project.subject(file.xnat_subject_id)
    if not xnat_subject.exists():
        xnat_server.disconnect()
        raise NameError(f'Subject {file.xnat_subject_id} does not exist.')

    experiment_id = file.xnat_experiment_id
    experiment = xnat_subject.experiment(experiment_id)
    if not experiment.exists():
        xnat_server.disconnect()
        raise NameError(f'Experiment {experiment_id} does not exist.')

    scan = experiment.scan(file.xnat_scan_id)
    if not scan.exists():
        xnat_server.disconnect()
        raise NameError(f'Scan {scan} does not exist.')


    return xnat_project, xnat_subject, experiment, scan