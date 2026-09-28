"""The mirror checker (FWD-020, ADR-0016): one declared mechanism for every
source→copy pair in this self-hosted repository.

Pure core. `check(root, manifest)` reads only under `root` and returns
labeled violations; it never writes, spawns a process, touches git or the
network, or depends on the cwd or the environment. Schema problems are
violations (pair "<manifest>"), never exceptions; I/O and decode errors
propagate so the calling test errors (red). An empty list is the only
green. The attack-order renderer formats the kernel's own plan
(`runtime/fde_lib.py::probe_plan`), imported from this repository's
runtime; it reads its inputs from under `root` like every other renderer.

Not collected by unittest discovery (the name does not match `test*.py`);
test modules import it the way they import `support`. The manifest it
reads is `tests/mirror.toml`; its schema is
`specs/FWD-020-mirror-drift/architecture.md`.
"""
from __future__ import annotations

import fnmatch
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

# The attack order is the kernel's own derivation (runtime/fde_lib.py
# probe_plan), imported, never re-derived here (F2, MNT-11).
_KERNEL_RUNTIME = str(Path(__file__).resolve().parent.parent / "runtime")
if _KERNEL_RUNTIME not in sys.path:
    sys.path.insert(0, _KERNEL_RUNTIME)
import fde_lib  # noqa: E402

MANIFEST = "<manifest>"

RELATIONS = frozenset({"identical", "identical-except", "absent"})
RENDERERS = ("invariants_list", "weights_list", "depths_list", "attack_order")
KINDS = frozenset({
    "malformed", "missing-source", "empty-source", "zero-checked",
    "missing-copy", "differs", "orphan", "present-but-absent",
    "stale-exception", "count-mismatch", "source-of-truth-missing",
    "not-a-regular-file", "ignore-not-in-gitignore",
})

TOP_KEYS = frozenset({"meta", "sources", "ignore", "pair"})
SOURCE_KEYS = frozenset({"config", "invariants", "attributes"})
PAIR_REQUIRED = frozenset({"id", "source", "copy", "relation"})
PAIR_OPTIONAL = frozenset({"erosion_measured", "except"})
EXCEPT_KEYS = {
    "placeholder": frozenset({"kind", "token", "count", "value"}),
    "substitute": frozenset({"kind", "from", "to", "count"}),
    "insert": frozenset({"kind", "before", "text"}),
    "replace-section": frozenset({"kind", "heading", "value"}),
}
GLOB_CHARS = frozenset("*?[]!\\")
# The one non-literal ignore form: `*.<suffix>`, a literal basename suffix
# (e.g. `*.pyc`, which .gitignore's `*.py[co]` covers). Nothing broader.
SUFFIX_IGNORE = re.compile(r"\*\.[A-Za-z0-9_-]+")


class Violation(NamedTuple):
    pair: str
    relation: str
    path: str
    kind: str
    detail: str


class SourceOfTruthMissing(Exception):
    """Raised by `resolve` for a key/file the declared source lacks; caught
    by name only, and turned into a `source-of-truth-missing` violation."""


def load(path) -> dict:
    """Parse the manifest with tomllib. No validation — `check` validates."""
    with open(path, "rb") as fh:
        return tomllib.load(fh)


# --------------------------------------------------------------------------
# schema


def _bad_path(p) -> str | None:
    """A manifest path is relative, POSIX, with no empty, `.` or `..`
    component. Returns the reason it is not, or None."""
    if not isinstance(p, str) or not p:
        return "not a non-empty string"
    if p.startswith("/") or "\\" in p or ":" in p.split("/")[0]:
        return "not a relative POSIX path"
    parts = p[:-1].split("/") if p.endswith("/") else p.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "empty, '.' or '..' component"
    return None


