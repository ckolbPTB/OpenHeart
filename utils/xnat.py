import pyxnat
from datetime import datetime
import os, shutil
import ismrmrd
import utils
from zipfile import ZipFile

project_name = 'Vault4'
project_name_open = 'Open'

def upload_raw_mr(server_address, username, pw, raw_path, subject_list, tmp_path):
    experiment_date = datetime.utcnow().strftime('%Y-%m-%d')
    xnat_subject_list = []

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Upload each raw data file
    for ind in range(len(subject_list)):
        # Verify subject does not exist
        time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
        subject_id = 'Subj-' + time_id
        xnat_subject = xnat_project.subject(subject_id)
        if xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {subject_id} already exists.')
        else:
            # Append list [subject name, number of scans]
            xnat_subject_list.append([subject_id, subject_list[ind][1]])

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

        # Add all scans
        for snd in range(subject_list[ind][1]):
            scan_id = 'Scan_' + str(snd)
            scan = experiment.scan(scan_id)
            if scan.exists():
                print(f'Scan {scan_id} already exists')
            else:
                # Current raw data file and folder
                raw_folder = subject_list[ind][0]
                raw_file = subject_list[ind][snd+2]

                # Copy each file to temp folder
                shutil.copyfile(os.path.join(raw_path, raw_folder, raw_file), os.path.join(tmp_path, raw_file))

                # Get ISMRMRD header to populate MrScanData fields
                dset = ismrmrd.Dataset(os.path.join(tmp_path, raw_file), 'dataset', create_if_needed=False)
                header = ismrmrd.xsd.CreateFromDocument(dset.read_xml_header())
                xnat_hdr = utils.ismrmrd_2_xnat(header)
                dset.close()

                scan.create(**xnat_hdr)
                scan_resource = scan.resource('MR_RAW')
                scan_resource.put_dir(tmp_path, format='HDF5', label='MR_RAW',
                                      content='RAW', **{'xsi:type': 'xnat:mrScanData'})

                # Remove uploaded file
                os.remove(os.path.join(tmp_path, raw_file))

    xnat_server.disconnect()
    print('Data was uploaded!')
    return(xnat_subject_list)


def download_dcm_images(server_address, username, pw, xnat_subject_list, subject_list, tmp_path, qc_im_path):

    # Create a list for each subject, -1 = dicom image not yet received
    fname_qc_out = []
    for ind in range(len(xnat_subject_list)):
        fname_qc_out.append([-1]*len(xnat_subject_list[ind][1]))

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Get dicom of each subject
    for ind in range(len(xnat_subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnat_subject_list[ind][0])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {xnat_subject_list[ind]} does not exist.')

        experiment_id = xnat_subject_list[ind][0].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Add all scans
        for snd in range(xnat_subject_list[ind][1]):
            scan_id = 'Scan_' + str(snd)
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
                qc_im_full_filename = utils.create_qc_gif(tmp_path, qc_im_path, subject_list[ind][snd+2].replace('.h5', ''))
                print(f'QC image {qc_im_full_filename} created')

                fname_qc_out[ind][snd] = qc_im_full_filename

                # Delete all files in the tmp folder
                for root, dirs, files in os.walk(tmp_path):
                    for file in files:
                        os.remove(os.path.join(root, file))

    return(fname_qc_out)


def commit_to_open(server_address, username, pw, xnat_subject_list):
    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    for ind in range(len(xnat_subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnat_subject_list[ind][0])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {xnat_subject_list[ind][0]} does not exist.')

        experiment_id = xnat_subject_list[ind][0].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Move subject and experiment to open project
        xnat_subject.share(project_name_open, primary=True)
        experiment.share(project_name_open, primary=True)

    xnat_server.disconnect()
    return(True)


def delete_from_vault(server_address, username, pw, xnat_subject_list):
    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    for ind in range(len(xnat_subject_list)):
        # Verify that subject and experiment exists
        xnat_subject = xnat_project.subject(xnat_subject_list[ind][0])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {xnat_subject_list[ind][0]} does not exist.')

        experiment_id = xnat_subject_list[ind][0].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not experiment.exists():
            xnat_server.disconnect()
            raise NameError(f'Experiment {experiment_id} does not exist.')

        # Delete subject and experiment
        experiment.delete()
        xnat_subject.delete()

    xnat_server.disconnect()
    return(True)