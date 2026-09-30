#!/usr/bin/env python3
"""
productmap — the product map of a feature, generated from its code
(owner request, 2026-09-30).

A feature's map is a markdown file in the project, `docs/map/<slug>.md`,
kept beside the specs as a reference: screens → components → API calls
→ handlers → the guards and business rules that can refuse the call, the
events it emits, the columns it writes and the tables it reads, and the
triggers behind them. The top of the file is for people (by screen, the
rule catalog, events, who writes and reads each table); the bottom is the
full edge list for agents and for export to a graph tool.

The kernel knows no project. Everything project-specific lives in
`docs/map/conventions.toml` in the project: where routes and API clients
are, which function refuses a call and where its messages are, which
functions are guards, which emit events, how tables are named. The agent
writes that file once by reading the code (`fde-map` skill).

Generated sections are rewritten on every run; the block between the
DECLARED markers is the project's own and is carried over verbatim.
`--check` fails when the file no longer matches the code.

Adapters shipped: frontend `react-routes` (JSX <Route> tree + exported API
client objects); backend `route-table` (a module-level dict
{path: {METHOD: function}}) with SQL in Python strings and migrations.
Other stacks are other adapters. stdlib only (I6).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

GENERATED = "<!-- FDE-MAP:GENERATED — regenerated from code; edit only the declared block -->"
DECL_BEGIN = "<!-- FDE-MAP:DECLARED:BEGIN — kept across regenerations -->"
DECL_END = "<!-- FDE-MAP:DECLARED:END -->"
SQL_HINT = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.I)
IMPORT = re.compile(r'import\s+(?:type\s+)?(?:(\w+)|\{([^}]*)\})(?:\s*,\s*\{([^}]*)\})?\s+from\s+"([^"]+)"')
CODE = re.compile(r"[A-Z][A-Z0-9_]{2,}")


class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str, str]] = []

    def node(self, nid, kind, **attrs):
        self.nodes.setdefault(nid, {"kind": kind})
        self.nodes[nid].update({k: v for k, v in attrs.items() if v is not None})
        return nid

    def edge(self, a, rel, b, prov=""):
        self.edges.append((a, rel, b, prov))

    def unique(self):
        self.edges = list(dict.fromkeys(self.edges))
        return self


class Mapper:
    def __init__(self, root: Path, conv: dict, feature: dict):
        self.root = root.resolve()
        self.conv, self.feature = conv, feature
        fe, be = conv.get("frontend", {}), conv.get("backend", {})
        self.routes_file = self.root / fe.get("routes_file", "")
        self.fe_dir = self.root / feature.get("feature_dir", fe.get("feature_dir", ""))
        self.fe_root = self.root / fe.get("source_root", "src")
        self.client_glob = fe.get("client_glob", "*Api*.ts")
        self.base_helper = fe.get("path_base_helper", "base")
        self.prefix = feature.get("route_prefix", "/")
        self.handler_glob = feature.get("handler_glob", be.get("handler_glob", ""))
        self.shared = self.root / be.get("shared_dir", "__none__")
        self.route_table = be.get("route_table", "ROUTES")
        self.table = be.get("table_pattern", r"(?:\w+\.)?(\w+)\b")
        self.sql_tag = re.compile(be.get("sql_tag", r"--\s*([\w.]+)")) if be.get("sql_tag") else None
        self.migrations_glob = be.get("migrations_glob", "")
        rules = conv.get("rules", {})
        self.refusals = set(rules.get("refusal_calls", []))
        self.guards = tuple(rules.get("guard_prefixes", []))
        self.protocol = set(rules.get("protocol_codes", []))
        self.catalogs = rules.get("catalogs", [])
        self.emits = set(conv.get("events", {}).get("emit_calls", []))
        self.g = Graph()
        self._modules: dict[Path, Module] = {}

    def rel(self, p) -> str:
        try:
            return str(Path(p).resolve().relative_to(self.root))
        except ValueError:
            return str(p)

    # ------------------------------------------------------------ frontend
    def resolve_import(self, from_file: Path, spec: str):
        if not spec.startswith("."):
            return None
        base = (from_file.parent / spec).resolve()
        for cand in (base, base.with_suffix(".tsx"), base.with_suffix(".ts"),
                     base.with_suffix(".jsx"), base.with_suffix(".js"),
                     base / "index.tsx", base / "index.ts"):
            if cand.is_file():
                return cand
        return None

    def imports(self, f: Path) -> dict[str, Path]:
        out = {}
        for m in IMPORT.finditer(f.read_text(errors="replace")):
            names = [m.group(1)] if m.group(1) else []
            for grp in (m.group(2), m.group(3)):
                if grp:
                    names += [n.strip().split(" as ")[-1].replace("type ", "").strip()
                              for n in grp.split(",") if n.strip()]
            target = self.resolve_import(f, m.group(4))
            if target:
                for n in names:
                    out[n] = target
        return out

    def routes(self):
        """(full path, component, file, line) under the feature's prefix,
        from the JSX <Route> tree (element attribute read with braces
        balanced)."""
        if not self.routes_file.is_file():
            return []
        text = self.routes_file.read_text(errors="replace")
        imp = self.imports(self.routes_file)
        out, stack, i = [], [], 0
        while True:
            a, c = text.find("<Route", i), text.find("</Route>", i)
            if a == -1 and c == -1:
                break
            if c != -1 and (a == -1 or c < a):
                if stack:
                    stack.pop()
                i = c + 8
                continue
            j, depth = a + 6, 0
            while j < len(text):
                ch = text[j]
                depth += ch == "{"
                depth -= ch == "}"
                if ch == ">" and depth == 0:
                    break
                j += 1
            attrs, i = text[a + 6:j], j + 1
            selfclose = attrs.rstrip().endswith("/")
            path = re.search(r'path="([^"]*)"', attrs)
            comp = re.search(r"element=\{<(\w+)", attrs)
            if not path and "index" not in attrs:
                if not selfclose:
                    stack.append("")
                continue
            seg = path.group(1) if path else ""
            full = "/" + "/".join(s.strip("/") for s in [*stack, seg] if s.strip("/"))
            if comp and full.startswith(self.prefix) and comp.group(1) in imp \
                    and str(imp[comp.group(1)]).startswith(str(self.fe_dir.resolve())):
                out.append((full, comp.group(1), imp[comp.group(1)],
                            text.count("\n", 0, a) + 1))
            if not selfclose:
                stack.append(seg)
        return out

    def norm_path(self, raw: str, base_expr: str | None = None) -> str:
        p = raw.strip("`\"")
        if base_expr:
            p = re.sub(r"\$\{" + self.base_helper + r"\(\w+\)\}", base_expr, p)
        return re.sub(r"\$\{(?:[\w.]+\()?(\w+)\)?\}", lambda m: "{" + m.group(1) + "}", p)

    def first_path(self, chunk: str, base_expr: str | None):
        pat = re.compile(r"`\$\{" + self.base_helper + r"\(\w+\)\}([^`?]*)|`(/[^`?]*)|\"(/[^\"?]*)|\b("
                         + self.base_helper + r")\(\w+\)")
        for m in pat.finditer(chunk):
            if m.group(1) is not None and base_expr:
                return base_expr + self.norm_path("`" + m.group(1) + "`")
            if m.group(4):
                return base_expr
            return self.norm_path("`" + (m.group(2) or m.group(3)) + "`", base_expr)
        return None

    @staticmethod
    def method_of(chunk: str) -> str:
        m = re.search(r'\(\s*"(GET|POST|PUT|PATCH|DELETE)"|method:\s*"(\w+)"', chunk)
        return (m.group(1) or m.group(2)) if m else "GET"

    def clients(self):
        """{(client object, function): (METHOD, path, file:line)} from the
        feature's exported API client objects."""
        out = {}
        for f in sorted(self.fe_dir.glob(self.client_glob)):
            text = f.read_text(errors="replace")
            obj = re.search(r"export const (\w+)\s*=\s*\{", text)
            if not obj:
                continue
            name = obj.group(1)
            b = re.search(r"const " + self.base_helper + r" = \(\w+: \w+\) => `([^`]+)`", text)
            base_expr = self.norm_path(b.group(1)) if b else None
            funcs = {}
            for m in re.finditer(r"^(?:export )?(?:async )?function (\w+)\(", text, re.M):
                s0 = text.find("{\n", m.end())
                s1 = text.find("\n}", s0)
                if s0 != -1 and s1 != -1:
                    funcs[m.group(1)] = (m.start(), text[s0:s1])
            end = text.find("\n};", obj.end())
            block = text[obj.end():end]
            starts = [(m.start(), m.group(1), m.group(2)) for m in
                      re.finditer(r"^\s{2}(\w+)(?::\s*(\w+)?)?", block, re.M)]
            for k, (st, fn, ref) in enumerate(starts):
                chunk = block[st:starts[k + 1][0]] if k + 1 < len(starts) else block[st:]
                line = text.count("\n", 0, obj.end() + st) + 1
                head = chunk.strip().splitlines()[0].strip().rstrip(",") if chunk.strip() else ""
                target = ref if ref and ref in funcs else (fn if head == fn else None)
                if target and target in funcs:
                    chunk, line = funcs[target][1], text.count("\n", 0, funcs[target][0]) + 1
                path = self.first_path(chunk, base_expr)
                if path:
                    out[(name, fn)] = (self.method_of(chunk), path, f"{self.rel(f)}:{line}")
        return out

    def components(self, roots, client_names):
        seen, todo, renders, calls = set(), list(roots), [], []
        call_re = re.compile(r"\b(" + "|".join(map(re.escape, client_names)) + r")\.(\w+)\(") \
            if client_names else None
        while todo:
            f = todo.pop()
            if f in seen or not f.is_file():
                continue
            seen.add(f)
            text = f.read_text(errors="replace")
            for name, target in self.imports(f).items():
                if not str(target).startswith(str(self.fe_root.resolve())):
                    continue
                if re.search(r"<" + name + r"\b", text) or (
                        target.suffix in (".ts", ".js") and re.search(r"\b" + name + r"\(", text)):
                    renders.append((f, target))
                    todo.append(target)
            if call_re:
                for m in call_re.finditer(text):
                    calls.append((f, m.group(1), m.group(2), text.count("\n", 0, m.start()) + 1))
        return renders, calls

    # ------------------------------------------------------------- backend
    def module(self, path: Path) -> "Module":
        path = self.canonical(path)
        if path not in self._modules:
            self._modules[path] = Module(path, self)
        return self._modules[path]

    def canonical(self, path: Path) -> Path:
        """Identical copies of a shared module count once."""
        shared = self.shared / path.name
        if shared.is_file() and path.resolve() != shared.resolve() and \
                hashlib.md5(shared.read_bytes()).digest() == hashlib.md5(path.read_bytes()).digest():
            return shared
        return path

    def reach(self, mod, fname, via=(), depth=0, seen=None):
        seen = seen if seen is not None else set()
        key = (mod.path, fname)
        if key in seen or depth > 6 or fname not in mod.funcs:
            return []
        seen.add(key)
        fn, out, here = mod.funcs[fname], [], self.rel(mod.path)
        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                name = n.func.id if isinstance(n.func, ast.Name) else \
                    n.func.attr if isinstance(n.func, ast.Attribute) else ""
                code = next((x.value for x in n.args if isinstance(x, ast.Constant)
                             and isinstance(x.value, str) and CODE.fullmatch(x.value)), None)
                if name in self.refusals and code:
                    out.append(("refuses", code, via, f"{here}:{n.lineno}"))
                elif name in self.emits and code:
                    out.append(("emits", code, via, f"{here}:{n.lineno}"))
                tgt = mod.target_of(n.func)
                if tgt:
                    m2, f2 = tgt
                    if self.guards and f2.startswith(self.guards):
                        gid = f"{m2.path.stem}.{f2}"
                        out.append(("guard", gid, via, f"{here}:{n.lineno}"))
                        out += self.reach(m2, f2, via + (gid,), depth + 1, seen)
                    else:
                        out += self.reach(m2, f2, via, depth + 1, seen)
            s, where = None, ""
            if isinstance(n, ast.Name) and n.id in mod.assigns:
                s, where = mod.const(n.id), f"{here}:{n.id}"
            elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in mod.imports:
                m2name, nm = mod.imports[n.value.id]
                p = mod.resolve_module(nm or m2name) or mod.resolve_module(m2name)
                if p:
                    m2 = self.module(p)
                    s, where = m2.const(n.attr), f"{self.rel(m2.path)}:{n.attr}"
            elif isinstance(n, (ast.Constant, ast.JoinedStr)):
                s, where = mod.literal(n), f"{here}:{getattr(n, 'lineno', fn.lineno)}"
            if s and SQL_HINT.search(s) and re.search(self.table, s):
                out.append(("sql", s, via, where))
        return out

    def sql_effects(self, sql: str):
        out, s = [], re.sub(r"--[^\n]*", "", sql)
        t = self.table
        for m in re.finditer(r"INSERT\s+INTO\s+" + t + r"\s*\(([^)]*)\)", s, re.I):
            out.append(("writes", m.group(1), [c.strip() for c in m.group(2).split(",") if c.strip()]))
        for m in re.finditer(r"UPDATE\s+" + t + r"\s+(?:\w+\s+)?SET\s+(.*?)(?:\bWHERE\b|\bRETURNING\b|\bFROM\b|$)",
                             s, re.I | re.S):
            cols = re.findall(r"(?:^|,)\s*(\w+)\s*=", m.group(2))
            out.append(("writes", m.group(1), cols or ["?"]))
        for m in re.finditer(r"DELETE\s+FROM\s+" + t, s, re.I):
            out.append(("deletes", m.group(1), []))
        for m in re.finditer(r"(?:FROM|JOIN)\s+" + t, s, re.I):
            out.append(("reads", m.group(1), []))
        tag = self.sql_tag.search(sql) if self.sql_tag else None
        return out, (tag.group(1) if tag else None)

    def route_table_entries(self):
        out = []
        for hf in sorted(self.root.glob(self.handler_glob)) if self.handler_glob else []:
            mod = Module(hf, self)
            table = mod.assigns.get(self.route_table)
            if not isinstance(table, ast.Dict):
                continue
            for k, v in zip(table.keys, table.values):
                path = mod.literal(k) or "?"
                if not isinstance(v, ast.Dict):
                    continue
                for mk, mv in zip(v.keys, v.values):
                    func = mv if isinstance(mv, (ast.Name, ast.Attribute)) else None
                    ref = mod.target_of(func) if func is not None else None
                    ref = ref or (mod, getattr(mv, "id", getattr(mv, "attr", "?")))
                    out.append((mk.value, path, ref, f"{self.rel(hf)}:{k.lineno}"))
        return out

    def messages(self):
        msgs = {}
        for c in self.catalogs:
            path = self.root / c["file"]
            if not path.is_file():
                continue
            mod = Module(path, self)
            vocab = Module(self.root / c["messages_from"], self) \
                if c.get("messages_from") and (self.root / c["messages_from"]).is_file() else None
            d = mod.assigns.get(c["name"])
            if not isinstance(d, ast.Dict):
                continue
            for k, v in zip(d.keys, d.values):
                if isinstance(k, ast.Tuple) and k.elts and isinstance(k.elts[0], ast.Constant):
                    k = k.elts[0]
                if isinstance(k, ast.Constant) and isinstance(v, ast.Tuple) and len(v.elts) == 2:
                    status = v.elts[0].value if isinstance(v.elts[0], ast.Constant) else None
                    msg = mod.literal(v.elts[1])
                    if vocab and msg and msg in vocab.assigns:
                        msg = vocab.const(msg)
                    msgs.setdefault(k.value, (status, msg))
        return msgs

    def triggers(self):
        out, writes = [], defaultdict(set)
        migs = sorted(self.root.glob(self.migrations_glob)) if self.migrations_glob else []
        texts = {f: f.read_text(errors="replace") for f in migs}
        for f, t in texts.items():
            for m in re.finditer(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:\w+\.)?(\w+)\s*\(.*?\$(\w*)\$(.*?)\$\2\$",
                                 t, re.I | re.S):
                for w in re.finditer(r"INSERT\s+INTO\s+" + self.table, m.group(3), re.I):
                    writes[m.group(1)].add(w.group(1))
        for f, t in texts.items():
            for m in re.finditer(r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(\w+)(.*?)\bON\s+" + self.table
                                 + r"(.*?)EXECUTE\s+(?:FUNCTION|PROCEDURE)\s+(?:\w+\.)?(\w+)", t, re.I | re.S):
                out.append((m.group(1), m.group(3), m.group(5), sorted(writes.get(m.group(5), ())),
                            f"{self.rel(f)}:{t.count(chr(10), 0, m.start()) + 1}"))
        return out

    # ------------------------------------------------------------ assemble
    def build(self) -> Graph:
        g = self.g
        rs = self.routes()
        for full, comp, f, line in rs:
            s = g.node(f"screen:{full}", "screen", file=self.rel(f))
            g.edge(s, "renders", g.node(f"component:{f.stem}", "component", file=self.rel(f)),
                   f"{self.rel(self.routes_file)}:{line}")
        cl = self.clients()
        client_names = sorted({o for o, _ in cl})
        feature_rel = self.rel(self.fe_dir)
        extra = []
        if self.fe_root.is_dir():
            for f in self.fe_root.rglob("*.ts*"):
                if str(f.resolve()).startswith(str(self.fe_dir.resolve())) or "test" in f.name:
                    continue
                if any(t for t in self.imports(f).values()
                       if str(t).startswith(str(self.fe_dir.resolve()))):
                    extra.append(f)
        renders, calls = self.components([f for _, _, f, _ in rs] + extra, client_names)
        for a, b in renders:
            g.edge(g.node(f"component:{a.stem}", "component", file=self.rel(a)), "uses",
                   g.node(f"component:{b.stem}", "component", file=self.rel(b)))
        for f, obj, fn, line in calls:
            comp = g.node(f"component:{f.stem}", "component", file=self.rel(f))
            c = cl.get((obj, fn))
            if c:
                g.edge(comp, "calls", g.node(f"api:{c[0]} {c[1]}", "api", client=c[2]), f"{self.rel(f)}:{line}")
            else:
                g.edge(comp, "calls", g.node(f"client:{obj}.{fn}", "unresolved"),
                       f"{self.rel(f)}:{line} (path not resolved)")
        msgs = self.messages()
        for meth, path, (mod, fname), where in self.route_table_entries():
            api = next((n for n in g.nodes if n.startswith(f"api:{meth} ")
                        and same_path(n.split(" ", 1)[1], path)), None) \
                or g.node(f"api:{meth} {path}", "api", no_screen=True)
            fnode = mod.funcs.get(fname)
            h = g.node(f"handler:{mod.path.stem}.{fname}", "handler",
                       file=f"{self.rel(mod.path)}:{getattr(fnode, 'lineno', '?')}")
            g.edge(api, "handled_by", h, where)
            for kind, what, via, w in self.reach(mod, fname):
                owner = f"guard:{via[-1]}" if via else h
                if kind == "guard":
                    g.node(f"guard:{what}", "guard")
                    g.edge(owner, "applies", f"guard:{what}", w)
                elif kind == "refuses":
                    if what in self.protocol:
                        continue
                    status, msg = msgs.get(what, (None, None))
                    g.node(f"rule:{what}", "rule", status=status, message=msg)
                    g.edge(owner, "refuses", f"rule:{what}", w)
                elif kind == "emits":
                    g.edge(owner, "emits", g.node(f"event:{what}", "event"), w)
                else:
                    effects, tag = self.sql_effects(what)
                    prov = w + (f" [{tag}]" if tag else "") + (f" via {via[-1]}" if via else "")
                    for op, table, cols in effects:
                        if cols:
                            for col in cols:
                                g.edge(h, op, g.node(f"column:{table}.{col}", "column"), prov)
                        else:
                            g.edge(h, op, g.node(f"table:{table}", "table"), prov)
        for name, table, fn, writes, where in self.triggers():
            t = g.node(f"table:{table}", "table")
            if writes:
                for w in writes:
                    g.edge(t, "fires_into", g.node(f"table:{w}", "table"), f"{where} trigger {name}")
            else:
                g.edge(t, "protected_by", g.node(f"trigger:{name}", "trigger"), where)
        return g.unique()


