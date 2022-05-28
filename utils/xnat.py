import pyxnat
from datetime import datetime
import os, shutil
import ismrmrd
import utils
from zipfile import ZipFile

project_name = 'Vault4'
project_name_open = 'Open'
scan_id = 'cart_cine_scan'

def upload_raw_mr(server_address, username, pw, raw_path, raw_files, tmp_path):
    experiment_date = datetime.utcnow().strftime('%Y-%m-%d')
    subject_list = []

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Upload each raw data file
    for ind in range(len(raw_files)):
        # Copy each file to temp folder
        shutil.copyfile(raw_path + raw_files[ind], tmp_path + raw_files[ind])

        # Verify subject does not exist
        time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
        subject_id = 'Subj-' + time_id
        xnat_subject = xnat_project.subject(subject_id)
        if xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {subject_id} already exists.')
        else:
            subject_list.append(subject_id)

        # Add exam
        experiment_id = 'Exp-' + time_id
        experiment = xnat_subject.experiment(experiment_id)
        if experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} already exists.')
        else:
            experiment.create(
                **{'experiments': 'xnat:mrSessionData',
                   'xnat:mrSessionData/date': experiment_date})

        # Add scan
        scan = experiment.scan(scan_id)
        if scan.exists():
            print(f'Scan {scan_id} already exists')
        else:
            # Get ISMRMRD header to populate MrScanData fields
            dset = ismrmrd.Dataset(tmp_path + raw_files[ind], 'dataset', create_if_needed=False)
            header = ismrmrd.xsd.CreateFromDocument(dset.read_xml_header())
            xnat_hdr = utils.ismrmrd_2_xnat(header)
            dset.close()

            scan.create(**xnat_hdr)
            scan_resource = scan.resource('MR_RAW')
            scan_resource.put_dir(tmp_path, format='HDF5', label='MR_RAW',
                                  content='RAW', **{'xsi:type': 'xnat:mrScanData'})

            # Remove uploaded file
            os.remove(tmp_path + raw_files[ind])

    xnat_server.disconnect()
    print('Data was uploaded!')
    return(subject_list)


def download_dcm_images(server_address, username, pw, subject_list, fname_qc_in, tmp_path, qc_im_path):

    fname_qc_out = [-1]*len(subject_list)

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Get dicom of each subject
    for ind in range(len(subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(subject_list[ind])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {subject_list[ind]} does not exist.')

        experiment_id = subject_list[ind].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Select scan
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
            qc_im_full_filename = utils.create_qc_gif(tmp_path, qc_im_path, fname_qc_in[ind])
            print(f'QC image {qc_im_full_filename} created')

            fname_qc_out[ind] = qc_im_full_filename

            # Delete all files in the tmp folder
            for root, dirs, files in os.walk(tmp_path):
                for file in files:
                    os.remove(os.path.join(root, file))

    return(fname_qc_out)


def commit_to_open(server_address, username, pw, subject_list):
    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    for ind in range(len(subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(subject_list[ind])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {subject_list[ind]} does not exist.')

        experiment_id = subject_list[ind].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Move subject and experiment to open project
        xnat_subject.share(project_name_open, primary=True)
        experiment.share(project_name_open, primary=True)

    xnat_server.disconnect()
    return(True)


def delete_from_vault(server_address, username, pw, subject_list):
    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    for ind in range(len(subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(subject_list[ind])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {subject_list[ind]} does not exist.')

        experiment_id = subject_list[ind].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Delete subject and experiment
        experiment.delete()
        xnat_subject.delete()

    xnat_server.disconnect()
    return(True)