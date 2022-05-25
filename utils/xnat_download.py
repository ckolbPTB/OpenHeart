import pyxnat
from pyxnat.core import downloadutils as du
import numpy as np
from datetime import datetime
import os, os.path, shutil, glob

from zipfile import ZipFile

from xnat_upload import upload_raw_mr
import utils

project_name = 'mri-cine-raw'
scan_id = 'cart_cine_scan'

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
        # Verify that subject exists
        xnat_subject = xnat_project.subject(subject_list[ind])
        if not xnat_subject.exists():
            xnat_server.disconnect()
            raise NameError(f'Subject {subject_list[ind]} does not exist.')

        experiment_id = subject_list[ind].replace('Subj', 'Exp')
        experiment = xnat_subject.experiment(experiment_id)
        if not xnat_subject.exists():
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
