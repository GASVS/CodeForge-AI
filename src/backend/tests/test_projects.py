"""P3.1: project import endpoints (JSON + zip), file access, settings store."""
import io
import zipfile


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_project_json_create_list_get_delete(client, fresh_projects):
    r = client.post("/api/projects", json={
        "name": "demo-app",
        "files": [
            {"path": "src/greet.py", "content": "def greet(x):\n    return 'Hello ' + x\n"},
            {"path": "src/util.ts", "content": "export const ok = true;\n"},
        ],
    })
    assert r.status_code == 200, r.text
    proj = r.json()
    assert proj["name"] == "demo-app"
    assert proj["file_count"] == 2
    assert proj["total_bytes"] > 0
    pid = proj["id"]
    paths = sorted(f["path"] for f in proj["files"])
    assert paths == ["src/greet.py", "src/util.ts"]

    # list (summaries only)
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert any(p["id"] == pid and p["name"] == "demo-app" for p in r.json()["projects"])

    # get by id (with files)
    r = client.get(f"/api/projects/{pid}")
    assert r.status_code == 200
    rj = r.json()
    assert rj["name"] == "demo-app" and rj["file_count"] == 2

    # fetch one file by id
    fid = [f for f in rj["files"] if f["path"] == "src/greet.py"][0]["id"]
    r = client.get(f"/api/projects/{pid}/files/{fid}")
    assert r.status_code == 200
    assert "def greet" in r.json()["content"]

    # delete -> 404 afterwards
    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.delete(f"/api/projects/{pid}").status_code == 404


def test_project_404_missing(client, fresh_projects):
    assert client.get("/api/projects/nope").status_code == 404
    assert client.delete("/api/projects/nope").status_code == 404


def test_project_file_404_wrong_project(client, fresh_projects):
    r = client.post("/api/projects", json={
        "name": "p1", "files": [{"path": "a.py", "content": "x = 1"}]})
    pid = r.json()["id"]
    fid = r.json()["files"][0]["id"]
    # file id is valid but project id is not — must not leak content
    assert client.get(f"/api/projects/other/{fid}").status_code == 404
    assert client.get(f"/api/projects/{pid}/files/nope").status_code == 404
    client.delete(f"/api/projects/{pid}")


def test_project_json_422_bad_input(client, fresh_projects):
    # missing name
    r = client.post("/api/projects", json={"files": [{"path": "a.py", "content": "x"}]})
    assert r.status_code == 422

    # empty files
    r = client.post("/api/projects", json={"name": "n", "files": []})
    assert r.status_code == 422

    # absolute path
    r = client.post("/api/projects", json={
        "name": "n", "files": [{"path": "/etc/passwd", "content": "x"}]})
    assert r.status_code == 422

    # traversal
    r = client.post("/api/projects", json={
        "name": "n", "files": [{"path": "../secret.py", "content": "x"}]})
    assert r.status_code == 422

    # non-string content
    r = client.post("/api/projects", json={
        "name": "n", "files": [{"path": "a.py", "content": 42}]})
    assert r.status_code == 422

    # disallowed extension
    r = client.post("/api/projects", json={
        "name": "n", "files": [{"path": "a.pdf", "content": "x"}]})
    assert r.status_code == 415

    # nothing imported on rejection
    assert client.get("/api/projects").json()["projects"] == []


def test_project_zip_roundtrip_and_skip_dirs(client, fresh_projects):
    zipped = _make_zip({
        "src/app.py": b"def run():\n    return 1\n",
        "src/README.md": b"# app\n",
        "node_modules/pkg/index.js": b"// should be skipped\n",
        "package-lock.json": b"{} /* skipped */\n",
        ".hidden.py": b"# skipped (dotfile)\n",
        "notes.txt": b"keep me\n",
    })
    r = client.post(
        "/api/projects",
        files=[("zip", ("myapp.zip", zipped, "application/zip"))],
    )
    assert r.status_code == 200, r.text
    proj = r.json()
    # name derives from the zip filename
    assert proj["name"] == "myapp"
    paths = sorted(f["path"] for f in proj["files"])
    assert paths == ["notes.txt", "src/README.md", "src/app.py"]
    fid = [f for f in proj["files"] if f["path"] == "notes.txt"][0]["id"]
    assert client.get(f"/api/projects/{proj['id']}/files/{fid}").json()["content"] == "keep me\n"
    client.delete(f"/api/projects/{proj['id']}")


def test_project_zip_bad_and_empty(client, fresh_projects):
    # not a zip
    r = client.post("/api/projects", files=[("zip", ("bad.zip", b"hello", "application/zip"))])
    assert r.status_code == 415

    # valid zip, no importable files
    r = client.post("/api/projects", files=[(
        "zip", ("empty.zip", _make_zip({"node_modules/x.js": b"1", "notes.bin": b"\x00"}),
                "application/zip"))])
    assert r.status_code == 422

    # nothing imported on rejection
    assert client.get("/api/projects").json()["projects"] == []


def test_chat_context_includes_project_file(client, fresh_projects):
    """Project file IDs must work in /api/chat context like upload IDs do."""
    import main

    r = client.post("/api/projects", json={
        "name": "ctx-demo",
        "files": [{"path": "mod/greet.py", "content": "def greet(x):\n    return 'Hello ' + x\n"}],
    })
    assert r.status_code == 200
    pid = r.json()["id"]
    fid = r.json()["files"][0]["id"]

    # add_file_context is the exact helper the chat endpoints call — verify
    # it picks up a project file and labels it with the in-repo path.
    out = main.add_file_context("explain greet", [fid])
    assert "def greet" in out
    assert "ctx-demo/mod/greet.py" in out

    # unknown ids degrade gracefully (message returned unchanged)
    assert main.add_file_context("hi", ["no-such-id"]) == "hi"

    # an upload id still works alongside a project file id
    up = client.post("/api/upload", files=[("files", ("h.py", b"print(1)\n", "text/x-python"))])
    upid = up.json()["files"][0]["id"]
    out2 = main.add_file_context("q", [upid, fid])
    assert "print(1)" in out2 and "def greet" in out2 and "h.py" in out2
    client.delete(f"/api/projects/{pid}")


def test_settings_defaults_and_roundtrip(fresh_projects):
    """Settings key/value store with default application (P3.4 backend)."""
    import database

    # defaults applied when nothing stored
    alls = database.settings_all()
    assert alls["system_prompt"] == database.DEFAULT_SYSTEM_PROMPT
    assert alls["temperature"] == "0.7"

    temperature = database.setting_get("temperature", None)
    assert temperature is None or temperature == "0.7"

    database.setting_set("temperature", "0.2")
    assert database.setting_get("temperature") == "0.2"
    database.setting_set("temperature", "0.9")  # upsert, not duplicate
    assert database.setting_get("temperature") == "0.9"

    database.setting_set("system_prompt", "Be terse.")
    assert database.setting_get("system_prompt") == "Be terse."
    assert database.settings_all()["system_prompt"] == "Be terse."

    # main.py helpers clamp and fall back
    import main
    assert main._temperature() == 0.9
    main._temperature()
    database.setting_set("temperature", "9.9")
    assert main._temperature() == 1.0
    database.setting_set("temperature", "nan")
    assert main._temperature() == 0.7
    database.setting_set("system_prompt", "  ")
    assert main._system_prompt() == ""
    conn = database.get_db()
    assert conn.execute("SELECT COUNT(*) FROM settings WHERE key='temperature'").fetchone()[0] == 1
