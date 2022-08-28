from pathlib import Path

import os
import tempfile

import pytest
from openheart import create_app

from openheart.user import File, User, db
from werkzeug.security import generate_password_hash

test_user = User(email='test@testmail.com')
test_file = File(id = 0,
                user_id = 0,
                xnat_subj_id = 'Subj-S1-2022-08-28-16-26-11-342',
                xnat_experiment_id = 'Exp-2022-08-28-16-26-31-658',
                xnat_scan_id = 'Scan_0')

test_app_configuration = {
        'TESTING': True,
        'XNAT_SERVER':"http://e81151.berlin.ptb.de:8080/xnat",
        'XNAT_ADMIN_USER':"admin",
        'XNAT_ADMIN_PW':"e81151",
        'XNAT_PROJECT_ID_VAULT':"OPENHEART",
        'XNAT_PROJECT_ID_OPEN':"Open"
    }

@pytest.fixture(scope='module')
def app():
    db_fd, db_path = tempfile.mkstemp()
    test_app_configuration['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app = create_app(test_app_configuration)

    with app.app_context():
        db.session.add(test_user)
        db.session.add(test_file)
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