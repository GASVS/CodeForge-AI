"""P6.2 structural code index — deterministic symbol/reference extraction.

Pure functions, no DB and no network: `extract(path, content)` returns
(symbols, refs) for a file. Python uses the stdlib `ast` (exact line ranges);
JS/TS use a light-tokenizer fallback (regex + brace scanner), which is what
the plan sanctions when tree-sitter grammars are not installed; Go reuses the
same brace scanner for funcs/methods and imports.

Symbol dict: {name, kind, sig, start_line, end_line, parent}
Ref dict:    {from_symbol, to_name, kind, line}   (kind: use|call|import)
"""
import ast
import re

MAX_BYTES = 1_000_000  # skip pathological files; index must stay fast

PY_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}


def _sig(first_line: str) -> str:
    return first_line.strip()[:160]


# ---------------------------------------------------------------- Python ----

def extract_python(content: str):
    tree = ast.parse(content)  # SyntaxError propagates — caller skips file
    lines = content.splitlines()
    symbols, refs = [], []

    def scope_name(prefix, name):
        return f"{prefix}.{name}" if prefix else name

    def collect_refs(node, current):
        """Record Name/Attribute uses and call sites inside one definition."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                fn = child.func
                target = None
                if isinstance(fn, ast.Name):
                    target, kind = fn.id, "call"
                elif isinstance(fn, ast.Attribute):
                    target, kind = fn.attr, "call"
                if target:
                    refs.append({"from_symbol": current, "to_name": target,
                                 "kind": kind, "line": child.lineno})
            elif isinstance(child, (ast.Name, ast.Attribute)) and \
                    isinstance(getattr(child, "ctx", None), ast.Load):
                name = child.attr if isinstance(child, ast.Attribute) else child.id
                refs.append({"from_symbol": current, "to_name": name,
                             "kind": "use", "line": getattr(child, "lineno", 0)})
            elif isinstance(child, ast.Import):
                for a in child.names:
                    refs.append({"from_symbol": current,
                                 "to_name": a.name, "kind": "import",
                                 "line": child.lineno})
            elif isinstance(child, ast.ImportFrom):
                base = child.module or ""
                for a in child.names:
                    refs.append({"from_symbol": current,
                                 "to_name": f"{base}.{a.name}" if base else a.name,
                                 "kind": "import", "line": child.lineno})

    def walk(node, parent):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = ("method" if parent else
                        "async function" if isinstance(child, ast.AsyncFunctionDef)
                        else "function")
                # a plain def inside a class is still a method; async kept in sig
                name = child.name
                symbols.append({
                    "name": name, "kind": kind,
                    "sig": _sig(lines[child.lineno - 1]),
                    "start_line": child.lineno,
                    "end_line": getattr(child, "end_lineno", child.lineno),
                    "parent": parent,
                })
                collect_refs(child, scope_name(parent, name))
                walk(child, scope_name(parent, name))
            elif isinstance(child, ast.ClassDef):
                symbols.append({
                    "name": child.name, "kind": "class",
                    "sig": _sig(lines[child.lineno - 1]),
                    "start_line": child.lineno,
                    "end_line": getattr(child, "end_lineno", child.lineno),
                    "parent": parent,
                })
                collect_refs(child, scope_name(parent, child.name))
                walk(child, scope_name(parent, child.name))
            else:
                walk(child, parent)

    # module-level imports/uses (from_symbol = "")
    for top in tree.body:
        if isinstance(top, (ast.Import, ast.ImportFrom)):
            collect_refs(top, "")
    walk(tree, None)
    return symbols, refs


# ------------------------------------------------------------- JS / TS ------

_JS_PATTERNS = [
    # name, kind, regex (must capture the identifier in group 1)
    ("function", re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)", re.M)),
    ("class", re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.M)),
    ("interface", re.compile(r"^(?:export\s+)?interface\s+(\w+)", re.M)),
    ("type", re.compile(r"^export\s+type\s+(\w+)\s*=", re.M)),
    ("enum", re.compile(r"^(?:export\s+)?(?:const\s+)?enum\s+(\w+)", re.M)),
    ("function", re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::[^=\n]+)?=\s*"
        r"(?:async\s+)?(?:function\b|\([^)]*\)\s*(?::[^={\n]*)?=>|(?:async\s+)?\w+\s*=>)", re.M)),
    # object-literal / class methods: `  foo(args) {` or `  foo: (x) => {`
    ("method", re.compile(r"^\s{2,}(?:(?:public|private|protected|static|async)\s+)*"
                          r"(?!if|for|while|switch|catch|return)(\w+)\s*\([^)]*\)\s*(?::[^={]+)?\{", re.M)),
]

_JS_IMPORT = re.compile(r"^\s*import\s+(?:[\w{},*\s]+\s+from\s+)?['\"]([^'\"]+)['\"]", re.M)
_JS_CALL = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")


def _brace_end(lines, start_idx):
    """Approximate end line of a block starting at 0-based `start_idx` by
    scanning braces outside strings/comments. Returns 1-based end line."""
    depth = 0
    seen_open = False
    for i in range(start_idx, len(lines)):
        line = re.sub(r"//.*$", "", lines[i])  # strip // comments
        line = re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", "", line)
        for ch in line:
            if ch == "{":
                depth += 1
                seen_open = True
            elif ch == "}":
                depth -= 1
                if seen_open and depth <= 0:
                    return i + 1
    return len(lines)


def _call_refs(content, lines, symbols):
    """Call-site refs inside each symbol's line span (JS/TS and Go share this)."""
    refs = []
    def_sites = {(s["name"], s["start_line"]) for s in symbols}
    for sym in symbols:
        seg_start = sum(len(l) + 1 for l in lines[:sym["start_line"] - 1])
        seg_end = sum(len(l) + 1 for l in lines[:sym["end_line"]])
        for m in _JS_CALL.finditer(content, seg_start, min(seg_end, len(content))):
            callee = m.group(1)
            line = sym["start_line"] + content.count("\n", seg_start, m.start())
            if callee == sym["name"] or callee in ("if", "for", "while", "switch",
                                                   "catch", "return", "function",
                                                   "import"):
                continue
            if (callee, line) in def_sites:
                continue  # `run(a) {` — a definition header, not a call site
            refs.append({"from_symbol": sym["name"], "to_name": callee,
                         "kind": "call", "line": line})
    return refs


