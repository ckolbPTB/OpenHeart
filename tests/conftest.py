from pathlib import Path

import os
import tempfile

import pytest
from openheart import create_app
from openheart.db import get_db, init_db


fpath_dummy_data = Path(__file__).resolve().parent / 'data.sql'
with fpath_dummy_data.open('rb') as f:
    _data_sql = f.read().decode('utf8')


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()

    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
    })

    with app.app_context():
        init_db()
        get_db().executescript(_data_sql)

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()