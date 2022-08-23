import pytest
from flask import g, session

from openheart.db import get_db


def test_register(client, app):

    '''Test to check whether registered user ends up in database.'''
    assert client.get('/auth/register').status_code == 200

    response = client.post(
        '/auth/register', data={'email':'a@b.de', 'password':'a'}
    )

    assert response.headers["Location"] == "/auth/login"

    with app.app_context():
        assert get_db().execute(
            "SELECT * FROM user WHERE email = 'a@b.de'",
        ).fetchone() is not None



@pytest.mark.parametrize(('email', 'password', 'message'),(
    ('', '', b'Email is required.'),
    ('valid@email.com', '', b'Password is required.'),
    ('test@testmail.com', 'test', b'already registered.'),
))
def test_register_validate_input(app, client, email, password, message):
    response = client.post(
        '/auth/register', data={'email':email, 'password':password}
    )

    assert message in response.data
