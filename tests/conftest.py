from pathlib import Path

import os
import tempfile

import pytest
from openheart import create_app

from openheart.database import File, User, db
import pyxnat

test_user = User(email='test@testmail.com')

# we need files that are 
test_files = []
test_files.append(
            File(id = 0,
                user_id = 0,
                xnat_subject_id = 'TestSub0',
                xnat_experiment_id = 'TestExpSub0',
                xnat_scan_id = 'TestScan')
)
test_files.append(
            File(id = 1,
                user_id = 0,
                xnat_subject_id = 'TestSub0',
                xnat_experiment_id = 'TestExpSub0',
                xnat_scan_id = 'TestScan1')
)

test_files.append(
            File(id = 2,
                user_id = 0,
                xnat_subject_id = 'TestSub1',
                xnat_experiment_id = 'TestExpSub1',
                xnat_scan_id = 'TestScan2')
)


test_app_configuration = {
        'TESTING': True,
        'XNAT_SERVER':"http://e81151.berlin.ptb.de:8080/xnat",
        'XNAT_ADMIN_USER':"admin",
        'XNAT_ADMIN_PW':"e81151",
        'XNAT_PROJECT_ID_VAULT':"TestVault",
        'XNAT_PROJECT_ID_OPEN':"TestOpen"
    }

@pytest.fixture(scope='module')
def app():
    db_fd, db_path = tempfile.mkstemp()
    test_app_configuration['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app = create_app(test_app_configuration)

    with app.app_context():
        db.session.add(test_user)
        for f in test_files:
            db.session.add(f)
        db.session.commit()

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()