def extract_js(content: str):
    lines = content.splitlines()
    symbols, refs = [], []

    for kind, pat in _JS_PATTERNS:
        for m in pat.finditer(content):
            name = m.group(1)
            if not name or name in ("from", "return"):
                continue
            start_line = content.count("\n", 0, m.start()) + 1
            end_line = _brace_end(lines, start_line - 1)
            symbols.append({
                "name": name, "kind": kind,
                "sig": _sig(lines[start_line - 1]),
                "start_line": start_line, "end_line": end_line,
                "parent": None,
            })

    # refs: imports + call sites (callers of a symbol = who mentions it).
    # Scan `content` directly — import lines contain no `ident(` except
    # dynamic import(), whose name is filtered below.
    for m in _JS_IMPORT.finditer(content):
        refs.append({"from_symbol": None, "to_name": m.group(1),
                     "kind": "import",
                     "line": content.count("\n", 0, m.start()) + 1})
    refs.extend(_call_refs(content, lines, symbols))
    return symbols, refs


# ------------------------------------------------------------------ Go -----

_GO_FUNC = re.compile(r'^func\s+(?:\(([^)]*)\)\s*)?([A-Za-z_]\w*)\s*\(', re.M)


def extract_go(content: str):
    lines = content.splitlines()
    symbols, refs = [], []
    for m in _GO_FUNC.finditer(content):
        recv, name = m.group(1), m.group(2)
        start_line = content.count("\n", 0, m.start()) + 1
        end_line = _brace_end(lines, start_line - 1)
        symbols.append({
            "name": name, "kind": "method" if recv is not None else "function",
            "sig": _sig(lines[start_line - 1]),
            "start_line": start_line, "end_line": end_line,
            "parent": recv.split()[-1].lstrip("*") if recv else None,
        })
    in_block = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ("):
            in_block = True
            continue
        if in_block:
            if stripped.startswith(")"):
                in_block = False
                continue
            m = re.match(r'^(\w+\s+)?"([^"]+)"', stripped)
            if m:
                refs.append({"from_symbol": None, "to_name": m.group(2),
                             "kind": "import", "line": i + 1})
        elif stripped.startswith("import "):
            m = re.match(r'^import\s+(?:\w+\s+)?"([^"]+)"', stripped)
            if m:
                refs.append({"from_symbol": None, "to_name": m.group(1),
                             "kind": "import", "line": i + 1})
    refs.extend(_call_refs(content, lines, symbols))
    return symbols, refs


# ------------------------------------------------------------------ API ----

def _dedupe_refs(refs, symbols):
    """One ref per (to_name, line) site: the innermost enclosing scope wins,
    and 'call' beats 'use' at the same site. Nested ast scopes / brace blocks
    otherwise report every use once per enclosing symbol."""
    by_site = {}
    for r in refs:
        by_site.setdefault((r["to_name"], r["line"]), []).append(r)
    spans = sorted(((s["start_line"], s["end_line"], s["name"]) for s in symbols),
                   key=lambda t: t[1] - t[0])

    def innermost(line):
        for a, b, n in spans:
            if a <= line <= b:
                return n
        return None

    out = []
    for (to_name, line), group in by_site.items():
        target = innermost(line)
        best = None
        if target is not None:
            for r in group:
                fs = r["from_symbol"] or ""
                if fs == target or fs.endswith("." + target):
                    best = r
                    break
        if best is None:
            best = group[0]
        for r in group:
            if r["kind"] == "call" and (r["from_symbol"] or "") == (best["from_symbol"] or ""):
                best = r
                break
        out.append(best)
    return out


def extract(path: str, content: str):
    """Return (symbols, refs); ([], []) for unsupported/binary/oversized files."""
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if len(content.encode("utf-8", "ignore")) > MAX_BYTES:
        return [], []
    try:
        if ext in PY_EXTS:
            syms, refs = extract_python(content)
        elif ext in JS_EXTS:
            syms, refs = extract_js(content)
        elif ext == ".go":
            syms, refs = extract_go(content)
        else:
            return [], []
    except (SyntaxError, ValueError, RecursionError):
        return [], []  # unparseable file: skip silently, index stays best-effort
    return syms, _dedupe_refs(refs, syms)