def _bad_value(v) -> str | None:
    if not isinstance(v, str):
        return "value is not a string"
    if v.startswith("config:"):
        key = v[len("config:"):]
        if not key or any(not k for k in key.split(".")):
            return f"bad config key {v!r}"
        return None
    if v.startswith("render:"):
        name = v[len("render:"):]
        if name not in RENDERERS:
            return f"unknown renderer {name!r}"
        return None
    return f"value {v!r} is neither config:<key> nor render:<name>"


def _is_count(n) -> bool:
    return isinstance(n, int) and not isinstance(n, bool) and n >= 1


def _validate_except(pid: str, i: int, e) -> list[str]:
    where = f"pair {pid!r} except[{i}]"
    if not isinstance(e, dict):
        return [f"{where}: not a table"]
    kind = e.get("kind")
    if kind not in EXCEPT_KEYS:
        return [f"{where}: unknown exception kind {kind!r}"]
    keys = EXCEPT_KEYS[kind]
    out = []
    if set(e) != keys:
        out.append(f"{where}: {kind} takes exactly {sorted(keys)}, "
                   f"got {sorted(e)}")
        return out
    if "count" in keys and not _is_count(e["count"]):
        out.append(f"{where}: count must be an integer >= 1")
    for k in ("token", "from", "to", "before", "text", "heading"):
        if k in keys and (not isinstance(e[k], str) or not e[k]):
            out.append(f"{where}: {k} must be a non-empty string")
    if "value" in keys:
        bad = _bad_value(e["value"])
        if bad:
            out.append(f"{where}: {bad}")
    if kind == "replace-section" and isinstance(e["heading"], str):
        h = e["heading"]
        hashes = len(h) - len(h.lstrip("#"))
        if hashes == 0 or h[hashes:hashes + 1] != " " or "\n" in h:
            out.append(f"{where}: heading must be one '#… ' line")
    if kind == "substitute" and e.get("from") == e.get("to"):
        out.append(f"{where}: from equals to")
    return out


def _validate(manifest) -> list[str]:
    if not isinstance(manifest, dict):
        return ["manifest is not a table"]
    out = []
    extra = set(manifest) - TOP_KEYS
    if extra:
        out.append(f"unknown top-level keys {sorted(extra)}")
    missing = TOP_KEYS - set(manifest)
    if missing:
        out.append(f"missing top-level tables {sorted(missing)}")
        return out
    meta = manifest["meta"]
    if not isinstance(meta, dict) or set(meta) != {"schema"} \
            or meta.get("schema") != 1:
        out.append("[meta] must be exactly schema = 1")
    src = manifest["sources"]
    if not isinstance(src, dict) or set(src) != SOURCE_KEYS:
        out.append(f"[sources] must have exactly {sorted(SOURCE_KEYS)}")
    else:
        for k, v in src.items():
            bad = _bad_path(v)
            if bad or v.endswith("/"):
                out.append(f"[sources].{k}: {bad or 'must name a file'}")
    ign = manifest["ignore"]
    if not isinstance(ign, dict) or set(ign) != {"entries"} \
            or not isinstance(ign.get("entries"), list):
        out.append("[ignore] must be exactly entries = [...]")
    else:
        for entry in ign["entries"]:
            if isinstance(entry, str) and SUFFIX_IGNORE.fullmatch(entry):
                continue
            if not isinstance(entry, str) or not entry \
                    or GLOB_CHARS & set(entry) or entry.startswith("/") \
                    or _bad_path(entry):
                out.append(f"[ignore] entry {entry!r} is not a literal "
                           f"relative path or a `*.<suffix>`")
    pairs = manifest["pair"]
    if not isinstance(pairs, list) or not pairs:
        out.append("[[pair]] must be a non-empty array of tables")
        return out
    ids = set()
    for n, p in enumerate(pairs):
        if not isinstance(p, dict):
            out.append(f"pair[{n}] is not a table")
            continue
        pid = p.get("id", f"#{n}")
        keys = set(p)
        if not PAIR_REQUIRED <= keys or keys - PAIR_REQUIRED - PAIR_OPTIONAL:
            out.append(f"pair {pid!r}: keys must be {sorted(PAIR_REQUIRED)} "
                       f"plus optional {sorted(PAIR_OPTIONAL)}, got "
                       f"{sorted(keys)}")
            continue
        if not isinstance(pid, str) or not pid or \
                any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                    for c in pid):
            out.append(f"pair {pid!r}: id must match [a-z0-9-]+")
        elif pid in ids:
            out.append(f"pair {pid!r}: duplicate id")
        ids.add(pid)
        for side in ("source", "copy"):
            bad = _bad_path(p[side])
            if bad:
                out.append(f"pair {pid!r}: {side} {bad}")
        if isinstance(p["source"], str) and isinstance(p["copy"], str) and \
                p["source"].endswith("/") != p["copy"].endswith("/"):
            out.append(f"pair {pid!r}: source and copy must both be "
                       f"directories (trailing '/') or both files")
        rel = p["relation"]
        if rel not in RELATIONS:
            out.append(f"pair {pid!r}: unknown relation {rel!r}")
            continue
        if "erosion_measured" in p and (
                rel != "identical" or not isinstance(p["erosion_measured"],
                                                     bool)):
            out.append(f"pair {pid!r}: erosion_measured is a boolean, "
                       f"identical pairs only")
        if rel == "identical-except":
            exc = p.get("except")
            if not isinstance(exc, list) or not exc:
                out.append(f"pair {pid!r}: identical-except needs >= 1 "
                           f"[[pair.except]]")
            else:
                for i, e in enumerate(exc):
                    out.extend(_validate_except(pid, i, e))
            if isinstance(p["source"], str) and p["source"].endswith("/"):
                out.append(f"pair {pid!r}: identical-except applies to a "
                           f"file pair, not a directory")
        elif "except" in p:
            out.append(f"pair {pid!r}: except on a {rel} pair")
    if out:
        return out
    out.extend(_validate_layout(pairs))
    return out


