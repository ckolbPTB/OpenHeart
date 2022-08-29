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


def get_unique_attribute(list_of_objects, attribute):
    return set([getattr(obj,attribute) for obj in list_of_objects])

def get_subject_uniques(list_files):
    return get_unique_attribute(list_files, 'subject_unique')

def get_unique_xnat_exp_id(list_files):
    return get_unique_attribute(list_files, 'xnat_experiment_id')

def get_unique_xnat_subject_id(list_files):
    return get_unique_attribute(list_files, 'xnat_subject_id')

def download_dcm_images(file_list, server_address, username, pw, project_name, tmp_path, qc_im_path):

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    for f in file_list:
        if f.reconstructed:
            continue
        # Check if dicom exists
        recon_performed, scan = check_if_file_was_reconstructed(xnat_server, f, project_name)
        if recon_performed:

            tmp_path_file = Path(tmp_path) / f"temp_file_{f.id}"
            tmp_path_file.mkdir(parents=True, exist_ok=True)

            # Download dicom and extract it
            fname_dcm_zip = Path(scan.resource('DICOM').get(str(tmp_path_file)))
            print(f"We have extracted them to {fname_dcm_zip}.")
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

def check_if_file_was_reconstructed(xnat_server, f, project_name):
    __, __, __, scan = verify_file_existence(xnat_server, f, project_name)
    # Check if dicom exists
    if scan.resource('DICOM').exists():
        return True, scan
    else:
         return False, scan

def commit_subjects_to_open(list_xnat_subject_id, server_address, username, pw, project_name, project_name_open):
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

        xnat_subject.share(project_name_open, primary=True)

    xnat_server.disconnect()

    return True

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