class Module:
    def __init__(self, path: Path, mapper: Mapper):
        self.path, self.mapper = path, mapper
        self.tree = ast.parse(path.read_text(errors="replace"))
        self.funcs = {n.name: n for n in self.tree.body
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assigns, self.imports, self._const = {}, {}, {}
        for n in self.tree.body:
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    if isinstance(t, ast.Name) and n.value is not None:
                        self.assigns[t.id] = n.value
            elif isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    self.imports[a.asname or a.name] = (n.module, a.name)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    self.imports[a.asname or a.name] = (a.name, None)

    def resolve_module(self, modname: str):
        for base in (self.path.parent, self.mapper.shared):
            cand = base / (modname.split(".")[-1] + ".py")
            if cand.is_file():
                return cand
        return None

    def const(self, name, depth=0):
        if name not in self._const:
            self._const[name] = None
            v = self.assigns.get(name)
            self._const[name] = self.literal(v, depth) if v is not None else None
        return self._const[name]

    def literal(self, v, depth=0):
        """A string, with constants substituted inside f-strings and `+`
        (SQL built from other SQL constants)."""
        if depth > 6 or v is None:
            return None
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            return v.value
        if isinstance(v, ast.Name):
            return self.const(v.id, depth + 1)
        if isinstance(v, ast.JoinedStr):
            return "".join(p.value if isinstance(p, ast.Constant) else
                           (self.literal(p.value, depth + 1) or " {expr} ") for p in v.values)
        if isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add):
            a, b = self.literal(v.left, depth + 1), self.literal(v.right, depth + 1)
            return (a or "") + (b or "") if (a or b) else None
        return None

    def target_of(self, func):
        if isinstance(func, ast.Name):
            if func.id in self.funcs:
                return self, func.id
            if func.id in self.imports:
                m2, name = self.imports[func.id]
                p = self.resolve_module(m2)
                if p:
                    return self.mapper.module(p), name or func.id
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id in self.imports:
            m2, name = self.imports[func.value.id]
            p = self.resolve_module(name or m2) or self.resolve_module(m2)
            if p:
                return self.mapper.module(p), func.attr
        return None


