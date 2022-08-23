import sqlite3

import pytest
from openheart.db import get_db


def test_get_close_db(app):
    with app.app_context():
        db = get_db()
        assert db == get_db()
    
    with pytest.raises(sqlite3.ProgrammingError) as e:
        db.execute('SELECT 1')

    print(f"The assertion is {e.value}")
    assert 'closed' in str(e.value)