def _contains(outer: str, inner: str) -> bool:
    """True when directory path `outer` (trailing '/') strictly contains
    path `inner`."""
    return outer.endswith("/") and inner != outer and inner.startswith(outer)


def _parent(pair: dict, pairs: list[dict]) -> dict | None:
    """The pair whose source directory most closely contains this pair's
    source (longest prefix)."""
    best = None
    for q in pairs:
        if q is not pair and _contains(q["source"], pair["source"]):
            if best is None or len(q["source"]) > len(best["source"]):
                best = q
    return best


def _ancestors(pair: dict, pairs: list[dict]) -> list[dict]:
    out, cur = [], _parent(pair, pairs)
    while cur is not None:
        out.append(cur)
        cur = _parent(cur, pairs)
    return out


def _validate_layout(pairs: list[dict]) -> list[str]:
    out = []
    seen: dict[str, str] = {}
    for p in pairs:
        if p["source"] in seen:
            out.append(f"pair {p['id']!r}: duplicate source {p['source']!r} "
                       f"(also {seen[p['source']]!r})")
        seen[p["source"]] = p["id"]
        parent = _parent(p, pairs)
        if parent is not None:
            offset = p["source"][len(parent["source"]):]
            if p["copy"] != parent["copy"] + offset:
                out.append(f"pair {p['id']!r} is nested in {parent['id']!r}: "
                           f"copy must be {parent['copy'] + offset!r}")
    for a in pairs:
        for b in pairs:
            if a is b or a["id"] >= b["id"]:
                continue
            overlap = (a["copy"] == b["copy"] or _contains(a["copy"], b["copy"])
                       or _contains(b["copy"], a["copy"]))
            nested = a in _ancestors(b, pairs) or b in _ancestors(a, pairs)
            if overlap and not nested:
                out.append(f"pairs {a['id']!r} and {b['id']!r}: overlapping "
                           f"copies without nested sources")
    return out


# --------------------------------------------------------------------------
# ignore