def same_path(a: str, b: str) -> bool:
    sa, sb = a.strip("/").split("/"), b.strip("/").split("/")
    return len(sa) == len(sb) and all(x == y or (x.startswith("{") and y.startswith("{"))
                                       for x, y in zip(sa, sb))


# -------------------------------------------------------------------- render
def render(g: Graph, feature: dict, sha: str, declared: str) -> str:
    out = defaultdict(list)
    for a, r, b, p in g.edges:
        out[a].append((r, b))

    def targets(n, r):
        return sorted({b for rr, b in out[n] if rr == r})

    def guards(n):
        seen, todo = set(), targets(n, "applies")
        while todo:
            x = todo.pop()
            if x not in seen:
                seen.add(x)
                todo += targets(x, "applies")
        return seen

    def via_guards(h, r):
        s = set(targets(h, r))
        for x in guards(h):
            s |= set(targets(x, r))
        return sorted(s)

    def writes(h):
        t = defaultdict(set)
        for r, b in out[h]:
            if r == "writes":
                tab, col = b.split(":", 1)[1].split(".", 1)
                t[tab].add(col)
            elif r == "deletes":
                t[b.split(":", 1)[1]].add("(delete)")
        return t

    def reads(h):
        return sorted({b.split(":", 1)[1] for r, b in out[h] if r == "reads"})

    kinds = defaultdict(int)
    for n in g.nodes.values():
        kinds[n["kind"]] += 1
    api_handler = {a: b for a, r, b, _ in g.edges if r == "handled_by"}
    handler_apis = defaultdict(list)
    for a, h in api_handler.items():
        handler_apis[h].append(a)

    L = ["---", f"feature: {feature.get('name', feature.get('slug'))}",
         f"route_prefix: {feature.get('route_prefix', '/')}", f"generated_from: {sha}", "---",
         f"# Product map — {feature.get('name', feature.get('slug'))}", "", GENERATED, "",
         "## Summary", ""]
    for k, label in (("screen", "screens"), ("component", "components"), ("api", "API operations"),
                     ("handler", "handlers"), ("guard", "guards"), ("rule", "business rules"),
                     ("event", "events"), ("table", "tables"), ("column", "columns"),
                     ("unresolved", "unresolved calls")):
        if kinds.get(k):
            L.append(f"- {label}: {kinds[k]}")
    L.append(f"- edges: {len(g.edges)}")

    L += ["", "## By screen", ""]
    for s in sorted(n for n in g.nodes if n.startswith("screen:")):
        L.append(f"### {s[7:]}  (`{g.nodes[s].get('file')}`)")
        seen, todo = set(), targets(s, "renders")
        while todo:
            c = todo.pop()
            if c not in seen:
                seen.add(c)
                todo += targets(c, "uses")
        for c in sorted(seen):
            apis = targets(c, "calls")
            if not apis:
                continue
            L.append(f"- **{c.split(':', 1)[1]}**")
            for api in apis:
                h = api_handler.get(api)
                L.append(f"  - `{api[4:]}` → `{h.split(':', 1)[1] if h else '?'}`")
                if not h:
                    continue
                for label, items in (("refuses", via_guards(h, "refuses")),
                                     ("emits", via_guards(h, "emits"))):
                    if items:
                        L.append(f"    - {label}: " + ", ".join(f"`{i.split(':', 1)[1]}`" for i in items))
                w = writes(h)
                if w:
                    L.append("    - writes: " + "; ".join(
                        f"{t}.{{{', '.join(sorted(cs))}}}" for t, cs in sorted(w.items())))
                rd = reads(h)
                if rd:
                    L.append("    - reads: " + ", ".join(rd))
        L.append("")
    orphan = sorted(n for n, d in g.nodes.items() if d.get("no_screen"))
    if orphan:
        L += ["### API operations no screen calls", ""] + [f"- `{a[4:]}`" for a in orphan] + [""]

    rules = sorted(n for n in g.nodes if n.startswith("rule:"))
    if rules:
        L += ["## Business rules", "",
              "| rule | status | message to the user | applied in | operations |", "|---|---|---|---|---|"]
        for r in rules:
            owners = sorted({a.split(":", 1)[1] for a, rr, b, _ in g.edges if rr == "refuses" and b == r})
            ops = sum(1 for h in handler_apis if r in via_guards(h, "refuses") for _ in handler_apis[h])
            n = g.nodes[r]
            L.append(f"| `{r[5:]}` | {n.get('status', '')} | {n.get('message') or '—'} | "
                     f"{', '.join(owners)} | {ops} |")
        L.append("")
    events = sorted(n for n in g.nodes if n.startswith("event:"))
    if events:
        L += ["## Events", ""]
        for e in events:
            owners = sorted({a.split(":", 1)[1] for a, rr, b, _ in g.edges if rr == "emits" and b == e})
            L.append(f"- `{e[6:]}` ← {', '.join(owners)}")
        L.append("")
    tables = sorted({n.split(":", 1)[1].split(".")[0] for n in g.nodes
                     if n.startswith(("column:", "table:")) and "?" not in n})
    if tables:
        L += ["## Tables", "", "| table | written by | read by | trigger writes to | guard triggers |",
              "|---|---|---|---|---|"]
        for t in tables:
            w = sum(1 for h in handler_apis if t in writes(h))
            r = sum(1 for h in handler_apis if t in reads(h))
            fi = sorted({b.split(":", 1)[1] for a, rr, b, _ in g.edges if rr == "fires_into" and a == f"table:{t}"})
            pr = sum(1 for a, rr, b, _ in g.edges if rr == "protected_by" and a == f"table:{t}")
            L.append(f"| {t} | {w} | {r} | {', '.join(fi)} | {pr or ''} |")
        L.append("")
    L += ["## Declared by hand", "", DECL_BEGIN, declared.strip("\n") or
          "<!-- what code cannot show: intent, external systems, known gaps -->", DECL_END, "",
          "## Edges", "", "```edges"]
    L += [f"{a}  {r}  {b}  [{p}]" for a, r, b, p in g.edges]
    L += ["```", ""]
    return "\n".join(L)


