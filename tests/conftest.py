from pathlib import Path

import os
import tempfile

import pytest
from openheart import create_app

from openheart.user import User, db
from werkzeug.security import generate_password_hash

test_user = User(email='test@testmail.com', password=generate_password_hash('test'))


@pytest.fixture(scope='module')
def app():
    db_fd, db_path = tempfile.mkstemp()

    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
    })

    with app.app_context():
        db.session.add(test_user)
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