from uuid import uuid4
import pyxnat
from datetime import datetime
import os
import ismrmrd
from openheart.utils.utils import ismrmrd_2_xnat
from zipfile import ZipFile
from flask import current_app
import sys

def upload_raw_mr(all_files, server_address, username, pw, project_name):

    experiment_date = datetime.utcnow().strftime('%Y-%m-%d')

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Verify subject does not exist
    all_subjects = set([f.subject_unique for f in all_files])


    for subj_id in all_subjects:
        current_app.logger.info(f"We will upload files for {subj_id}.")

        subject_files = [f for f in all_files if f.subject_unique == subj_id]
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
                xnat_hdr = ismrmrd_2_xnat(header)
                dset.close()

                scan.create(**xnat_hdr)
                scan_resource = scan.resource('MR_RAW')
                scan_resource.put([sf.name_unique], format='HDF5', label='MR_RAW', content='RAW', **{'xsi:type': 'xnat:mrScanData'})

                current_app.logger.info(f"Finished uploading of {sf.name}, aka. {sf.name_unique}")

                sf.transmitted =  True

                sf.xnat_subj_id = subj_id
                sf.xnat_experiment_id = experiment_id
                sf.xnat_scan_id = scan_id


    current_app.logger.info(f"Finished uploading of of data to xnat. Disconnecting...")
    xnat_server.disconnect()

    return all_files


def download_dcm_images(server_address, username, pw, project_name, user, tmp_path, qc_im_path):

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Get dicom of each subject
    print(user.get_num_xnat_subjects())
    for ind in range(user.get_num_xnat_subjects()):
        # Get current subject
        xnat_subject_user = user.get_xnat_subjects()[ind]

        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnat_subject_user)
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {xnat_subject} does not exist.')

        experiment_id = xnat_subject_user.replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Add all scans
        for snd in range(user.get_num_xnat_scans(xnat_subject_user)):
            scan_id = user.get_xnat_scans(xnat_subject_user)[snd]
            scan = experiment.scan(scan_id)
            if not scan.exists():
                xnat_server.disconnect()
                raise NameError(f'Scan {scan_id} does not exist.')

            # Check if dicom exists
            if scan.resource('DICOM').exists():
                # Make sure folder is empty
                for root, dirs, files in os.walk(tmp_path):
                    for file in files:
                        os.remove(os.path.join(root, file))

                # Download dicom and extract it
                fname_dcm_zip = scan.resource('DICOM').get(tmp_path)

                with ZipFile(fname_dcm_zip, 'r') as zip:
                    zip.extractall(tmp_path)

                # Create gif
                subject, scan = user.get_subject_scan_by_idx(ind, snd)
                print(subject, ' - ', scan)
                cfile = user.get_raw_data(subject, scan)
                qc_im_full_filename = utils.create_qc_gif(tmp_path, qc_im_path, cfile)
                print(f'QC image {qc_im_full_filename} created')

                # Update user info
                user.set_recon_flag(subject, scan)

                # Delete all files in the tmp folder
                for root, dirs, files in os.walk(tmp_path):
                    for file in files:
                        os.remove(os.path.join(root, file))

    xnat_server.disconnect()
    return(user)


def commit_to_open(server_address, username, pw, project_name, project_name_open, xnat_subject_list):
    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    for ind in range(len(xnat_subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnat_subject_list[ind])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {xnat_subject_list[ind]} does not exist.')

        experiment_id = xnat_subject_list[ind].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Move subject and experiment to open project
        xnat_subject.share(project_name_open, primary=True)
        experiment.share(project_name_open, primary=True)

    xnat_server.disconnect()
    return(True)


def delete_from_vault(server_address, username, pw, project_name, xnat_subject_list):
    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    for ind in range(len(xnat_subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnat_subject_list[ind])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {xnat_subject_list[ind]} does not exist.')

        experiment_id = xnat_subject_list[ind].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Delete subject and experiment
        experiment.delete()
        xnat_subject.delete()

    xnat_server.disconnect()
    return(True)