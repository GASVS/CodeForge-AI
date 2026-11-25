"""P6.1: per-message model persistence + skills seeding from SKILL.md files."""
import os

import database


def test_seed_skills_from_dir(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    name = "demo-skill-" + os.urandom(4).hex()  # avoid cross-test collisions
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: A demo\n---\n\nBody text here.\n",
        encoding="utf-8",
    )

    assert database.skill_get(name) is None
    seeded = database.seed_skills_from_dir(str(tmp_path))
    assert seeded == 1
    skill = database.skill_get(name)
    assert skill is not None
    assert "Body text here." in skill["body"]
    # frontmatter must NOT leak into the body
    assert "description:" not in skill["body"]

    # insert-only: a second seed never overwrites user edits
    with database._lock:
        conn = database.get_db()
        conn.execute("UPDATE skills SET body=? WHERE name=?", ("user edited", name))
        conn.commit()
    assert database.seed_skills_from_dir(str(tmp_path)) == 0
    assert database.skill_get(name)["body"] == "user edited"


def test_repo_skills_seed_on_startup(client):
    # lifespan seeds the bundled skills/ folder (react-theme-manage has SKILL.md)
    r = client.get("/api/skills")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["skills"]]
    assert "react-theme-manage" in names


def test_update_conversation_tracks_last_used_model(fresh_chats):
    chat = database.create_conversation(messages=[{"role": "user", "content": "hi"}])
    assert database.update_conversation(chat["id"], model="model-b")["model"] == "model-b"
    # None keeps the previous value; a new reply updates it again
    assert database.update_conversation(chat["id"], title="t")["model"] == "model-b"
    assert database.update_conversation(
        chat["id"], messages=[{"role": "user", "content": "x"}], model="model-c"
    )["model"] == "model-c"


def test_chat_api_persists_per_message_model(client, fresh_chats):
    r = client.post("/api/chats", json={"title": "P6.1"})
    assert r.status_code == 200
    chat_id = r.json()["id"]

    msgs = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1", "model": "llama-3.1:8b"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2", "model": "qwen3.5-9b-64k:latest"},
    ]
    r = client.put(f"/api/chats/{chat_id}", json={"messages": msgs, "model": "qwen3.5-9b-64k:latest"})
    assert r.status_code == 200

    chat = client.get(f"/api/chats/{chat_id}").json()
    # per-message model survives round-trip (alternating models in one chat)
    assert [m.get("model") for m in chat["messages"]] == [None, "llama-3.1:8b", None, "qwen3.5-9b-64k:latest"]
    # conversations.model = last used
    assert chat["model"] == "qwen3.5-9b-64k:latest"
