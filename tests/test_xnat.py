import pytest

import tempfile
from pathlib import Path
from uuid import uuid4
# from conftest import app, test_files
from openheart.utils import xnat


def mock_xnat_scan_hdr():
    xnat_dict = {}

    xnat_dict['scans'] = 'xnat:mrScanData'
    xnat_dict['xnat:mrScanData/fieldStrength'] = 2.89

    return xnat_dict

def teardown_xnat_file(xnat_server, name_project, xnat_file):

    xnat_project = xnat.get_xnat_project(xnat_server, name_project)
    xnat_subject = xnat_project.subject(xnat_file["subject_id"])

    if xnat_subject.exists():
        xnat_subject.delete(delete_files=True)

def delete_subjects_from_vault(xnat_server, app, xnat_dicts):
    try:
        for f in xnat_dicts:
            teardown_xnat_file(xnat_server, 'XNAT_PROJECT_ID_VAULT', f)
    except NameError:
        app.logger.debug(f"In test trying to delete an xnat scan that doesnt exist: {f}")

def create_mock_xnat_scans_dict():

    subj_ids = [0,1]
    num_exps = 3
    scan_ids = [0,1]
    exp_date = "1900.01.01"

    xnat_files = []
    for sub in subj_ids:
        for i in range(num_exps):
            exp = uuid4()
            for scan in scan_ids:
                cfile={"subject_id": str(sub), "experiment_id": str(exp), "scan_id": str(scan), "experiment_date":exp_date}
                xnat_files.append(cfile)

    return xnat_files


def upload_DICOM_files_to_scan(xnat_project, xnat_file_dict, list_filenames_dicoms):

    subject_id = xnat_file_dict["subject_id"]
    experiment_id = xnat_file_dict["experiment_id"]
    scan_id = xnat_file_dict["scan_id"]

    scan = xnat.get_scan_from_project(xnat_project, subject_id, experiment_id, scan_id)

    scan_resource = scan.resource('DICOM')
    scan_resource.put(list_filenames_dicoms, format='DCM', label='DICOM', content='IMAGE', **{'xsi:type': 'xnat:mrScanData'})

    return True, scan


def test_get_xnat_connection(app):
    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        assert True, "The connection to the XNAT could not be established."
        xnat_server.disconnect() 


@pytest.mark.parametrize(('projectname'),(
    ('XNAT_PROJECT_ID_VAULT'),
    ('XNAT_PROJECT_ID_OPEN'),
))
def test_get_xnat_project(app, projectname):
    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        proj = xnat.get_xnat_project(xnat_server, projectname)
        assert proj.exists(), f"The project {projectname} does not exist."
        xnat_server.disconnect()

def test_create_xnat_scan(app):
    xnat_dicts = create_mock_xnat_scans_dict()
    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        success = True
        try:
            xnat_project = xnat.get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_VAULT')
            for f in xnat_dicts:
                success *= xnat.create_xnat_scan(xnat_project, mock_xnat_scan_hdr(), f)
        except NameError:
            success *= False

        delete_subjects_from_vault(xnat_server, app, xnat_dicts)

        xnat_server.disconnect()

    assert success, "You did not successfully create every scan from the list. Probably they already existed."


def test_upload_rawdata_file_to_scan(app):

    xnat_files = create_mock_xnat_scans_dict()

    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        success = True
        xnat_project = xnat.get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_VAULT')
        try:
            for f in xnat_files:
                success *= xnat.create_xnat_scan(xnat_project, mock_xnat_scan_hdr(), f)
        except NameError:
            success = False

        tmp_rawfile = tempfile.NamedTemporaryFile(delete=False)
        try:
            for f in xnat_files:
                upload_ok, __ = xnat.upload_rawdata_file_to_scan(xnat_project, f, [tmp_rawfile.name])
                success *= upload_ok
        except NameError:
            success = False

        delete_subjects_from_vault(xnat_server, app, xnat_files)

        assert success, "Something went wront with the upload of the file to the XNAT"

        xnat_server.disconnect()