def declared_block(text: str) -> str:
    if DECL_BEGIN in text and DECL_END in text:
        return text.split(DECL_BEGIN, 1)[1].split(DECL_END, 1)[0].strip("\n")
    return ""


def comparable(text: str) -> str:
    """The generated part only: the declared block and the source SHA do
    not count as drift."""
    text = re.sub(r"^generated_from: .*$", "", text, flags=re.M)
    if DECL_BEGIN in text and DECL_END in text:
        a, rest = text.split(DECL_BEGIN, 1)
        text = a + rest.split(DECL_END, 1)[1]
    return text


def load_conventions(root: Path, path: str | None = None) -> dict:
    p = Path(path) if path else root / "docs" / "map" / "conventions.toml"
    if not p.is_file():
        raise SystemExit(f"productmap: no {p} — the fde-map skill writes it "
                         "by reading the code")
    return tomllib.loads(p.read_text(encoding="utf-8"))


def generate(root: Path, conv: dict, feature: dict) -> tuple[Graph, str]:
    g = Mapper(root, conv, feature).build()
    sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip() or "—"
    target = root / "docs" / "map" / f"{feature['slug']}.md"
    old = target.read_text(encoding="utf-8") if target.is_file() else ""
    return g, render(g, feature, sha, declared_block(old))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="product map of a feature, from its code")
    ap.add_argument("--root", default=".", help="project root (default: cwd)")
    ap.add_argument("--feature", help="one feature slug (default: all in conventions.toml)")
    ap.add_argument("--write", action="store_true", help="write docs/map/<slug>.md")
    ap.add_argument("--check", action="store_true", help="exit 1 when a map is out of date")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--conventions", help="conventions file (default: docs/map/conventions.toml)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    conv = load_conventions(root, args.conventions)
    features = [f for f in conv.get("feature", []) if not args.feature or f.get("slug") == args.feature]
    if not features:
        print("productmap: no [[feature]] matches", file=sys.stderr)
        return 2
    stale = []
    for feature in features:
        g, md = generate(root, conv, feature)
        target = root / "docs" / "map" / f"{feature['slug']}.md"
        if args.check:
            old = target.read_text(encoding="utf-8") if target.is_file() else ""
            if comparable(old) != comparable(md):
                stale.append(str(target.relative_to(root)))
            continue
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(md, encoding="utf-8")
            print(f"wrote {target.relative_to(root)} ({len(g.nodes)} nodes, {len(g.edges)} edges)")
        elif args.format == "json":
            print(json.dumps({"feature": feature, "nodes": g.nodes,
                              "edges": [dict(zip(("source", "relation", "target", "provenance"), e))
                                        for e in g.edges]}, indent=2, ensure_ascii=False))
        else:
            sys.stdout.write(md)
    if args.check:
        if stale:
            print("productmap: out of date — run `python3 bin/fde/productmap.py --write`: "
                  + ", ".join(stale))
            return 1
        print(f"productmap: {len(features)} map(s) match the code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