def _ignored(rel: str, is_dir: bool, entries: list[str]) -> bool:
    """Three literal forms and one suffix form, nothing else: `name/`
    matches a directory component anywhere; an entry with an inner `/`
    matches a root-relative prefix; a bare `name` matches a basename;
    `*.<suffix>` matches a file whose basename ends in `.<suffix>`."""
    parts = rel.split("/")
    dirs = parts if is_dir else parts[:-1]
    for e in entries:
        if SUFFIX_IGNORE.fullmatch(e):
            if not is_dir and parts[-1].endswith(e[1:]):
                return True
            continue
        core = e[:-1] if e.endswith("/") else e
        if "/" in core:                       # root-anchored prefix
            if e.endswith("/"):
                if (rel + "/").startswith(e):
                    return True
            elif rel == e or rel.startswith(e + "/"):
                return True
        elif e.endswith("/"):                 # directory name, any level
            if core in dirs:
                return True
        elif parts[-1] == e:                  # basename
            return True
    return False


def hidden(rel: str, is_dir: bool, entries: list[str]) -> bool:
    """THE ignore predicate: True when `rel`, or any directory above it, is
    ignored. Every walk (the checker's, the tests' `files_under`) and the
    tracked-file validator (`test_mirror.silenced_tracked`) call this one
    function, so what a walk drops and what the validator sees as dropped
    cannot diverge (F14: a bare `dimensions` hides a directory by name)."""
    parts = rel.split("/")
    return any(_ignored("/".join(parts[:n]), True, entries)
               for n in range(1, len(parts))) or \
        _ignored(rel, is_dir, entries)


def _gitignore_lines(root: Path) -> set[str]:
    gi = root / ".gitignore"
    if not gi.is_file():
        return set()
    return {line.rstrip() for line in
            gi.read_text(encoding="utf-8").splitlines()}


def _in_gitignore(entry: str, lines: set[str]) -> bool:
    """A literal entry must be a verbatim .gitignore line. A `*.<suffix>`
    entry must be matched, as a basename, by a basename pattern of
    .gitignore (`*.pyc` by `*.py[co]`) — git ignores it, so it is output."""
    if entry in lines:
        return True
    if not SUFFIX_IGNORE.fullmatch(entry):
        return False
    probe = "x" + entry[1:]
    return any(ln and not ln.startswith(("#", "!")) and "/" not in ln
               and fnmatch.fnmatchcase(probe, ln) for ln in lines)


# --------------------------------------------------------------------------
# sources of truth and renderers


def _toml(root: Path, rel: str) -> dict:
    f = root / rel
    if not f.is_file():
        raise SourceOfTruthMissing(f"{rel} does not exist")
    with open(f, "rb") as fh:
        return tomllib.load(fh)


def _get(d, dotted: str, where: str):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            raise SourceOfTruthMissing(f"{where} has no {dotted!r}")
        cur = cur[k]
    return cur


def _stable_desc(items: list[tuple[str, int]]) -> list[tuple[str, int]]:
    return sorted(items, key=lambda kv: -kv[1])  # sorted() is stable


