"""P3.2: semantic search (RAG) — chunking, indexing, search, RAG prompt context.

Ollama is never contacted in tests: `_embed_texts` is monkeypatched with a
deterministic fake (word-averaged 8-dim vectors) so chunk ranking has meaning
and runs offline.
"""
import numpy as np

import main

# --- helpers -----------------------------------------------------------------


def _fake_emb(text: str) -> list[float]:
    """Deterministic toy embedding: avg one-hot of content words, dim 8.

    Shared substrings → shared vector components → cosine > 0, which is enough
    to verify ranking order without a real model. crc32 keeps the bucketing
    stable within a process (built-in hash() is salted per process).
    """
    import zlib
    v = np.zeros(8, dtype=np.float64)
    tokens = text.lower().split()
    for t in tokens:
        v[zlib.crc32(t.encode("utf-8")) % 8] += 1.0
    n = np.linalg.norm(v) or 1.0
    return (v / n).tolist()


class _FakeEmbedder:
    def __init__(self):
        self.calls = []

    async def __call__(self, texts):
        self.calls.append(len(texts))
        return [_fake_emb(t) for t in texts]


import pytest


@pytest.fixture
def fake_embedder(monkeypatch):
    emb = _FakeEmbedder()
    monkeypatch.setattr(main, "_embed_texts", emb)
    return emb


def _import(client, name, files):
    r = client.post("/api/projects", json={"name": name,
                                           "files": [{"path": p, "content": c}
                                                     for p, c in files.items()]})
    assert r.status_code == 200, r.text
    return r.json()


# --- pure functions ----------------------------------------------------------


def test_split_chunks_small_file_single_chunk():
    out = main._split_chunks("a = 1\nb = 2\n")
    assert len(out) == 1
    assert out[0][0] == 1
    assert "a = 1" in out[0][1]


def test_split_chunks_large_file_overlapping():
    text = "\n".join(f"line_{i} = {i}" for i in range(4000))
    out = main._split_chunks(text)
    assert len(out) >= 2
    # Every non-empty line survives chunking (no content dropped at seams).
    joined = "".join(c for _sl, c in out)
    for i in (0, 1000, 2500, 3999):
        assert f"line_{i}" in joined
    # start_line is a sane positive int
    assert all(sl >= 1 for sl, _c in out)


def test_split_chunks_blank_only_empties():
    assert main._split_chunks("\n\n\n") == []


def test_cosine_identical_is_one_and_zero_norm_safe():
    v = np.random.RandomState(0).randn(8).astype(np.float32)
    assert main._cosine(v, v.reshape(1, -1))[0] == pytest.approx(1.0, abs=1e-6)
    assert list(main._cosine(np.zeros(8), v.reshape(1, -1))) == [0.0]


# --- index + search endpoints ------------------------------------------------


def test_import_builds_index_and_search_ranks_relevant(client, fresh_projects, fake_embedder):
    proj_a = _import(client, "rag-a", {
        "billing/invoice.py": "def charge_subscription(card, plan):\n    total = plan.price * 12\n    invoice = create_invoice(card, total)\n    return invoice\n" * 3,
        "ui/theme.ts": "export const dark: Record<string, string> = {\n  bg: '#111827',\n  fg: '#f9fafb',\n};\n" * 8,
    })["id"]
    # import must store embeddings (fake embedder did the work)
    rows = main.database.get_db().execute(
        "SELECT COUNT(*) FROM embeddings WHERE project_id=?", (proj_a,)).fetchone()[0]
    assert rows >= 2  # one chunk per file minimum

    # Query about billing → the invoice chunk ranks #1 for that project
    fake_embedder.calls.clear()
    r = client.get(f"/api/projects/{proj_a}/search", params={"q": "charge subscription invoice billing plan"})
    assert r.status_code == 200
    data = r.json()
    assert data["results"], "search must return at least one result"
    top = data["results"][0]
    assert top["file"] == "billing/invoice.py"
    assert top["score"] >= data["results"][-1]["score"]
    assert top["start_line"] >= 1 and top["end_line"] >= top["start_line"]
    assert isinstance(top["snippet"], str) and top["snippet"]
    client.delete(f"/api/projects/{proj_a}")


def test_import_succeeds_even_when_embedder_down(client, fresh_projects, monkeypatch):
    async def boom(texts):
        raise main.HTTPException(status_code=502, detail="embedding model down")
    monkeypatch.setattr(main, "_embed_texts", boom)
    r = client.post("/api/projects", json={"name": "rag-down",
                                           "files": [{"path": "a.py", "content": "x = 1"}]})
    # Import is 200 (best-effort index); only the search reflects the gap.
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = client.get(f"/api/projects/{pid}/search", params={"q": "x"})
    assert r.status_code == 200 and r.json()["results"] == []
    # Manual (re)build of the index also fails with a clean 502, not a crash.
    r2 = client.post(f"/api/projects/{pid}/index")
    assert r2.status_code == 502
    client.delete(f"/api/projects/{pid}")


