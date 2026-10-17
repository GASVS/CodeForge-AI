"""P3.4: settings REST API — GET/PUT /api/settings + /api/ollama/status.

Ollama is never contacted: the status endpoint is exercised by monkeypatching
httpx.AsyncClient so both the up and down paths run offline.
"""
from fastapi.testclient import TestClient

import main
import database


def test_settings_defaults(client):
    database.get_db().execute("DELETE FROM settings")
    database.get_db().commit()
    r = client.get("/api/settings")
    assert r.status_code == 200
    d = r.json()
    assert d["temperature"] == 0.7
    assert isinstance(d["system_prompt"], str) and d["system_prompt"]


def test_settings_roundtrip_temperature(client):
    r = client.put("/api/settings", json={"temperature": 0.3})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["updated"] == ["temperature"]
    assert d["temperature"] == 0.3
    # persisted in the DB and read back through the Ollama path's helper
    assert abs(main._temperature() - 0.3) < 1e-9


def test_settings_clamps_temperature(client):
    for raw, expected in [(1.5, 1.0), (-0.5, 0.0), (0.5, 0.5)]:
        r = client.put("/api/settings", json={"temperature": raw})
        assert r.status_code == 200
        assert r.json()["temperature"] == expected


def test_settings_nan_temperature(client):
    # NaN survives JSON round-trip with allow_nan (FastAPI default)
    r = client.put("/api/settings", json={"temperature": float("nan")})
    assert r.status_code == 200
    assert r.json()["temperature"] == 0.7


def test_settings_system_prompt_roundtrip(client):
    custom = "Be terse and cite line numbers."
    r = client.put("/api/settings", json={"system_prompt": custom})
    assert r.status_code == 200
    assert r.json()["system_prompt"] == custom
    # the reader used by the Ollama call path now returns it
    assert main._system_prompt() == custom


def test_settings_system_prompt_too_long(client):
    r = client.put("/api/settings", json={"system_prompt": "x" * 4001})
    assert r.status_code == 422
    assert "too long" in r.json()["detail"]


def test_settings_partial_update(client):
    # Only temperature given → system_prompt should not be clobbered
    client.put("/api/settings", json={"system_prompt": "keep me"})
    r = client.put("/api/settings", json={"temperature": 0.1})
    assert r.status_code == 200
    body = r.json()
    assert body["system_prompt"] == "keep me"
    assert body["temperature"] == 0.1
    assert body["updated"] == ["temperature"]


def test_settings_noop_update(client):
    # Empty body → 200 ok, nothing persisted/clobbered
    client.put("/api/settings", json={"system_prompt": "keep me"})
    r = client.put("/api/settings", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["updated"] == []
    assert body["system_prompt"] == "keep me"


def _patch_ollama(monkeypatch, fail: bool):
    import httpx

    class FakeResp:
        def json(self):
            return {"models": [{"name": "a"}, {"name": "b"}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            if fail:
                raise httpx.ConnectError("refused")
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)


def test_ollama_status_up(client, monkeypatch):
    _patch_ollama(monkeypatch, fail=False)
    r = client.get("/api/ollama/status")
    assert r.status_code == 200
    d = r.json()
    assert d["up"] is True
    assert d["model_count"] == 2
    assert set(d["models"]) == {"a", "b"}


def test_ollama_status_down(client, monkeypatch):
    _patch_ollama(monkeypatch, fail=True)
    r = client.get("/api/ollama/status")
    assert r.status_code == 200  # 200 with up:false so the UI can render a badge
    d = r.json()
    assert d["up"] is False
    assert d["model_count"] == 0
    assert "refused" in d["error"]
