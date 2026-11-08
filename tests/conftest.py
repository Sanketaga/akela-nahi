import os
import sys
import tempfile
from pathlib import Path

# Isolated data folder and no real keys, set BEFORE the app is imported.
os.environ["AKELA_DATA_DIR"] = tempfile.mkdtemp(prefix="akela_test_")
os.environ["GNANI_API_KEY"] = ""
os.environ["DASHBOARD_PASSWORD"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, main, scheduler  # noqa: E402


async def _no_scheduler(*_a, **_k):
    return None


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(scheduler, "run_forever", _no_scheduler)
    if db.config.DB_PATH.exists():
        db.config.DB_PATH.unlink()
    with TestClient(main.app) as c:
        yield c


ELDER = {
    "name": "Sharma ji", "family_label": "Papa", "language": "hi-IN", "voice": "Chetana",
    "call_time": "08:30", "family_name": "Rahul", "family_relation": "son", "family_language": "en-IN",
    "medicines": "BP tablet", "share_transcript": True, "use_family_voice": False, "active": False,
}


@pytest.fixture()
def elder(client):
    return client.post("/api/elders", json=ELDER).json()
