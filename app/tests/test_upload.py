from conftest import test_app_configuration, test_file

from openheart.utils import xnat

def test_download_dcm_img():

    tmp_path = '/home/sirfuser/Temp/'

    server = test_app_configuration['XNAT_SERVER']
    user = test_app_configuration['XNAT_ADMIN_USER']
    pw = test_app_configuration['XNAT_ADMIN_PW']
    project = test_app_configuration['XNAT_PROJECT_ID_VAULT']


    xnat.download_dcm_images([test_file], server, user, pw, project, tmp_path, tmp_path)

test_download_dcm_img()