def test_index_endpoint_rebuilds_idempotently(client, fresh_projects, fake_embedder):
    pid = _import(client, "rag-rebuild", {
        "m.py": "def f():\n    return 41 + 1\n"})["id"]
    n1 = main.database.get_db().execute(
        "SELECT COUNT(*) FROM embeddings").fetchone()[0]

    r = client.post(f"/api/projects/{pid}/index")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["files_indexed"] == 1 and body["chunks"] >= 1
    n2 = main.database.get_db().execute(
        "SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert n2 == n1  # replaced in place, not duplicated
    client.delete(f"/api/projects/{pid}")


def test_search_validation_and_404(client, fresh_projects):
    # unknown project
    assert client.get("/api/projects/nope/search", params={"q": "x"}).status_code == 404
    assert client.post("/api/projects/nope/index").status_code == 404

    r = _import(client, "rag-422", {"a.py": "y = 2\n"})
    # empty query → 422
    assert client.get(f"/api/projects/{r['id']}/search", params={"q": "   "}).status_code == 422
    client.delete(f"/api/projects/{r['id']}")


# --- RAG into the prompt -----------------------------------------------------


@pytest.mark.asyncio
async def test_rag_context_for_question_builds_labelled_block(client, fresh_projects, fake_embedder):
    import asyncio
    pid = _import(client, "rag-q", {
        "math/adder.py": "def add(a, b):\n    '''Return the sum of a and b.'''\n    return a + b\n" * 2,
        "math/subtract.py": "def sub(a, b):\n    return a - b\n",
    })["id"]
    header, count = await main._rag_context_for_question([pid], "how does add sum the two inputs")
    assert count >= 1
    assert "math/adder.py" in header
    assert "def add" in header  # code, not just the label
    # Unknown project ids are skipped, not fatal.
    h2, c2 = await main._rag_context_for_question(["nope", pid], "how does add work")
    assert c2 >= 1 and "math/adder.py" in h2
    # No embeddings at all → empty block
    main.database.embeddings_clear(pid)
    h3, c3 = await main._rag_context_for_question([pid], "q")
    assert h3 == "" and c3 == 0
    client.delete(f"/api/projects/{pid}")


@pytest.mark.asyncio
async def test_stream_chat_project_ids_rag_prefix(client, fresh_projects, fake_embedder, monkeypatch):
    """project_ids on /stream/api/chat must flow into the Ollama prompt."""
    pid = _import(client, "rag-stream", {
        "svc/handler.py": "def respond(request):\n    status = 200\n    return {'status': status}\n",
    })["id"]

    captured: dict = {}

    async def fake_stream(prompt, model_name, prefix_context=""):
        captured["prefix"] = prefix_context
        captured["prompt"] = prompt
        yield "data: {\"text\": \"ok\"}\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(main, "stream_ollama", fake_stream)
    r = client.get("/stream/api/chat", params={
        "message": "what status does respond return?",
        "model_name": "no-such-model-xyz",
        "project_ids": pid,
    })
    assert r.status_code == 200
    assert "svc/handler.py" in captured["prefix"]
    assert "def respond" in captured["prefix"]
    # classic file_ids flow still works and stays RAG-free
    captured.clear()
    r = client.get("/stream/api/chat", params={
        "message": "hi", "model_name": "m", "file_ids": "no-such-id",
    })
    assert r.status_code == 200
    assert captured["prefix"] == ""
    client.delete(f"/api/projects/{pid}")


def test_api_chat_accepts_project_ids_field(client, fresh_projects, fake_embedder):
    """/api/chat (non-streaming) exposes project_ids and threads the prefix in."""
    pid = _import(client, "rag-api", {
        "core/engine.py": "def start_engine(mode):\n    if mode == 'fast':\n        spin = 100\n    return spin\n",
    })["id"]

    captured: dict = {}

    async def fake_generate(prompt, model_name, prefix_context=""):
        captured["prefix"] = prefix_context
        captured["prompt"] = prompt
        return "fast → 100"

    old = main.call_ollama
    main.call_ollama = fake_generate
    try:
        r = client.post("/api/chat", json={
            "message": "what does start_engine return in fast mode?",
            "model_name": "no-such-model-xyz",
            "project_ids": [pid],
        })
    finally:
        main.call_ollama = old
    assert r.status_code == 200, r.text
    assert "core/engine.py" in captured["prefix"]
    assert "def start_engine" in captured["prefix"]
    assert "fast → 100" in r.json()["content"]  # the (fake) model ran
    client.delete(f"/api/projects/{pid}")