def _int(v, where: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise SourceOfTruthMissing(f"{where} is not an integer")
    return v


def _render(root: Path, manifest: dict, name: str) -> str:
    src = manifest["sources"]
    if name == "invariants_list":
        inv = _get(_toml(root, src["invariants"]), "invariant",
                   src["invariants"])
        return "\n".join(
            f"- **{_get(i, 'id', 'invariant')} {_get(i, 'name', 'invariant')}**"
            f" — {' '.join(_get(i, 'statement', 'invariant').split())}"
            for i in inv)
    cfg = _toml(root, src["config"])
    if name == "weights_list":
        w = _get(cfg, "weights", src["config"])
        items = [(k, _int(v, f"weights.{k}")) for k, v in w.items()]
        return "\n".join(f"- {k}: {v}" for k, v in _stable_desc(items))
    if name == "depths_list":
        derived = _get(cfg, "derived.depths", src["config"])
        over = cfg.get("depths", {})
        keys = list(derived) + [k for k in over if k not in derived]
        items = [(k, max(_int(derived.get(k, 0), f"derived.depths.{k}"),
                         _int(over.get(k, 0), f"depths.{k}"))) for k in keys]
        return "\n".join(f"- {k}: {v}" for k, v in _stable_desc(items)
                         if v > 0)
    if name == "attack_order":
        return _attack_order(cfg, _toml(root, src["attributes"]), src)
    raise SourceOfTruthMissing(f"unknown renderer {name!r}")


def _attack_order(cfg: dict, quality: dict, src: dict) -> str:
    """SETUP §8.2's section, formatted from the kernel's own plan
    (`fde_lib.probe_plan`): its order (ties in quality-attributes.toml
    order) and its floor for an attribute [weights] omits. Only the
    markdown layout lives here."""
    weights = _get(cfg, "weights", src["config"])
    attrs = _get(quality, "attribute", src["attributes"])
    known = {a.get("id") for a in attrs if isinstance(a, dict)}
    for k, v in weights.items():
        _int(v, f"weights.{k}")
        if k not in known:
            raise SourceOfTruthMissing(
                f"{src['attributes']} has no attribute {k!r}")
    plan = fde_lib.probe_plan(
        fde_lib.Config(path=Path(src["config"]), raw=cfg,
                       weights=dict(weights)),
        fde_lib.Spec(invariants={}, quality=quality, domains={}, roles={}))
    lines = ["## Attack order — this project's weights, descending", ""]
    for n, step in enumerate(plan, 1):
        lines.append(f"### {n}. {step['label']} — weight {step['weight']}")
        lines.extend(f"- {probe}" for probe in step["probes"])
        lines.append("")
    return "\n".join(lines) + "\n"


def resolve(root: Path, manifest: dict, value: str) -> str:
    """`config:<dotted.key>` or `render:<name>` → the text it stands for.
    Raises `SourceOfTruthMissing` for a key or file the source lacks."""
    root = Path(root)
    if value.startswith("config:"):
        cfg_rel = manifest["sources"]["config"]
        v = _get(_toml(root, cfg_rel), value[len("config:"):], cfg_rel)
        if isinstance(v, bool) or not isinstance(v, (str, int)):
            raise SourceOfTruthMissing(f"{value} is not a string or integer")
        return str(v)
    if value.startswith("render:"):
        return _render(root, manifest, value[len("render:"):])
    raise SourceOfTruthMissing(f"unresolvable value {value!r}")


# --------------------------------------------------------------------------
# relations


_ATX = re.compile(r" {0,3}(#{1,6})(?:[ \t]|$)")
_SETEXT = re.compile(r" {0,3}(=+|-+)[ \t]*$")


def _heading_level(lines: list[str], i: int) -> int:
    """CommonMark heading level of the heading that STARTS at lines[i], 0
    if none: ATX (0-3 spaces, 1-6 `#`, then space, tab or end of line) or
    setext (a non-blank text line underlined by `=`/`-`). A replaced
    section ends at the next heading of the same OR a higher level (F12,
    F17). Code fences are not modelled: a `#` line inside one ends the
    span early, which leaves source text the copy lacks — `differs`, red."""
    line = lines[i].rstrip("\n")
    m = _ATX.match(line)
    if m:
        return len(m.group(1))
    if line.strip() and i + 1 < len(lines):
        u = _SETEXT.match(lines[i + 1].rstrip("\n"))
        if u and not line.startswith("    "):
            return 1 if u.group(1)[0] == "=" else 2
    return 0


_QUOTED_ATX = re.compile(r" {0,3}>(?:[ \t]*>)*[ \t]*#{1,6}(?:[ \t]|$)")


def _unmodelled_heading(lines: list[str], start: int) -> str | None:
    """architecture.md "Known simplifications" (F19): the recognizer looks
    one line ahead, so after the replaced heading a setext underline whose
    text line is itself preceded by a non-blank line (a multi-line or
    lazy-continuation heading paragraph), or a block-quoted heading
    (`> # …`), would move the span silently. Name the first such construct;
    the caller reports it and computes no span from it."""
    for i in range(start + 1, len(lines)):
        ln = lines[i].rstrip("\n")
        if _QUOTED_ATX.match(ln):
            return f"block-quoted heading at line {i + 1}"
        if (_SETEXT.match(ln) and i - 2 >= start and lines[i - 1].strip()
                and lines[i - 2].strip()):
            return (f"setext underline at line {i + 1} closing a multi-line "
                    f"paragraph")
    return None


def _first_diff_line(a: bytes, b: bytes) -> int:
    la, lb = a.split(b"\n"), b.split(b"\n")
    for n, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return n
    return min(len(la), len(lb)) + 1


def _count_issue(found: int, declared: int, what: str) -> tuple[str, str] | None:
    if found == 0:
        return ("stale-exception", f"{what} matches nothing in the source")
    if found != declared:
        return ("count-mismatch", f"{what} occurs {found}x, declared {declared}")
    return None


def _apply(root: Path, manifest: dict, text: str,
           excepts: list[dict]) -> tuple[str, list[tuple[str, str]]]:
    """Apply the declared exceptions, in order, to the source text. Returns
    the expected copy text and the (kind, detail) problems found."""
    problems: list[tuple[str, str]] = []
    for e in excepts:
        k = e["kind"]
        try:
            if k == "placeholder":
                issue = _count_issue(text.count(e["token"]), e["count"],
                                     f"placeholder {e['token']!r}")
                if issue:
                    problems.append(issue)
                    continue
                text = text.replace(e["token"],
                                    resolve(root, manifest, e["value"]))
            elif k == "substitute":
                issue = _count_issue(text.count(e["from"]), e["count"],
                                     f"substitute {e['from']!r}")
                if issue:
                    problems.append(issue)
                    continue
                text = text.replace(e["from"], e["to"])
            elif k == "insert":
                issue = _count_issue(text.count(e["before"]), 1,
                                     f"insert anchor {e['before']!r}")
                if issue:
                    problems.append(issue)
                    continue
                text = text.replace(e["before"], e["text"] + e["before"])
            else:  # replace-section (the vocabulary is validated)
                heading = e["heading"]
                lines = text.splitlines(keepends=True)
                hits = [i for i, ln in enumerate(lines)
                        if ln.rstrip("\n") == heading]
                issue = _count_issue(len(hits), 1, f"section {heading!r}")
                if issue:
                    problems.append(issue)
                    continue
                start = hits[0]
                construct = _unmodelled_heading(lines, start)
                if construct:
                    problems.append(("stale-exception",
                                     f"section {heading!r}: unmodelled "
                                     f"heading form after it ({construct}); "
                                     f"the span is not computed"))
                    continue
                level = len(heading) - len(heading.lstrip("#"))
                end = next((i for i in range(start + 1, len(lines))
                            if _heading_level(lines, i) in
                            range(1, level + 1)), len(lines))
                text = ("".join(lines[:start])
                        + resolve(root, manifest, e["value"])
                        + "".join(lines[end:]))
        except SourceOfTruthMissing as err:
            problems.append(("source-of-truth-missing", str(err)))
    return text, problems


class _Run:
    def __init__(self, root: Path, manifest: dict):
        self.root = Path(root)
        self.m = manifest
        self.pairs: list[dict] = manifest["pair"]
        self.ignore: list[str] = manifest["ignore"]["entries"]
        self.out: list[Violation] = []
        self.counts: dict[str, int] = {}
        self._names: dict[Path, frozenset[str]] = {}

    def exact(self, rel: str) -> bool:
        """True when every component of `rel` exists under root with this
        exact spelling. A case-insensitive filesystem (macOS APFS) answers
        `is_file()` for `Guard.py` when only `guard.py` exists; the pairing
        must not (F5): CI's filesystem is case-sensitive."""
        cur = self.root
        for part in rel.rstrip("/").split("/"):
            if cur not in self._names:
                self._names[cur] = frozenset(
                    os.listdir(cur) if cur.is_dir() else ())
            if part not in self._names[cur]:
                return False
            cur = cur / part
        return True

    def add(self, p: dict, path: str, kind: str, detail: str) -> None:
        self.out.append(Violation(p["id"], p["relation"], path, kind, detail))

    def governor(self, rel: str, side: str) -> dict | None:
        """The pair whose `side` path governs root-relative file `rel`:
        longest declared prefix wins (nested pairs override parents)."""
        best = None
        for p in self.pairs:
            decl = p[side]
            if (decl.endswith("/") and rel.startswith(decl)) or rel == decl:
                if best is None or len(decl) > len(best[side]):
                    best = p
        return best

    def walk(self, p: dict, base: str) -> list[str]:
        """Root-relative paths of the non-ignored files under `base`.
        Symlinks and special files are reported, never followed."""
        found: list[str] = []
        stack = [base.rstrip("/")]
        while stack:
            d = stack.pop()
            for child in sorted((self.root / d).iterdir()):
                rel = f"{d}/{child.name}"
                if child.is_symlink():
                    if not hidden(rel, False, self.ignore):
                        self.add(p, rel, "not-a-regular-file", "symlink")
                    continue
                if child.is_dir():
                    if not hidden(rel, True, self.ignore):
                        stack.append(rel)
                elif child.is_file():
                    if not hidden(rel, False, self.ignore):
                        found.append(rel)
                elif not hidden(rel, False, self.ignore):
                    self.add(p, rel, "not-a-regular-file", "special file")
        return sorted(found)

    def regular(self, p: dict, rel: str, missing_kind: str) -> bool:
        f = self.root / rel
        if f.is_symlink():
            self.add(p, rel, "not-a-regular-file", "symlink")
            return False
        parts = rel.split("/")[:-1]
        for n in range(1, len(parts) + 1):
            d = "/".join(parts[:n])
            if (self.root / d).is_symlink():   # F13: never resolve through
                self.add(p, rel, "not-a-regular-file",
                         f"parent {d}/ is a symlink")
                return False
        if not f.exists():
            self.add(p, rel, missing_kind, "does not exist")
            return False
        if not self.exact(rel):
            self.add(p, rel, missing_kind,
                     "exists only under another letter case")
            return False
        if not f.is_file():
            self.add(p, rel, "not-a-regular-file", "not a regular file")
            return False
        return True

    def compare(self, p: dict, src: str, cpy: str) -> None:
        if not self.regular(p, cpy, "missing-copy"):
            return
        a = (self.root / src).read_bytes()
        b = (self.root / cpy).read_bytes()
        if p["relation"] == "identical-except":
            expected, problems = _apply(self.root, self.m,
                                        a.decode("utf-8"), p["except"])
            for kind, detail in problems:
                self.add(p, src, kind, detail)
            if problems:
                return
            a = expected.encode("utf-8")
            b.decode("utf-8")  # strict: a non-UTF-8 copy raises (red)
        if a != b:
            self.add(p, cpy, "differs",
                     f"first differing line {_first_diff_line(a, b)}")

    def pair(self, p: dict) -> None:
        src, cpy = p["source"], p["copy"]
        self.counts[p["id"]] = 0
        if p["relation"] == "absent":
            s = self.root / src
            if not (s.is_dir() if src.endswith("/") else s.is_file()):
                self.add(p, src, "missing-source",
                         "the source an absent pair names does not exist")
            c = self.root / cpy.rstrip("/")
            if c.exists() or c.is_symlink():
                self.add(p, cpy, "present-but-absent",
                         "this copy must not exist")
            self.counts[p["id"]] = 1
            return
        if not src.endswith("/"):
            if self.regular(p, src, "missing-source"):
                self.compare(p, src, cpy)
                self.counts[p["id"]] = 1
            return
        sdir = self.root / src
        if sdir.is_symlink() or not sdir.is_dir():
            self.add(p, src, "missing-source", "not a directory")
            return
        files = self.walk(p, src)
        if not files:
            self.add(p, src, "empty-source", "no non-ignored file")
            return
        mine = [f for f in files if self.governor(f, "source") is p]
        for f in mine:
            self.compare(p, f, cpy + f[len(src):])
        self.counts[p["id"]] = len(mine)
        if not mine:
            self.add(p, src, "zero-checked", "every file is governed by a "
                     "nested pair")
        cdir = self.root / cpy
        if cdir.is_symlink():
            self.add(p, cpy, "not-a-regular-file", "symlink")
            return
        if not cdir.is_dir():
            return  # every source file already reported missing-copy
        for f in self.walk(p, cpy):
            if self.governor(f, "copy") is not p:
                continue
            twin = src + f[len(cpy):]
            if not ((self.root / twin).is_file() and self.exact(twin)):
                self.add(p, f, "orphan", f"no source {twin}")

    def copy_dirs(self) -> None:
        """Orphans beside the file pairs (F6): the directory holding a file
        pair's copy (`.githooks/`, `.github/workflows/`) is a copy directory
        too, so each of its files must be some pair's copy. Not walked: the
        repository root (it holds user-owned files — README, CLAUDE.md) and
        any directory a directory pair already walks. One level only."""
        declared = {q["copy"] for q in self.pairs}
        for d, owners in sibling_dirs(self.pairs).items():
            base = self.root / d
            if base.is_symlink():
                self.add(owners[0], d, "not-a-regular-file",
                         "copy directory is a symlink")
                continue
            if not base.is_dir():
                continue  # every owner already reported its missing copy
            for child in sorted(base.iterdir()):
                rel = f"{d}{child.name}"
                if hidden(rel, child.is_dir() and not child.is_symlink(),
                          self.ignore):
                    continue
                if child.is_symlink() or not (child.is_file()
                                              or child.is_dir()):
                    if rel not in declared:
                        self.add(owners[0], rel, "not-a-regular-file",
                                 "beside a declared copy")
                elif child.is_file() and rel not in declared:
                    self.add(owners[0], rel, "orphan",
                             f"no pair declares a copy at {rel}")


def sibling_dirs(pairs: list[dict]) -> dict[str, list[dict]]:
    """Directory (trailing '/') → the non-absent file pairs whose copy
    sits directly in it, for every such directory that is neither the
    repository root nor inside a directory pair's copy."""
    out: dict[str, list[dict]] = {}
    dir_copies = [q["copy"] for q in pairs if q["copy"].endswith("/")]
    for p in pairs:
        c = p["copy"]
        if c.endswith("/") or p["relation"] == "absent" or "/" not in c:
            continue
        d = c.rsplit("/", 1)[0] + "/"
        if any(d.startswith(dc) for dc in dir_copies):
            continue
        out.setdefault(d, []).append(p)
    return out


def check_with_counts(root, manifest) -> tuple[list[Violation], dict[str, int]]:
    """`check`, plus how many files each pair compared (absent: 1)."""
    root = Path(root)
    problems = _validate(manifest)
    if problems:
        return [Violation(MANIFEST, "", "", "malformed", d)
                for d in problems], {}
    run = _Run(root, manifest)
    lines = _gitignore_lines(root)
    for e in manifest["ignore"]["entries"]:
        if not _in_gitignore(e, lines):
            run.out.append(Violation(MANIFEST, "", ".gitignore",
                                     "ignore-not-in-gitignore",
                                     f"{e!r} is not a line of .gitignore"))
    for p in manifest["pair"]:
        run.pair(p)
    run.copy_dirs()
    return run.out, run.counts


def check(root, manifest) -> list[Violation]:
    """Every violation of every declared pair; [] is the only green."""
    return check_with_counts(root, manifest)[0]
