#!/usr/bin/env python3
"""P6.2 MCP (Model Context Protocol) server for the CodeForge code index.

Stdio transport, newline-delimited JSON-RPC 2.0 — the exact subset Claude
Desktop / any MCP client needs: initialize, tools/list, tools/call. Reads the
same SQLite store as the backend; no FastAPI, no network, never touches Ollama.

Usage:
    python src/backend/mcp_server.py --project <id-or-name> [--db PATH]

Tools exposed (plan P6.2): list_files, search_symbols, get_definition,
find_references, read_file, get_file_outline.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class UsageError(Exception):
    pass


def _resolve_project(database, ref: str) -> dict:
    for p in database.project_list():
        if p["id"] == ref or p["name"] == ref:
            return p
    raise UsageError(f"no project with id or name {ref!r}")


TOOLS = [
    {"name": "list_files",
     "description": "List every indexed file in the project (path, size, lines).",
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "search_symbols",
     "description": "Search function/class/method symbols by name substring. "
                    "Optional kind: function|method|class|async function|interface|type|enum.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "kind": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_definition",
     "description": "Return each definition of a symbol name: file, line range, signature.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string"}}, "required": ["name"]}},
    {"name": "find_references",
     "description": "Return definitions plus every use/call/import site of a symbol name.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string"}}, "required": ["name"]}},
    {"name": "read_file",
     "description": "Read an indexed file's content; optional 1-based line window.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string"},
         "start_line": {"type": "integer"},
         "end_line": {"type": "integer"}}, "required": ["path"]}},
    {"name": "get_file_outline",
     "description": "Symbols in one file with line ranges, in source order.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string"}}, "required": ["path"]}},
]


def make_handlers(database, project_id: str):
    def read_file(path, start_line=None, end_line=None):
        row = database.project_file_get_by_path(project_id, path)
        if row is None:
            raise UsageError(f"file {path!r} not in project")
        content = row["content"] or ""
        lines = content.splitlines()
        if start_line or end_line:
            a = max(1, start_line or 1)
            b = min(len(lines), end_line or len(lines))
            lines = lines[a - 1:b]
        return {"path": path, "content": "\n".join(lines)}

    def dispatch(name, args):
        if name == "list_files":
            return {"files": database.project_files_list(project_id)}
        if name == "search_symbols":
            return {"symbols": database.symbol_search(
                project_id, q=args.get("query"), kind=args.get("kind"))}
        if name == "get_definition":
            defs = database.symbol_references(project_id, args["name"])["definitions"]
            return {"definitions": defs}
        if name == "find_references":
            return database.symbol_references(project_id, args["name"])
        if name == "read_file":
            return read_file(args["path"], args.get("start_line"), args.get("end_line"))
        if name == "get_file_outline":
            return {"path": args["path"],
                    "symbols": database.file_outline(project_id, args["path"])}
        raise UsageError(f"unknown tool {name!r}")

    return dispatch


def serve(database, project_id: str, stdin=None, stdout=None):
    """Newline-delimited JSON-RPC 2.0 loop. Returns when stdin closes."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    dispatch = make_handlers(database, project_id)

    def send(msg):
        stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        stdout.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            send({"jsonrpc": "2.0", "id": None,
                  "error": {"code": -32700, "message": "parse error"}})
            continue
        method, rid = req.get("method"), req.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "codeforge-index", "version": "1.0"}}})
        elif method in ("notifications/initialized", "initialized"):
            pass  # notification — no response
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = req.get("params") or {}
            try:
                out = dispatch(params.get("name"), params.get("arguments") or {})
                send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text",
                                 "text": json.dumps(out, ensure_ascii=False)}],
                    "isError": False}})
            except UsageError as e:
                # tool-level errors are results (isError), not protocol errors
                send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True}})
            except KeyError as e:
                send({"jsonrpc": "2.0", "id": rid, "error":
                      {"code": -32602, "message": f"missing argument {e}"}})
        elif rid is not None:
            send({"jsonrpc": "2.0", "id": rid, "error":
                  {"code": -32601, "message": f"method not found: {method}"}})


def main(argv=None):
    ap = argparse.ArgumentParser(description="CodeForge MCP code-index server")
    ap.add_argument("--project", required=True, help="project id or name")
    ap.add_argument("--db", default=None, help="sqlite path (default: backend's)")
    args = ap.parse_args(argv)
    if args.db:
        os.environ["CODEFORGE_DB"] = args.db  # must be set before database import
    import database
    try:
        proj = _resolve_project(database, args.project)
    except UsageError as e:
        print(f"codeforge-mcp: {e}", file=sys.stderr)
        return 2
    serve(database, proj["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
