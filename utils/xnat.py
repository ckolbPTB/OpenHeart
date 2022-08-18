import pyxnat
from datetime import datetime
import os, shutil
import ismrmrd
import utils
from zipfile import ZipFile


def upload_raw_mr(server_address, username, pw, raw_path, project_name, user, tmp_path):
    experiment_date = datetime.utcnow().strftime('%Y-%m-%d')

    # Connect to server
    xnat_server = pyxnat.Interface(server=server_address, user=username, password=pw)

    # Verify project exists
    xnat_project = xnat_server.select.project(project_name)
    if not xnat_project.exists():
        xnat_server.disconnect()
        raise NameError(f'Project {project_name} not available on server.')

    # Upload each raw data file
    for ind in range(user.get_num_subjects()):
        # Verify subject does not exist
        time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
        subject_id = 'Subj-' + time_id
        xnat_subject = xnat_project.subject(subject_id)
        if xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {subject_id} already exists.')


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
        for snd in range(user.get_num_scans(user.get_subjects()[ind])):
            scan_id = 'Scan_' + str(snd)
            scan = experiment.scan(scan_id)
            if scan.exists():
                print(f'Scan {scan_id} already exists')
            else:
                # Current raw data file
                raw_file = user.get_raw_data(user.get_subjects()[ind], user.get_scans(user.get_subjects()[ind])[snd])
                raw_file += '.h5'

                # Copy each file to temp folder
                shutil.copyfile(os.path.join(raw_path, raw_file), os.path.join(tmp_path, raw_file))

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

                # Add xnat info to user
                user.add_xnat_scan(subject_id, scan_id)

    xnat_server.disconnect()
    return(user)


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
        print('xnat_subject', xnat_subject_user)

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

        # Go through all scans
        for snd in range(user.get_num_xnat_scans(xnat_subject_user)):
            subject_name, scan_name = user.get_subject_scan_by_idx(ind, snd)
            print(subject_name, ' - ', scan_name)

            if not user.get_recon_flag(subject_name, scan_name):
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
                    cfile = user.get_raw_data(subject_name, scan_name)
                    qc_im_full_filename = utils.create_qc_gif(tmp_path, qc_im_path, cfile)
                    print(f'QC image {qc_im_full_filename} created')

                    # Upload snapshot images
                    scan_resource = scan.resource('SNAPSHOTS')
                    scan_resource.put([qc_im_path + cfile + '_snapshot_t.gif',], format='gif', content='THUMBNAIL')
                    scan_resource.put([qc_im_path + cfile + '_snapshot.gif',], format='gif', content='ORIGINAL')

                    # Update user info
                    user.set_recon_flag(subject_name, scan_name)

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