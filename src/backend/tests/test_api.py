"""API tests: health, models failure path, chats CRUD + export, uploads."""
import json

import httpx


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


class _raising_client:
    """Duck-typed httpx.AsyncClient that fails at connect — Ollama 'down'."""
    async def __aenter__(self):
        raise httpx.ConnectError("ollama unreachable")

    async def __aexit__(self, *a):
        pass


def test_models_503_when_ollama_down(client, monkeypatch):
    import main

    monkeypatch.setattr(main.httpx, "AsyncClient", lambda *a, **k: _raising_client())
    r = client.get("/api/models")
    assert r.status_code == 503
    assert "Cannot fetch models" in r.json()["detail"]


def test_chats_crud_roundtrip(client, fresh_chats):
    # create (auto-titled from the first user message)
    r = client.post("/api/chats", json={
        "model": "qwen3.5:9b",
        "messages": [{"role": "user", "content": "hello world"}],
    })
    assert r.status_code == 200, r.text
    chat = r.json()
    assert chat["title"] == "hello world"
    chat_id = chat["id"]

    # list
    r = client.get("/api/chats")
    assert r.status_code == 200
    assert any(c["id"] == chat_id for c in r.json()["chats"])

    # get
    r = client.get(f"/api/chats/{chat_id}")
    assert r.status_code == 200
    assert r.json()["messages"][0]["content"] == "hello world"

    # update (append assistant answer, as the app does after each turn)
    r = client.put(f"/api/chats/{chat_id}", json={"messages": [
        {"role": "user", "content": "hello world"},
        {"role": "assistant", "content": "hi!"},
    ]})
    assert r.status_code == 200
    assert len(r.json()["messages"]) == 2

    # export markdown
    r = client.get(f"/api/chats/{chat_id}/export", params={"format": "md"})
    assert r.status_code == 200
    body = r.text
    assert "# hello world" in body
    assert "hello world" in body and "hi!" in body
    assert "You" in body and "Assistant" in body
    assert "attachment" in r.headers.get("content-disposition", "").lower()

    # export json
    r = client.get(f"/api/chats/{chat_id}/export", params={"format": "json"})
    assert r.status_code == 200
    payload = json.loads(r.text)
    assert payload["id"] == chat_id

    # delete -> gone -> 404 afterwards
    r = client.delete(f"/api/chats/{chat_id}")
    assert r.status_code == 200
    assert client.get(f"/api/chats/{chat_id}").status_code == 404
    assert client.delete(f"/api/chats/{chat_id}").status_code == 404


def test_chats_404_on_missing(client, fresh_chats):
    assert client.get("/api/chats/nope").status_code == 404
    assert client.get("/api/chats/nope/export").status_code == 404


def test_upload_small_then_list_get_delete(client):
    r = client.post("/api/upload", files=[("files", ("hello.py", b"print(1)", "text/x-python"))])
    assert r.status_code == 200, r.text
    fid = r.json()["files"][0]["id"]

    r = client.get("/api/files")
    assert any(f["id"] == fid for f in r.json()["files"])

    r = client.get(f"/api/files/{fid}")
    assert r.json()["content"] == "print(1)"

    r = client.delete(f"/api/files/{fid}")
    assert r.status_code == 200
    assert client.get(f"/api/files/{fid}").status_code == 404


def test_upload_413_over_2mb(client):
    big = b"x" * (2 * 1024 * 1024 + 1024)
    r = client.post("/api/upload", files=[("files", ("big.py", big, "text/x-python"))])
    assert r.status_code == 413


def test_upload_413_too_many_files(client):
    files = [("files", (f"f{i}.txt", b"a", "text/plain")) for i in range(11)]
    r = client.post("/api/upload", files=files)
    assert r.status_code == 413


def test_upload_415_disallowed_extension(client):
    r = client.post("/api/upload", files=[("files", ("doc.pdf", b"%PDF", "application/pdf"))])
    assert r.status_code == 415


def test_upload_415_binary_sniff(client):
    r = client.post("/api/upload", files=[("files", ("fake.txt", b"\x00\x01\x02bin", "text/plain"))])
    assert r.status_code == 415


def test_stream_bad_model_error_frame(client, fresh_chats):
    """A bad model must yield an SSE `error` frame + [DONE], not a silent hang."""
    r = client.get("/stream/api/chat", params={
        "message": "hi", "model_name": "no-such-model-xyz"})
    # The SSE transport opens fine; the error travels inside the stream body.
    assert r.status_code == 200
    body = r.text
    assert "[DONE]" in body
    assert "not available in Ollama" in body or "connect" in body.lower()
