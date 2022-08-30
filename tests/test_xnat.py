import pytest

import tempfile
from uuid import uuid4
from conftest import app, test_files
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

def delete_subjects_from_open(xnat_server, app, xnat_dicts):
    try:
        for f in xnat_dicts:
            teardown_xnat_file(xnat_server, 'XNAT_PROJECT_ID_OPEN', f)
    except NameError:
        app.logger.debug(f"In test trying to delete an xnat scan that doesnt exist: {f}")

def create_mock_xnat_scans_dict():

    subj_ids = [0,1,2]
    num_exps = 3
    scan_ids = [0,1,2]
    exp_date = "1900.01.01"

    xnat_files = []
    for sub in subj_ids:
        for i in range(num_exps):
            exp = uuid4()
            for scan in scan_ids:
                cfile={"subject_id": str(sub), "experiment_id": str(exp), "scan_id": str(scan), "experiment_date":exp_date}
                xnat_files.append(cfile)

    return xnat_files

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
            for f in xnat_dicts:
                success *= xnat.create_xnat_scan(xnat_server, 'XNAT_PROJECT_ID_OPEN', mock_xnat_scan_hdr(), f)
        except NameError:
            success *= False

        delete_subjects_from_open(xnat_server, app, xnat_dicts)

        xnat_server.disconnect()

    assert success, "You did not successfully create every scan from the list. Probably they already existed."


def test_upload_rawdata_file_to_scan(app):

    xnat_files = create_mock_xnat_scans_dict()
    xnat_files = xnat_files[:2]
    with app.app_context():
        xnat_server = xnat.get_xnat_connection()
        success = True

        try:
            for f in xnat_files:
                success *= xnat.create_xnat_scan(xnat_server, 'XNAT_PROJECT_ID_OPEN', mock_xnat_scan_hdr(), f)
        except NameError:
            success = False

        tmp_rawfile = tempfile.NamedTemporaryFile(delete=False)
        try:
            for f in xnat_files:
                upload_ok, __ = xnat.upload_rawdata_file_to_scan(xnat_server, 'XNAT_PROJECT_ID_OPEN', f, [tmp_rawfile.name])
                success *= upload_ok
        except NameError:
            success = False

        delete_subjects_from_open(xnat_server, app, xnat_files)

        assert success, "Something went wront with the uplaod of the file to the XNAT"

        xnat_server.disconnect()

def test_create_subject_in_vault():
    pass

def upload_raw_mr():
    pass

def test_download_dcm_images():
    pass

def test_commit_subjects_to_open():
    pass

def test_delete_from_vault():
    pass
