"""Shared fixtures: isolated temp DB + upload dir, Ollama never touched."""
import os
import sys
import tempfile

import pytest

# Isolate BEFORE main/database import: both pin paths at import time. Point the
# DB at a throwaway dir so the real dev DB (<repo>/private/runtime/codeforge.db)
# is never clobbered by tests; same for the upload dir.
_TMP = tempfile.mkdtemp(prefix="codeforge-test-")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402

database._DB_DIR = os.path.join(_TMP, "db")
os.makedirs(database._DB_DIR, exist_ok=True)
database.DB_PATH = os.path.join(database._DB_DIR, "test_codeforge.db")
database._conn = None  # force a fresh connection to the test DB

import main  # noqa: E402  (after DB isolation)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        # fresh uploads per test so cross-pollination is impossible
        database.get_db().execute("DELETE FROM uploads")
        database.get_db().commit()
        yield c


@pytest.fixture
def fresh_projects():
    conn = database.get_db()
    conn.execute("DELETE FROM project_files")
    conn.execute("DELETE FROM projects")
    conn.execute("DELETE FROM embeddings")
    conn.execute("DELETE FROM settings")
    conn.commit()


@pytest.fixture
def fresh_chats():
    database.get_db().execute("DELETE FROM conversations")
    database.get_db().commit()
