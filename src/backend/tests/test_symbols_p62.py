"""P6.2 — symbol table + reference index (symbols.py extractors, DB layer,
REST endpoints, MCP server). Ollama is never contacted: fake_embedder from
test_rag_p32 keeps project import deterministic without a running model."""

import difflib

import pytest

import database
import mcp_server
from symbols import extract

from test_rag_p32 import fake_embedder  # noqa: F401  (registers the fixture)

PY_A = """import os
from collections import OrderedDict


class Store:
    def __init__(self):
        self.items = OrderedDict()

    def put(self, key, value):
        self.items[key] = value
        return OrderedDict()

    def load(self, key):
        path = os.path.join("/tmp", key)
        return self.items.get(key), path


def helper(x):
    return x + 1


def main():
    return helper(2)
"""

PY_B = """import a


def run():
    return a.helper(3)
"""

TS_A = """export interface Readable {
  read(n: number): string
}

export type Mode = 'a' | 'b'

export function formatBytes(n: number): string {
  return String(n)
}

const run = () => {
  formatBytes(1)
}
"""

TSX_A = """import React from 'react'

function App() {
  return <div>hi</div>
}

export default App
"""

GO_A = """package main

import (
	"fmt"
	"os"
)

type Foo struct{}

func (f *Foo) Bar() int {
	return 42
}

func main() {
	fmt.Println(os.Args[0])
}
"""


# ------------------------------------------------------------- extractors ----

def test_extract_python_defs_and_calls():
    syms, refs = extract("a.py", PY_A)
    by_name = {s["name"]: s for s in syms}
    assert {"Store", "helper", "main"} <= set(by_name)
    assert by_name["Store"]["kind"] == "class"
    # methods get parent scope + method kind (ast-based, exact ranges)
    put = by_name["put"]
    assert put["kind"] == "method" and put["parent"] == "Store"
    assert put["start_line"] <= put["end_line"]

    calls = {(r["from_symbol"], r["to_name"]) for r in refs if r["kind"] == "call"}
    assert ("Store.__init__", "OrderedDict") in calls or ("Store.put", "OrderedDict") in calls
    assert ("Store.load", "join") in calls  # os.path.join(...) -> attr call

    imports = {r["to_name"] for r in refs if r["kind"] == "import"}
    assert {"os", "collections.OrderedDict"} <= imports


def test_extract_typescript_kinds():
    syms, _ = extract("src/a.ts", TS_A)
    kinds = {s["name"]: s["kind"] for s in syms}
    assert kinds.get("Readable") == "interface"
    assert kinds.get("formatBytes") == "function"
    assert kinds.get("Mode") == "type"


def test_extract_tsx_component():
    syms, _ = extract("src/App.tsx", TSX_A)
    names = {s["name"] for s in syms}
    assert "App" in names  # function App() — component detection is P6.4's job


def test_extract_go_method_and_import_block():
    syms, refs = extract("cmd/main.go", GO_A)
    by_name = {s["name"]: s for s in syms}
    assert by_name["Bar"]["kind"] == "method" and by_name["Bar"]["parent"] == "Foo"
    assert by_name["main"]["kind"] == "function"
    imports = {r["to_name"] for r in refs if r["kind"] == "import"}
    assert {"fmt", "os"} <= imports


def test_extract_unsupported_and_broken_are_empty():
    assert extract("README.md", "# hello") == ([], [])
    syms, refs = extract("broken.py", "def ([:\n  ???")   # never raises
    assert syms == [] and refs == []


# ------------------------------------------------------------- endpoints -----

@pytest.fixture()
def sym_project(client, fresh_projects, fake_embedder):  # noqa: F811
    r = client.post("/api/projects", json={
        "name": "syms-demo",
        "files": [{"path": "a.py", "content": PY_A},
                  {"path": "b.py", "content": PY_B}]})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_index_symbols_endpoint(client, sym_project):
    stats = client.post(f"/api/projects/{sym_project}/index-symbols").json()
    assert stats["files_indexed"] == 2 and stats["symbols"] >= 6
    # idempotent rebuild keeps counts stable
    again = client.post(f"/api/projects/{sym_project}/index-symbols").json()
    assert again == stats


