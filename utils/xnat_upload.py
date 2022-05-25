import pyxnat
import numpy as np
from datetime import datetime
import os, shutil, glob
import ismrmrd
import utils

def upload_raw_mr(server_address, username, pw, raw_path, raw_files, tmp_path):
    experiment_date = '2022-05-04'
    scan_id = 'cart_cine_scan'

    project_name = 'mri-cine-raw'
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
        if xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Exam {experiment_id} already exists.')
        else:
            experiment.create(
                **{'experiments': 'xnat:mrSessionData',
                   'xnat:mrSessionData/date': experiment_date})

        # Add scan
        scan = experiment.scan(scan_id)
        if scan.exists():
            print(f'xnat scan {scan_id} already exists')
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