def test_download_dcm_from_scan(app):
    filepath_dicoms = Path('/test/input/dicoms')
    filepath_test_output = Path('/test/output')

    list_fnames_dicoms = sorted(filepath_dicoms.glob("*.dcm"))
    list_fnames_dicoms = [str(fn) for fn in list_fnames_dicoms]

    num_dicoms_upload = len(list_fnames_dicoms)

    xnat_files = create_mock_xnat_scans_dict()
    xnat_files = xnat_files[:2]

    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        success = True
        xnat_project = xnat.get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_VAULT')
        for f in xnat_files:
            success *= xnat.create_xnat_scan(xnat_project, mock_xnat_scan_hdr(), f)

        for f in xnat_files:
            upload_ok, __ = upload_DICOM_files_to_scan(xnat_project, f, list_fnames_dicoms)
            assert upload_ok, "The upload of the dicom files failed"

        for f in xnat_files:
            success *= xnat.download_dcm_from_scan(xnat_project, f, filepath_test_output)

            num_dicoms_download = sorted(filepath_test_output.glob("*.dcm"))
            assert num_dicoms_upload == num_dicoms_upload, f"For {f} the # dicoms downloaded !=  # uploaded {num_dicoms_download} vs {num_dicoms_upload}"

        delete_subjects_from_vault(xnat_server, app, xnat_files)

        assert success, "Something went wrong with the dicoms download of the file to the XNAT."
        xnat_server.disconnect()

def test_create_gif_from_downloaded_recon(app):

    filepath_dicoms = Path('/test/input/dicoms')
    filepath_test_output = Path('/test/output')

    list_fnames_dicoms = sorted(filepath_dicoms.glob("*.dcm"))
    list_fnames_dicoms = [str(fn) for fn in list_fnames_dicoms]

    xnat_files = create_mock_xnat_scans_dict()
    xnat_files = xnat_files[:2]

    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        xnat_project = xnat.get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_VAULT')
        for f in xnat_files:
            assert xnat.create_xnat_scan(xnat_project, mock_xnat_scan_hdr(), f), f"Creating of {f} failed on the XNAT server."
            assert upload_DICOM_files_to_scan(xnat_project, f, list_fnames_dicoms)[0], f"Uploading {list_fnames_dicoms} failed."
            assert xnat.download_dcm_from_scan(xnat_project, f, filepath_test_output), f"Downloading the reconstruction of {f} failed"

            fname_gif = f'animation_sub_{f["subject_id"]}_exp_{f["experiment_id"]}_scan_{f["scan_id"]}'

            gif_success, fpath_gif = xnat.create_gif_from_downloaded_recon(filepath_test_output, filepath_test_output, '/' + fname_gif)
            assert gif_success, f"The construction of the gif failed."
            fpath_gif = Path(fpath_gif)
            assert fpath_gif.exists(), f"The gif does not exist at the filepath that create_gif_from_downloaded_recon was  failed."

        delete_subjects_from_vault(xnat_server, app, xnat_files)
        xnat_server.disconnect()

def test_share_list_of_scans(app):
    xnat_files = create_mock_xnat_scans_dict()

    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        xnat_project = xnat.get_xnat_project(xnat_server, 'XNAT_PROJECT_ID_VAULT')
        tmp_rawfile = tempfile.NamedTemporaryFile(delete=False)

        for f in xnat_files:
            assert xnat.create_xnat_scan(xnat_project, mock_xnat_scan_hdr(), f), f"Creating of {f} failed on the XNAT server."
            assert xnat.upload_rawdata_file_to_scan(xnat_project, f, [tmp_rawfile.name])[0], f"Uploading of rawdata to XNAT server failed."

        assert xnat.share_list_of_scans(xnat_server, xnat_files)

        delete_subjects_from_vault(xnat_server, app, xnat_files)

        xnat_server.disconnect()


