import pytest

from klubfit.db import SEED_DB, connect, reset_db
from klubfit.seed import build_seed_db


@pytest.fixture(scope="session", autouse=True)
def seed_db():
    build_seed_db(SEED_DB)
    return SEED_DB


@pytest.fixture
def db(tmp_path):
    return reset_db(tmp_path / "run.sqlite")


@pytest.fixture
def conn(db):
    c = connect(db)
    yield c
    c.close()


def client_id(conn, email):
    return conn.execute("SELECT id FROM clients WHERE email = ?", (email,)).fetchone()["id"]