def test_outline_endpoint(client, sym_project):
    r = client.get(f"/api/projects/{sym_project}/outline", params={"path": "a.py"})
    names = {s["name"] for s in r.json()["symbols"]}
    assert {"Store", "put", "helper", "main"} <= names


def test_find_references_endpoint(client, sym_project):
    r = client.get(f"/api/projects/{sym_project}/symbols/helper/references")
    assert r.status_code == 200, r.text
    data = r.json()

    defs = {(d["file_ref"], d["kind"]) for d in data["definitions"]}
    assert defs == {("a.py", "function")}

    sites = {(x["from_file"], x["kind"]) for x in data["references"]}
    # a.py main->helper call AND b.py run->a.helper call
    assert ("a.py", "call") in sites and ("b.py", "call") in sites

    missing = client.get(f"/api/projects/{sym_project}/symbols/nope/references")
    assert missing.json()["definitions"] == []


def test_symbol_search_endpoint(client, sym_project):
    r = client.get(f"/api/projects/{sym_project}/symbols",
                   params={"q": "hel", "kind": "function"})
    hits = {h["file_ref"] for h in r.json()["symbols"]}
    assert hits == {"a.py"}

    r2 = client.get(f"/api/projects/{sym_project}/symbols", params={"q": "zzz-nope"})
    assert r2.json()["symbols"] == []


def test_incremental_reindex_after_patch(client, sym_project):
    new_b = "def run():\n    return 42\n"
    diff = "".join(difflib.unified_diff(
        PY_B.splitlines(keepends=True), new_b.splitlines(keepends=True),
        fromfile="a/b.py", tofile="b/b.py"))
    r = client.post(f"/api/projects/{sym_project}/apply-patch",
                    json={"patch": diff})
    assert r.status_code == 200, r.text

    # b.py's call site of helper is gone; a.py's definition remains
    refs = client.get(f"/api/projects/{sym_project}/symbols/helper/references").json()
    files = {x["from_file"] for x in refs["references"]}
    assert "b.py" not in files and "a.py" in files


# ------------------------------------------------------------------- MCP -----

def test_mcp_dispatch_tools(sym_project):  # noqa: F811
    dispatch = mcp_server.make_handlers(database, sym_project)

    defs = dispatch("get_definition", {"name": "helper"})["definitions"]
    assert {d["file_ref"] for d in defs} == {"a.py"}

    both = dispatch("find_references", {"name": "helper"})
    assert any(r["from_file"] == "b.py" and r["kind"] == "call"
               for r in both["references"])

    hits = dispatch("search_symbols", {"query": "Store"})
    assert hits["symbols"] and hits["symbols"][0]["name"] == "Store"

    outline = dispatch("get_file_outline", {"path": "a.py"})
    assert any(s["kind"] == "class" for s in outline["symbols"])


def test_mcp_read_file_window(sym_project):  # noqa: F811
    dispatch = mcp_server.make_handlers(database, sym_project)
    out = dispatch("read_file", {"path": "a.py", "start_line": 18, "end_line": 19})
    assert out["content"] == "def helper(x):\n    return x + 1"

    with pytest.raises(mcp_server.UsageError):
        dispatch("read_file", {"path": "nope.py"})


def test_mcp_jsonrpc_round_trip(sym_project):  # noqa: F811
    import io
    reqs = ('{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
            '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":'
            '{"name":"get_definition","arguments":{"name":"helper"}}}\n')
    out = io.StringIO()
    mcp_server.serve(database, sym_project, stdin=io.StringIO(reqs), stdout=out)
    replies = [__import__("json").loads(l) for l in out.getvalue().splitlines()]
    assert replies[0]["result"]["capabilities"] == {"tools": {}}
    tool_names = {t["name"] for t in replies[1]["result"]["tools"]}
    assert {"search_symbols", "find_references", "read_file"} <= tool_names
    content = replies[2]["result"]["content"][0]["text"]
    assert "a.py" in content
