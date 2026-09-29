"""FWD-020 / ADR-0016: every source→copy pair of this self-hosted repo is
declared once, in tests/mirror.toml, and checked by one pure checker
(tests/mirror.py). This module is the only place in tests/ that compares
a source with its installed copy.

- TestRealRepo: the manifest holds on this repository, every pair checks
  at least one file, in under 2 s (R9).
- TestFailClosed: fixtures with one known violation each (R1, R3, R4).
- TestMutationSuite: for every pair iterated from the manifest — never a
  hand list — a temp copy of the pair's real files goes red on each
  mutation (R5); a slice of this repository with new pairs added by
  manifest lines goes through every real-repo check below (mutations,
  agreement, dropped-pair, inventory, marker) with zero test-code change.
- TestIgnore: runtime output and agent worktrees are not copies (R7).
- TestIgnoreNeverSilencesATrackedFile: no [ignore] entry matches a file
  git tracks (F9) — the one test here that runs git, outside the checker.
- TestAgreement: the manifest agrees with [erosion].generated_paths and
  SETUP's install destinations, so a dropped pair is noticed (R8).
- TestGeneratedMarker*: markers in generated pairs are SETUP §6's whole
  block (F7, F11).
- TestAttackOrderIsTheKernelsPlan: render:attack_order formats
  fde_lib.probe_plan, ties and floors included (F2).
- TestStaleAttackOrder: the drift this demand found (FM-15, R12).
- TestInventoryMapping: where each retired D1-D13 protection and each
  G1-G10 gap lives now (INVENTORY), resolved against the live suite.
"""
from __future__ import annotations

import copy as _copy
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
import unittest
from pathlib import Path

import mirror

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "tests" / "mirror.toml"


def real_manifest() -> dict:
    return mirror.load(MANIFEST_PATH)


def pair_by_id(manifest: dict, pid: str) -> dict:
    return next(p for p in manifest["pair"] if p["id"] == pid)


def kinds(violations, pid: str | None = None) -> set[str]:
    return {v.kind for v in violations if pid is None or v.pair == pid}


def fmt(violations) -> str:
    return "\n".join(f"  {v.pair} [{v.relation}] {v.path}: {v.kind} — "
                     f"{v.detail}" for v in violations) or "  (none)"


# --------------------------------------------------------------------------
# fixture building


def files_under(root: Path, rel: str, ignore: list[str]) -> list[str]:
    """Root-relative non-ignored regular files under directory `rel`."""
    out = []
    base = root / rel
    for dirpath, dirnames, filenames in os.walk(base):
        d = Path(dirpath).relative_to(root).as_posix()
        dirnames[:] = sorted(n for n in dirnames
                             if not mirror.hidden(f"{d}/{n}", True, ignore))
        for n in sorted(filenames):
            r = f"{d}/{n}"
            if not mirror.hidden(r, False, ignore):
                out.append(r)
    return out


def copy_rel(src_root: Path, dst_root: Path, rel: str) -> None:
    dst = dst_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_root / rel, dst)


def sub_manifest(manifest: dict, pair: dict) -> dict:
    """The pair plus every pair nested inside its source directory."""
    pairs = [q for q in manifest["pair"] if q is pair or (
        pair["source"].endswith("/") and q["source"].startswith(pair["source"]))]
    m = {k: _copy.deepcopy(v) for k, v in manifest.items() if k != "pair"}
    m["pair"] = _copy.deepcopy(pairs)
    return m


def build_pair_root(src_root: Path, manifest: dict, pair: dict,
                    dst: Path) -> dict:
    """A temp root holding only this pair (and its nested pairs), the
    declared sources of truth and .gitignore. Returns its sub-manifest."""
    ignore = manifest["ignore"]["entries"]
    for rel in list(manifest["sources"].values()) + [".gitignore"]:
        if (src_root / rel).is_file():
            copy_rel(src_root, dst, rel)
    for side in ("source", "copy"):
        rel = pair[side]
        if rel.endswith("/"):
            if (src_root / rel).is_dir():
                for f in files_under(src_root, rel, ignore):
                    copy_rel(src_root, dst, f)
        elif (src_root / rel).is_file():
            copy_rel(src_root, dst, rel)
    return sub_manifest(manifest, pair)


def governed_copy_files(root: Path, manifest: dict, pair: dict) -> list[str]:
    """Copy-side files this pair itself (not a nested pair) governs."""
    if not pair["copy"].endswith("/"):
        return [pair["copy"]]
    run = mirror._Run(root, manifest)
    return [f for f in files_under(root, pair["copy"],
                                   manifest["ignore"]["entries"])
            if run.governor(f, "copy") is pair]


def pick(text: str, lo: int, hi: int) -> int:
    """Index of an ASCII letter/digit in text[lo:hi], starting mid-range."""
    mid = (lo + hi) // 2
    for i in list(range(mid, hi)) + list(range(lo, mid)):
        if text[i].isascii() and text[i].isalnum():
            return i
    raise AssertionError(f"no ASCII alnum char in [{lo}, {hi})")


def flip_at(text: str, i: int) -> str:
    return text[:i] + ("y" if text[i] == "x" else "x") + text[i + 1:]


def exception_span_text(root: Path, manifest: dict, e: dict) -> str:
    if e["kind"] in ("placeholder", "replace-section"):
        return mirror.resolve(root, manifest, e["value"])
    return e["to"] if e["kind"] == "substitute" else e["text"]


def exception_spans(root: Path, manifest: dict, pair: dict) -> list[tuple[int, int]]:
    """(start, end) of every exception's output in the copy text, located
    by applying the exceptions to a sentinel-marked source — not by
    searching the copy, which could hit an identical string elsewhere."""
    source = (root / pair["source"]).read_text(encoding="utf-8")
    copy_text = (root / pair["copy"]).read_text(encoding="utf-8")
    spans = []
    for idx, e in enumerate(pair["except"]):
        marked = source
        if e["kind"] == "placeholder":
            marked = marked.replace(e["token"], "\x00" + e["token"], 1)
        elif e["kind"] == "substitute":
            marked = marked.replace(e["from"], "\x00" + e["from"], 1)
        elif e["kind"] == "insert":
            marked = marked.replace(e["before"], "\x00" + e["before"], 1)
        else:
            # the heading line itself is replaced, so the sentinel goes
            # just before the previous line's newline
            lines = marked.splitlines(keepends=True)
            at = next(i for i, ln in enumerate(lines)
                      if ln.rstrip("\n") == e["heading"])
            if at:
                lines[at - 1] = lines[at - 1][:-1] + "\x00\n"
            marked = "".join(lines)
        out, problems = mirror._apply(root, manifest, marked, pair["except"])
        assert not problems, problems
        assert out.replace("\x00", "") == copy_text, "sentinel changed output"
        if "\x00" not in out:
            start = 0                      # section at the top of the file
        else:
            start = out.index("\x00") + (e["kind"] == "replace-section")
        spans.append((start, start + len(exception_span_text(
            root, manifest, pair["except"][idx]))))
    return spans


def mutations(root: Path, manifest: dict):
    """Yield (pair id, label, expected kind, mutate(temp_root)) for every
    pair of the manifest. Driven entirely by the manifest: a new pair gets
    its cases with no change here."""
    beside = mirror.sibling_dirs(manifest["pair"])
    for pair in manifest["pair"]:
        pid, rel = pair["id"], pair["relation"]
        if rel == "absent":
            target = pair["copy"] + ("SKILL.md" if pair["copy"].endswith("/")
                                     else "")

            def create(t, target=target):
                (t / target).parent.mkdir(parents=True, exist_ok=True)
                (t / target).write_text("installed anyway\n", encoding="utf-8")
            yield pid, "forbidden copy created", "present-but-absent", create
            continue
        targets = governed_copy_files(root, manifest, pair)
        assert targets, f"{pid}: no copy file to mutate"
        target = targets[len(targets) // 2]

        def byte(t, target=target):
            b = (t / target).read_bytes()
            text = b.decode("latin-1")
            i = pick(text, 0, len(text))
            (t / target).write_bytes(flip_at(text, i).encode("latin-1"))
        yield pid, f"one byte changed in {target}", "differs", byte

        def delete(t, target=target):
            (t / target).unlink()
        yield pid, f"{target} deleted", "missing-copy", delete

        if pair["copy"].endswith("/"):
            def orphan(t, base=pair["copy"]):
                (t / base / "zz-orphan.dat").write_bytes(b"\x00orphan")
            yield pid, "orphan added under the copy root", "orphan", orphan
        elif pair["copy"].rsplit("/", 1)[0] + "/" in beside:
            def stray(t, base=pair["copy"].rsplit("/", 1)[0]):
                (t / base / "zz-orphan.dat").write_bytes(b"\x00orphan")
            yield pid, "orphan added beside the copy", "orphan", stray

        if rel != "identical-except":
            continue
        copy_text = (root / pair["copy"]).read_text(encoding="utf-8")
        spans = exception_spans(root, manifest, pair)
        inside = {i for s, e in spans for i in range(s, e)}
        outside = [i for i, c in enumerate(copy_text)
                   if i not in inside and c.isascii() and c.isalnum()]
        assert outside, f"{pid}: no un-excepted text to mutate"

        def out_region(t, i=outside[len(outside) // 2], cp=pair["copy"]):
            text = (t / cp).read_text(encoding="utf-8")
            (t / cp).write_text(flip_at(text, i), encoding="utf-8")
        yield pid, "one byte changed outside every exception", "differs", \
            out_region

        for n, ((s, e), exc) in enumerate(zip(spans, pair["except"])):
            def in_region(t, i=pick(copy_text, s, e), cp=pair["copy"]):
                text = (t / cp).read_text(encoding="utf-8")
                (t / cp).write_text(flip_at(text, i), encoding="utf-8")
            yield pid, f"one byte changed inside except[{n}] " \
                f"({exc['kind']})", "differs", in_region

            def stale(t, exc=exc, sp=pair["source"], m=manifest):
                text = (t / sp).read_text(encoding="utf-8")
                k = exc["kind"]
                if k == "placeholder":
                    text = text.replace(exc["token"],
                                        mirror.resolve(t, m, exc["value"]))
                elif k == "substitute":
                    text = text.replace(exc["from"], exc["to"])
                elif k == "insert":
                    text = text.replace(exc["before"], "")
                else:
                    text = text.replace(exc["heading"] + "\n",
                                        exc["heading"] + " (renamed)\n")
                (t / sp).write_text(text, encoding="utf-8")
            yield pid, f"except[{n}] ({exc['kind']}) made stale", \
                "stale-exception", stale


class MirrorCase(unittest.TestCase):
    def assert_clean(self, root: Path, manifest: dict) -> dict[str, int]:
        violations, counts = mirror.check_with_counts(root, manifest)
        self.assertEqual(violations, [], "\n" + fmt(violations))
        for p in manifest["pair"]:
            self.assertGreaterEqual(counts.get(p["id"], 0), 1,
                                    f"{p['id']} checked no file")
        return counts

    def run_mutations(self, root: Path, manifest: dict) -> dict[str, int]:
        """Every mutation of every pair must go red with the expected kind
        on that pair. Returns cases run per pair."""
        ran: dict[str, int] = {}
        bases: dict[str, tuple[Path, dict]] = {}
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for pid, label, kind, mutate in mutations(root, manifest):
                if pid not in bases:
                    base = tmp / f"base-{pid}"
                    sub = build_pair_root(root, manifest,
                                          pair_by_id(manifest, pid), base)
                    with self.subTest(pair=pid, mutation="(unmutated base)"):
                        self.assertEqual(mirror.check(base, sub), [],
                                         fmt(mirror.check(base, sub)))
                    bases[pid] = (base, sub)
                base, sub = bases[pid]
                n = ran.get(pid, 0)
                work = tmp / f"m-{pid}-{n}"
                shutil.copytree(base, work, symlinks=True)
                mutate(work)
                got = mirror.check(work, sub)
                with self.subTest(pair=pid, mutation=label):
                    self.assertIn(kind, kinds(got, pid),
                                  f"{label}: expected {kind}\n{fmt(got)}")
                ran[pid] = n + 1
        return ran


class TestRealRepo(MirrorCase):
    def test_every_declared_pair_holds_on_this_repo(self):
        counts = self.assert_clean(ROOT, real_manifest())
        # the walks actually walked: not a vacuous pass (D1's old pin)
        self.assertGreaterEqual(counts["runtime"], 9)
        self.assertGreaterEqual(counts["skills"], 12)

    def test_whole_check_runs_under_two_seconds(self):
        m = real_manifest()
        t0 = time.perf_counter()
        mirror.check(ROOT, m)
        self.assertLess(time.perf_counter() - t0, 2.0)

    def test_manifest_lives_once_under_eval_paths_and_is_never_installed(self):
        cfg = tomllib.loads((ROOT / "fde.config.toml").read_text("utf-8"))
        self.assertTrue(any("tests/mirror.toml".startswith(p)
                            for p in cfg["gate"]["eval_paths"]))
        # one copy: nothing named like it where copies or installs live
        for base in ("spec", ".fde", "templates", "bin", ".claude/skills",
                     ".claude/agents", "runtime"):
            self.assertEqual(list((ROOT / base).rglob("mirror*")), [], base)
        self.assertNotIn("mirror.toml",
                         (ROOT / "SETUP.md").read_text(encoding="utf-8"))

    def test_verified_regions_catch_plausible_wrong_values(self):
        # FM-7 examples named in acceptance: a weight in the attack order,
        # a stale per-weight BLOCKS MERGE tag (ADR-0018 removed it), a
        # probe line, an invariant statement, a weight
        m = real_manifest()
        cases = [
            (".claude/agents/fde-adversarial.md",
             "Functional correctness — weight 30\n",
             "Functional correctness — weight 29\n", "adversarial-role"),
            (".claude/agents/fde-adversarial.md",
             "evolvability — weight 22\n",
             "evolvability — weight 22 — BLOCKS MERGE\n",
             "adversarial-role"),
            (".claude/agents/fde-adversarial.md",
             "- state change with no visible feedback\n", "",
             "adversarial-role"),
            ("AGENTS.md", "It never receives the context",
             "It rarely receives the context", "agents-md"),
            ("AGENTS.md", "- maintainability: 22", "- maintainability: 21",
             "agents-md"),
            ("AGENTS.md", "- software_architecture: 1\n", "", "agents-md"),
            (".github/workflows/fde-gate.yml", "discover -s tests",
             "discover -s test", "workflow"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for n, (rel, old, new, pid) in enumerate(cases):
                with self.subTest(pid=pid, old=old):
                    work = Path(tmp) / str(n)
                    sub = build_pair_root(ROOT, m, pair_by_id(m, pid), work)
                    text = (work / rel).read_text(encoding="utf-8")
                    self.assertEqual(text.count(old), 1, old)
                    (work / rel).write_text(text.replace(old, new),
                                            encoding="utf-8")
                    self.assertIn("differs", kinds(mirror.check(work, sub),
                                                   pid))


# --------------------------------------------------------------------------


def write(root: Path, rel: str, text: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


FIXTURE_CONFIG = """\
[project]
name = "fixture"
[stack]
test_command = "make test"
"""


def fixture(root: Path, pairs: list[dict], files: dict[str, str],
            ignore=("__pycache__/",)) -> dict:
    write(root, ".gitignore", "".join(f"{e}\n" for e in ignore))
    write(root, "cfg.toml", FIXTURE_CONFIG)
    for rel, text in files.items():
        write(root, rel, text)
    return {"meta": {"schema": 1},
            "sources": {"config": "cfg.toml", "invariants": "inv.toml",
                        "attributes": "qa.toml"},
            "ignore": {"entries": list(ignore)},
            "pair": pairs}


def pair(pid, source, copy, relation="identical", **kw) -> dict:
    return {"id": pid, "source": source, "copy": copy, "relation": relation,
            **kw}


class TestFailClosed(unittest.TestCase):
    """Each fixture carries one known violation and must report exactly
    that kind (R1, R3, R4, FM-6, FM-14)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def only(self, manifest, kind, pid=None):
        got = mirror.check(self.root, manifest)
        self.assertTrue(got, f"expected {kind}, got a clean pass")
        self.assertEqual(kinds(got), {kind}, fmt(got))
        if pid is not None:
            self.assertEqual({v.pair for v in got}, {pid}, fmt(got))
        for v in got:
            self.assertIn(v.kind, mirror.KINDS)
        return got

    def test_clean_fixture_is_clean(self):
        m = fixture(self.root, [pair("d", "s/", "c/")],
                    {"s/a.txt": "a\n", "c/a.txt": "a\n"})
        self.assertEqual(mirror.check(self.root, m), [])

    def test_empty_source_root(self):
        m = fixture(self.root, [pair("d", "s/", "c/")],
                    {"s/__pycache__/x.pyc": "ignored only\n"})
        self.only(m, "empty-source", "d")

    def test_missing_source_root(self):
        m = fixture(self.root, [pair("d", "s/", "c/")], {"c/a.txt": "a\n"})
        self.only(m, "missing-source", "d")

    def test_missing_source_file(self):
        m = fixture(self.root, [pair("f", "s.txt", "c.txt")], {"c.txt": "x"})
        self.only(m, "missing-source", "f")

    def test_zero_checked_when_nested_pairs_govern_everything(self):
        m = fixture(self.root, [pair("d", "s/", "c/"),
                                pair("n", "s/only.txt", "c/only.txt")],
                    {"s/only.txt": "x\n", "c/only.txt": "x\n"})
        self.only(m, "zero-checked", "d")

    def test_missing_copy_and_orphan_all_file_types(self):
        m = fixture(self.root, [pair("d", "s/", "c/")],
                    {"s/a.py": "a\n", "c/x.bin": "stray\n"})
        got = mirror.check(self.root, m)
        self.assertEqual(kinds(got), {"missing-copy", "orphan"}, fmt(got))

    def test_unknown_relation(self):
        m = fixture(self.root, [pair("d", "s/", "c/", "skip")],
                    {"s/a": "a", "c/a": "a"})
        self.only(m, "malformed", mirror.MANIFEST)

    def test_unknown_exception_kind(self):
        m = fixture(self.root, [pair("f", "s.txt", "c.txt", "identical-except",
                                     **{"except": [{"kind": "regex",
                                                    "pattern": ".*"}]})],
                    {"s.txt": "a", "c.txt": "a"})
        self.only(m, "malformed")

    def test_extra_keys_are_malformed(self):
        base = {"s.txt": "a", "c.txt": "a"}
        m = fixture(self.root, [pair("f", "s.txt", "c.txt", skip=True)], base)
        self.only(m, "malformed")
        m = fixture(self.root, [pair("f", "s.txt", "c.txt")], base)
        m["globs"] = {"x": "*"}
        self.only(m, "malformed")
        m = fixture(self.root, [pair("f", "s.txt", "c.txt", "identical-except",
                                     **{"except": [{
                                         "kind": "substitute", "from": "a",
                                         "to": "b", "count": 1,
                                         "regex": True}]})], base)
        self.only(m, "malformed")

    def test_schema_shape_rules_are_malformed(self):
        base = {"s.txt": "a", "c.txt": "a"}
        bad = [
            [pair("f", "s.txt", "c.txt", "identical-except")],  # no except
            [pair("f", "s.txt", "c.txt", **{"except": [
                {"kind": "substitute", "from": "a", "to": "b", "count": 1}]})],
            [pair("f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "substitute", "from": "a", "to": "b", "count": 0}]})],
            [pair("f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "placeholder", "token": "a", "count": 1,
                 "value": "render:nope"}]})],
            [pair("f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "placeholder", "token": "a", "count": 1,
                 "value": "a"}]})],
            [pair("f", "../s.txt", "c.txt")],
            [pair("f", "/abs/s.txt", "c.txt")],
            [pair("f", "s.txt", "c/")],
            [pair("F!", "s.txt", "c.txt")],
            [pair("f", "s.txt", "c.txt"), pair("f", "s.txt", "d.txt")],
            [pair("f", "s.txt", "c.txt"), pair("g", "s.txt", "d.txt")],
            [pair("f", "s.txt", "c.txt", "absent", erosion_measured=True)],
            [pair("d", "s/", "c/"), pair("n", "s/a", "elsewhere/a")],
            [pair("d", "s/", "c/"), pair("e", "t/", "c/sub/")],
            [],
        ]
        for pairs in bad:
            with self.subTest(pairs=pairs):
                self.only(fixture(self.root, pairs, base), "malformed")
        m = fixture(self.root, [pair("f", "s.txt", "c.txt")], base)
        m["meta"]["schema"] = 2
        self.only(m, "malformed")
        for glob in ("*.py[co]", "*", "a*.pyc", "*.p?c", "*.pyc/", "**/*.pyc"):
            with self.subTest(ignore=glob):
                m = fixture(self.root, [pair("f", "s.txt", "c.txt")], base,
                            ignore=(glob,))
                self.only(m, "malformed")

    def test_stale_placeholder(self):
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "placeholder", "token": "{{PROJECT_NAME}}",
                 "count": 1, "value": "config:project.name"}]})],
            {"s.txt": "# fixture\n", "c.txt": "# fixture\n"})
        self.only(m, "stale-exception", "f")

    def test_wrong_count(self):
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "substitute", "from": "DEM-1", "to": "FWD-1",
                 "count": 1}]})],
            {"s.txt": "DEM-1 DEM-1\n", "c.txt": "FWD-1 FWD-1\n"})
        self.only(m, "count-mismatch", "f")

    def test_insert_anchor_must_be_unique_and_section_must_exist(self):
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "insert", "before": "x\n", "text": "hdr\n"}]})],
            {"s.txt": "x\nx\n", "c.txt": "hdr\nx\nx\n"})
        self.only(m, "count-mismatch", "f")
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "replace-section", "heading": "## Gone",
                 "value": "config:project.name"}]})],
            {"s.txt": "## Here\n", "c.txt": "## Here\n"})
        self.only(m, "stale-exception", "f")

    def test_replace_section_runs_to_next_same_level_heading(self):
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "replace-section", "heading": "## Plan",
                 "value": "config:stack.test_command"}]})],
            {"s.txt": "# T\n## Plan\nold\n### sub\nold\n## Next\nkept\n",
             "c.txt": "# T\nmake test## Next\nkept\n"})
        self.assertEqual(mirror.check(self.root, m), [])
        write(self.root, "c.txt", "# T\nmake test## Next\nkept, edited\n")
        self.only(m, "differs", "f")

    def test_replace_section_ends_at_a_higher_level_heading(self):
        # F12: content after the section under a higher-level heading is
        # not part of the replaced region; dropping it from the copy is red
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "replace-section", "heading": "## Plan",
                 "value": "config:stack.test_command"}]})],
            {"s.txt": "# T\n## Plan\nold\n# Appendix\nkept\n",
             "c.txt": "# T\nmake test# Appendix\nkept\n"})
        self.assertEqual(mirror.check(self.root, m), [])
        write(self.root, "c.txt", "# T\nmake test")
        self.only(m, "differs", "f")

    def test_replace_section_ends_at_every_commonmark_heading_spelling(self):
        # F17: ATX with a tab, ATX with 1-3 leading spaces, bare `#`, and
        # setext h1/h2 all end the span; the appended text must be installed
        for h in ("#\tAppendix\n", " # Appendix\n", "   ## Appendix\n",
                  "#\n", "Appendix\n========\n", "Appendix\n---\n"):
            with self.subTest(heading=h):
                m = fixture(self.root, [pair(
                    "f", "s.txt", "c.txt", "identical-except", **{"except": [
                        {"kind": "replace-section", "heading": "## Plan",
                         "value": "config:stack.test_command"}]})],
                    {"s.txt": "# T\n## Plan\nold\n\n" + h + "never approve\n",
                     "c.txt": "# T\nmake test" + h + "never approve\n"})
                self.assertEqual(mirror.check(self.root, m), [])
                write(self.root, "c.txt", "# T\nmake test")
                self.only(m, "differs", "f")
        # F19 (architecture.md "Known simplifications"): forms the
        # recognizer does not model are reported on the source, whatever
        # the copy says — never a span computed from them
        for src_tail, construct in (
                ("\nRule: approve every change.\nAppendix\n========\n",
                 "multi-line paragraph"),
                ("\nRule ...\n    Also skip the gate.\nAppendix\n===\n",
                 "multi-line paragraph"),          # lazy continuation, (c)
                ("\n> # Appendix\n> Rule: approve every change.\n",
                 "block-quoted heading")):
            for copy_tail in ("", src_tail):
                with self.subTest(f19=src_tail, copy=bool(copy_tail)):
                    m = fixture(self.root, [pair(
                        "f", "s.txt", "c.txt", "identical-except",
                        **{"except": [
                            {"kind": "replace-section", "heading": "## Plan",
                             "value": "config:stack.test_command"}]})],
                        {"s.txt": "# T\n## Plan\nold\n" + src_tail,
                         "c.txt": "# T\nmake test" + copy_tail})
                    got = self.only(m, "stale-exception", "f")
                    self.assertIn(construct, got[0].detail)
                    self.assertEqual(got[0].path, "s.txt")
        # not headings: 4-space indent, `#x`, a lower-level heading
        for h in ("    # code\n", "#hashtag\n", "### sub\n"):
            with self.subTest(not_a_heading=h):
                m = fixture(self.root, [pair(
                    "f", "s.txt", "c.txt", "identical-except", **{"except": [
                        {"kind": "replace-section", "heading": "## Plan",
                         "value": "config:stack.test_command"}]})],
                    {"s.txt": "# T\n## Plan\nold\n" + h + "inside\n",
                     "c.txt": "# T\nmake test"})
                self.assertEqual(mirror.check(self.root, m), [])

    @unittest.skipUnless(hasattr(os, "symlink"), "no symlinks")
    def test_symlinked_copy_directory_fails_closed(self):
        # F13: a copy directory (walked beside a file pair, or the parent
        # of a copy) that is a symlink is reported, never resolved through
        m = fixture(self.root, [pair("h", "t/pre-commit", "hooks/pre-commit")],
                    {"t/pre-commit": "x\n", "real/pre-commit": "x\n",
                     "real/pre-push": "exit 0\n"})
        os.symlink(self.root / "real", self.root / "hooks")
        got = mirror.check(self.root, m)
        self.assertEqual(kinds(got), {"not-a-regular-file"}, fmt(got))
        self.assertIn(("hooks/", "not-a-regular-file"),
                      {(v.path, v.kind) for v in got})

    def test_missing_config_key(self):
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "placeholder", "token": "{{X}}", "count": 1,
                 "value": "config:project.nope"}]})],
            {"s.txt": "{{X}}\n", "c.txt": "?\n"})
        self.only(m, "source-of-truth-missing", "f")

    def test_ignore_entry_absent_from_gitignore(self):
        m = fixture(self.root, [pair("d", "s/", "c/")],
                    {"s/a": "a", "c/a": "a"})
        m["ignore"]["entries"].append(".claude/worktrees/")
        self.only(m, "ignore-not-in-gitignore", mirror.MANIFEST)

    def test_suffix_ignore_is_narrow_and_must_be_gitignored(self):
        # F4 / R7: `*.pyc` is output git ignores (`*.py[co]`), not a copy
        m = fixture(self.root, [pair("d", "s/", "c/")],
                    {"s/a.py": "a\n", "c/a.py": "a\n", "s/a.pyc": "\x00",
                     "c/deep/b.pyc": "\x00"}, ignore=("*.py[co]",))
        m["ignore"]["entries"] = ["*.pyc"]
        self.assertEqual(mirror.check(self.root, m), [])
        write(self.root, "c/a.pyc.bak", "stray\n")      # suffix, not substring
        self.only(m, "orphan", "d")
        (self.root / "c" / "a.pyc.bak").unlink()
        write(self.root, ".gitignore", "__pycache__/\n")  # no longer ignored
        self.only(m, "ignore-not-in-gitignore", mirror.MANIFEST)

    def test_pairing_is_case_exact(self):
        # F5: on a case-insensitive filesystem Guard.py "is" guard.py; the
        # checker must not say so, since CI's filesystem disagrees
        m = fixture(self.root, [pair("d", "s/", "c/")],
                    {"s/Guard.py": "g\n", "c/guard.py": "g\n"})
        got = mirror.check(self.root, m)
        self.assertEqual({(v.path, v.kind) for v in got},
                         {("c/Guard.py", "missing-copy"),
                          ("c/guard.py", "orphan")}, fmt(got))
        m = fixture(self.root, [pair("f", "t/Hook", "h/hook")],
                    {"t/Hook": "x\n", "h/Hook": "x\n"})
        (self.root / "c").exists() and shutil.rmtree(self.root / "c")
        self.assertIn("missing-copy", kinds(mirror.check(self.root, m), "f"))

    def test_files_beside_a_file_pair_copy_are_orphans(self):
        # F6: the directory holding a file pair's copy is walked one level;
        # the repository root is not
        m = fixture(self.root, [pair("h", "t/pre-commit", "hooks/pre-commit"),
                                pair("r", "t/README", "README")],
                    {"t/pre-commit": "x\n", "hooks/pre-commit": "x\n",
                     "t/README": "r\n", "README": "r\n",
                     "user-notes.md": "the root is user-owned\n",
                     "hooks/sub/deeper.sh": "one level only\n"})
        self.assertEqual(mirror.check(self.root, m), [])
        write(self.root, "hooks/pre-push", "stray, and it would execute\n")
        self.only(m, "orphan", "h")
        m["pair"].append(pair("p", "t/pre-push", "hooks/pre-push"))
        write(self.root, "t/pre-push", "stray, and it would execute\n")
        self.assertEqual(mirror.check(self.root, m), [])

    def test_absent_pair(self):
        m = fixture(self.root, [pair("d", "s/", "c/"),
                                pair("x", "s/init/", "c/init/", "absent")],
                    {"s/a": "a", "c/a": "a", "s/init/SKILL.md": "i"})
        self.assertEqual(mirror.check(self.root, m), [])
        write(self.root, "c/init/SKILL.md", "i")
        self.only(m, "present-but-absent", "x")
        shutil.rmtree(self.root / "c" / "init")
        shutil.rmtree(self.root / "s" / "init")
        self.only(m, "missing-source", "x")  # a stale absent is red too

    @unittest.skipUnless(hasattr(os, "symlink"), "no symlinks")
    def test_symlink_is_not_a_regular_file(self):
        m = fixture(self.root, [pair("d", "s/", "c/")],
                    {"s/a": "a", "c/b": "a"})
        os.symlink(self.root / "c" / "b", self.root / "c" / "a")
        (self.root / "c" / "b").unlink()
        got = mirror.check(self.root, m)
        self.assertIn("not-a-regular-file", kinds(got), fmt(got))

    def test_checker_errors_propagate_never_pass(self):
        # a decode error inside the checker raises (the test errors, red);
        # it is never swallowed into an empty result
        m = fixture(self.root, [pair(
            "f", "s.txt", "c.txt", "identical-except", **{"except": [
                {"kind": "substitute", "from": "a", "to": "b", "count": 1}]})],
            {"c.txt": "b"})
        (self.root / "s.txt").write_bytes(b"a\xff")
        with self.assertRaises(UnicodeDecodeError):
            mirror.check(self.root, m)


class TestMutationSuite(MirrorCase):
    def test_every_manifest_pair_goes_red_on_every_mutation(self):
        m = real_manifest()
        ran = self.run_mutations(ROOT, m)
        # iterated from the manifest: every pair got cases, and the
        # identical-except pairs got their region and staleness cases
        self.assertEqual(set(ran), {p["id"] for p in m["pair"]})
        for p in m["pair"]:
            minimum = {"absent": 1, "identical": 2}.get(p["relation"])
            if minimum is None:
                minimum = 3 + 2 * len(p["except"])
            if p["relation"] != "absent" and (
                    p["copy"].endswith("/") or any(
                        p in owners for owners in
                        mirror.sibling_dirs(m["pair"]).values())):
                minimum += 1
            self.assertGreaterEqual(ran[p["id"]], minimum, p["id"])

    def test_a_new_pair_needs_zero_test_code(self):
        # The headline claim, executed on the real suite's code paths (F1):
        # a slice of this repository with new pairs of every relation added
        # by manifest lines alone — plus a SETUP §6 line only for the pairs
        # nothing else outside the manifest would notice being dropped —
        # goes through the real-repo check, the mutation suite, the R8
        # agreement, the dropped-pair check, the inventory check and the
        # marker check with no change to this file.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_slice(root, real_manifest())
            hook = "#!/bin/sh\nexec python3 bin/fde/verify.py --gate eval\n"
            write(root, "templates/zz-hook", hook)
            write(root, ".githooks/zz-hook", hook)
            write(root, "docs-src/a.md", "# a\n")
            write(root, "docs-src/deep/b.cfg", "k = 1\n")
            write(root, "docs-src/private/n.md", "never installed\n")
            write(root, "out/a.md", "# a\n")
            write(root, "out/deep/b.cfg", "k = 1\n")
            write(root, "tpl/readme.tmpl",
                  "# {{NAME}}\nrun `{{CMD}}` (see DEM-7)\n")
            write(root, "README.gen.md",
                  "# forward\nrun `python3 -m unittest discover -s tests` "
                  "(see FWD-7)\n")
            setup = (root / "SETUP.md").read_text(encoding="utf-8")
            setup_lines = ("- `docs-src/` → `out/`\n"
                           "- `tpl/readme.tmpl` → `README.gen.md`\n")
            write(root, "SETUP.md", setup.replace(
                "\n## 7.", "\n" + setup_lines + "\n## 7.", 1))
            write(root, "tests/mirror.toml",
                  MANIFEST_PATH.read_text(encoding="utf-8") + NEW_PAIRS)
            m = mirror.load(root / "tests" / "mirror.toml")
            new = {"zz-hook", "docs", "docs-private", "readme"}
            self.assertLess(new, {p["id"] for p in m["pair"]})

            self.assert_clean(root, m)
            ran = self.run_mutations(root, m)
            self.assertEqual(set(ran), {p["id"] for p in m["pair"]})
            self.assertEqual(ran["readme"], 3 + 2 * 3)
            self.assertEqual(ran["zz-hook"], 3)   # byte, delete, beside
            self.assertEqual(agreement(root, m), [])
            self.assertEqual(drop_unnoticed(root, m), [])
            self.assertEqual(inventory_problems(m), [])
            self.assertEqual(marker_problems(root, m), [])

            # and the one legitimate non-manifest line is enforced, not
            # decorative: without it, dropping those pairs goes unnoticed
            write(root, "SETUP.md", setup)
            self.assertEqual(sorted(drop_unnoticed(root, m)),
                             ["docs", "readme"])


NEW_PAIRS = """
[[pair]]
id = "zz-hook"
source = "templates/zz-hook"
copy = ".githooks/zz-hook"
relation = "identical"
erosion_measured = true

[[pair]]
id = "docs"
source = "docs-src/"
copy = "out/"
relation = "identical"
erosion_measured = true

[[pair]]
id = "docs-private"
source = "docs-src/private/"
copy = "out/private/"
relation = "absent"

[[pair]]
id = "readme"
source = "tpl/readme.tmpl"
copy = "README.gen.md"
relation = "identical-except"

  [[pair.except]]
  kind = "placeholder"
  token = "{{NAME}}"
  count = 1
  value = "config:project.name"

  [[pair.except]]
  kind = "placeholder"
  token = "{{CMD}}"
  count = 1
  value = "config:stack.test_command"

  [[pair.except]]
  kind = "substitute"
  from = "DEM-7"
  to = "FWD-7"
  count = 1
"""


def repo_slice(dst: Path, manifest: dict) -> None:
    """The files of this repository the real-repo tests read: every pair's
    source and copy, the sources of truth, .gitignore, SETUP.md,
    fde.config.toml and every [erosion].generated_paths tree."""
    ignore = manifest["ignore"]["entries"]
    cfg = tomllib.loads((ROOT / "fde.config.toml").read_text("utf-8"))
    for rel in list(manifest["sources"].values()) + [
            ".gitignore", "SETUP.md", "fde.config.toml"]:
        copy_rel(ROOT, dst, rel)
    trees = [p[side] for p in manifest["pair"] for side in ("source", "copy")]
    for rel in trees + list(cfg["erosion"]["generated_paths"]):
        if rel.endswith("/"):
            if (ROOT / rel).is_dir():
                for f in files_under(ROOT, rel, ignore):
                    copy_rel(ROOT, dst, f)
        elif (ROOT / rel).is_file():
            copy_rel(ROOT, dst, rel)


class TestIgnore(unittest.TestCase):
    """R7 / FM-11: runtime output and agent worktrees are not copies; an
    untracked, non-ignored file under a copy root is an orphan."""

    def test_ignored_paths_are_neither_orphans_nor_sources(self):
        m = real_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_rel(ROOT, root, ".gitignore")
            fx = {"meta": m["meta"], "sources": m["sources"],
                  "ignore": m["ignore"], "pair": [
                      pair("runtime", "runtime/", "bin/fde/"),
                      pair("claude", "claude-src/", ".claude/"),
                      pair("fde", "fde-src/", ".fde/")]}
            for rel in ("runtime/a.py", "bin/fde/a.py",
                        "claude-src/settings.json", ".claude/settings.json",
                        "fde-src/spec/x.toml", ".fde/spec/x.toml"):
                write(root, rel, "same\n")
            for rel in ("runtime/__pycache__/a.cpython-311.pyc",
                        "runtime/a.pyc", "bin/fde/legacy.pyc",
                        "bin/fde/__pycache__/a.cpython-311.pyc",
                        ".claude/worktrees/agent-1/runtime/a.py",
                        ".claude/worktrees/agent-1/.claude/skills/s/SKILL.md",
                        ".fde/guard-audit.jsonl",
                        ".claude/.DS_Store", "claude-src/.DS_Store"):
                write(root, rel, "noise\n")
            self.assertEqual(mirror.check(root, fx), [],
                             fmt(mirror.check(root, fx)))
            # narrow: the same names elsewhere are NOT ignored
            write(root, ".claude/sub/worktrees/x.md", "stray\n")
            write(root, ".fde/guard-audit.jsonl.bak", "stray\n")
            got = mirror.check(root, fx)
            self.assertEqual({(v.path, v.kind) for v in got},
                             {(".claude/sub/worktrees/x.md", "orphan"),
                              (".fde/guard-audit.jsonl.bak", "orphan")},
                             fmt(got))

    def test_untracked_file_under_claude_skills_is_an_orphan(self):
        m = real_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = build_pair_root(ROOT, m, pair_by_id(m, "skills"), root)
            self.assertEqual(mirror.check(root, sub), [])
            write(root, ".claude/skills/fde-stray/SKILL.md", "untracked\n")
            got = mirror.check(root, sub)
            self.assertEqual({(v.pair, v.path, v.kind) for v in got},
                             {("skills", ".claude/skills/fde-stray/SKILL.md",
                               "orphan")}, fmt(got))


# --------------------------------------------------------------------------
# R8: the manifest against the other declarations of the same layout

SETUP_PINNED = ("AGENTS.md", ".claude/agents/", ".claude/skills/")


def _section(text: str, start: str, stop: str) -> str:
    return text.split(start, 1)[1].split(stop, 1)[0]


def drop_unnoticed(root: Path, manifest: dict) -> list[str]:
    """Ids of the pairs whose removal from the manifest neither the checker
    nor the R8 agreement notices (FM-1)."""
    out = []
    for p in manifest["pair"]:
        dropped = _copy.deepcopy(manifest)
        dropped["pair"] = [q for q in dropped["pair"] if q["id"] != p["id"]]
        if not (mirror.check(root, dropped) or agreement(root, dropped)):
            out.append(p["id"])
    return out


def agreement(root: Path, manifest: dict) -> list[str]:
    """Where the manifest and [erosion].generated_paths / SETUP §6-§8
    disagree. Catches a pair dropped from the manifest (FM-1), which the
    orphan walk cannot: nothing walks a root nobody declares."""
    problems = []
    pairs = manifest["pair"]
    copies = [p["copy"] for p in pairs]
    ignore = manifest["ignore"]["entries"]

    def under_a_copy(rel: str) -> bool:
        return any(rel == c or (c.endswith("/") and rel.startswith(c))
                   for c in copies)

    cfg = tomllib.loads((root / "fde.config.toml").read_text("utf-8"))
    generated = cfg["erosion"]["generated_paths"]
    for entry in generated:
        if not any(c.startswith(entry) for c in copies):
            problems.append(f"generated_paths {entry!r} holds no declared "
                            f"copy root")
        if not (root / entry).exists():
            problems.append(f"generated_paths {entry!r} does not exist")
            continue
        for f in files_under(root, entry, ignore):
            if not under_a_copy(f):
                problems.append(f"{f} is under generated_paths {entry!r} "
                                f"but no declared copy root")
    for p in pairs:
        if p["relation"] != "identical":
            continue
        under = any(p["copy"].startswith(e) for e in generated)
        measured = p.get("erosion_measured", False)
        if under == measured:
            problems.append(
                f"{p['id']}: copy {p['copy']!r} must be under "
                f"generated_paths xor declare erosion_measured = true")
    setup = (root / "SETUP.md").read_text(encoding="utf-8")
    sec6 = _section(setup, "\n## 6.", "\n## 7.")
    sec78 = _section(setup, "\n## 7.", "\n## 9.")
    dests = re.findall(r"→ `([^`]+)`", sec6)
    if not dests:
        problems.append("SETUP §6 names no install destination")
    for d in SETUP_PINNED:
        if f"`{d}`" not in sec78:
            problems.append(f"SETUP §7/§8 no longer names `{d}`")
    for d in dests + list(SETUP_PINNED):
        if d not in copies:
            problems.append(f"SETUP installs to {d!r}, no pair declares it")
    return problems


def tracked_files(root: Path) -> list[str]:
    """`git ls-files` of root. Used only to validate the manifest's ignore
    list against what git tracks — never by the checker (ADR-0016 keeps
    git out of the pure core). Raises when root is not a git work tree:
    fail closed, never a skipped check."""
    top = subprocess.run(["git", "-C", str(root), "rev-parse",
                          "--show-toplevel"], check=True, capture_output=True,
                         text=True).stdout.strip()
    if Path(top).resolve() != Path(root).resolve():
        # F15: root inside SOMEONE ELSE's work tree lists nothing; that is
        # not "nothing is silenced"
        raise AssertionError(f"{root} is not the top level of its git work "
                             f"tree ({top})")
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                         check=True, capture_output=True).stdout
    files = [f for f in out.decode("utf-8").split("\0") if f]
    if not files:
        raise AssertionError(f"git tracks nothing under {root}")
    return files


def silenced_tracked(root: Path, manifest: dict) -> list[str]:
    """Tracked files an [ignore] entry would hide (F9). spec.md Always:
    "The ignore rule is explicit and narrow; it never silences a tracked
    file." Ignored paths drop out of both sides of every walk, so an
    entry matching a tracked file (`dimensions/`, `roles.toml`) would
    hide that file's drift — and .gitignore, the only other guard, does
    not untrack anything."""
    entries = manifest["ignore"]["entries"]
    return [f for f in tracked_files(root)
            if mirror.hidden(f, False, entries)]


class TestIgnoreNeverSilencesATrackedFile(unittest.TestCase):
    def test_no_ignore_entry_matches_a_tracked_file(self):
        self.assertEqual(silenced_tracked(ROOT, real_manifest()), [])

    def test_an_entry_over_tracked_content_is_reported(self):
        m = real_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            for rel in ("spec/dimensions/q.toml", ".fde/spec/dimensions/q.toml",
                        "agents/fde-implementation.md", "spec/roles.toml",
                        "runtime/a.py"):
                write(root, rel, "x\n")
            write(root, "runtime/__pycache__/a.cpython-314.pyc", "o")
            write(root, "runtime/b.pyc", "o")
            write(root, ".gitignore", "__pycache__/\n*.py[co]\n")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            self.assertEqual(silenced_tracked(root, m), [])  # output only
            write(root, "skills/fde-review/SKILL.md", "x\n")
            write(root, "skills/fde-review/refs/a.md", "x\n")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            dims = {"spec/dimensions/q.toml", ".fde/spec/dimensions/q.toml"}
            skill = {"skills/fde-review/SKILL.md",
                     "skills/fde-review/refs/a.md"}
            for entry, hidden in (
                    ("dimensions/", dims),
                    ("dimensions", dims),            # bare name of a dir (F14)
                    ("fde-review", skill),           # nested skills/<name>
                    ("fde-review/", skill),
                    ("spec", dims | {"spec/roles.toml"}),   # an ancestor
                    ("*.toml", dims | {"spec/roles.toml"}),
                    ("fde-implementation.md", {"agents/fde-implementation.md"}),
                    ("roles.toml", {"spec/roles.toml"}),
                    ("*.py", {"runtime/a.py"})):
                with self.subTest(entry=entry):
                    bad = _copy.deepcopy(m)
                    bad["ignore"]["entries"].append(entry)
                    self.assertEqual(set(silenced_tracked(root, bad)), hidden)

    def test_the_walk_and_the_validator_share_one_predicate(self):
        # F14's class, not its variant: for every entry form, the files a
        # directory-pair walk drops are exactly the files hidden() reports
        tree = ["s/a.md", "s/dimensions/q.toml", "s/dimensions/deep/r.toml",
                "s/fde-review/SKILL.md", "s/fde-review/refs/a.md",
                "s/x.pyc", "s/sub/x.pyc", "s/__pycache__/m.pyc"]
        forms = ["dimensions", "dimensions/", "fde-review", "fde-review/",
                 "*.pyc", "__pycache__/", "a.md", "s/dimensions/",
                 "s/fde-review/refs/a.md"]
        for entry in forms:
            with self.subTest(entry=entry), \
                    tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for rel in tree:
                    write(root, rel, "x\n")
                run = mirror._Run(root, {"pair": [], "ignore": {
                    "entries": [entry]}})
                walked = set(run.walk(pair("d", "s/", "c/"), "s/"))
                dropped = set(tree) - walked
                self.assertEqual(dropped, {f for f in tree if mirror.hidden(
                    f, False, [entry])})
                self.assertTrue(dropped, f"{entry} hid nothing")

    def test_tracked_files_fails_closed_outside_its_own_work_tree(self):
        # F15: an export nested inside another repository, and a work tree
        # that tracks nothing, are errors — never an empty "nothing hidden"
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            subprocess.run(["git", "init", "-q", str(outer)], check=True)
            write(outer, "forward/spec/dimensions/q.toml", "x\n")
            with self.assertRaises(AssertionError):
                tracked_files(outer / "forward")
            with self.assertRaises(AssertionError):
                tracked_files(outer)   # top level, but tracks nothing


class TestAgreement(unittest.TestCase):
    def test_manifest_agrees_with_generated_paths_and_setup(self):
        self.assertEqual(agreement(ROOT, real_manifest()), [])

    def test_dropping_any_one_pair_goes_red(self):
        # Iterated from the manifest. Something outside the manifest must
        # notice each drop: the parent pair's relation (nested pairs), the
        # orphan walk beside a file pair's copy, SETUP §6-§8 or
        # generated_paths (R8). A pair none of them sees needs its
        # destination named in SETUP — never a hand list here (F1).
        self.assertEqual(drop_unnoticed(ROOT, real_manifest()), [])

    def test_setup_parse_is_not_vacuous(self):
        # no hard-coded destination list: the parser finds something, and
        # everything it finds is declared; that it finds enough is what
        # test_dropping_any_one_pair_goes_red proves
        setup = (ROOT / "SETUP.md").read_text(encoding="utf-8")
        dests = re.findall(r"→ `([^`]+)`",
                           _section(setup, "\n## 6.", "\n## 7."))
        copies = {p["copy"] for p in real_manifest()["pair"]}
        self.assertTrue(dests)
        self.assertLessEqual(set(dests) | set(SETUP_PINNED), copies)

    def test_erosion_measured_is_exclusive(self):
        m = real_manifest()
        both = _copy.deepcopy(m)
        pair_by_id(both, "runtime")["erosion_measured"] = True
        self.assertTrue(agreement(ROOT, both))
        neither = _copy.deepcopy(m)
        del pair_by_id(neither, "pre-commit")["erosion_measured"]
        self.assertTrue(agreement(ROOT, neither))


# --------------------------------------------------------------------------
# F7: the generated-file marker is declared once, in SETUP §6; every
# generated (identical-except) pair that carries it — in an insert text or
# in its template source — must say it verbatim, in that file's comment
# syntax. Plain copies (`identical`, e.g. templates/pre-commit and its
# one-line marker) are copied, not generated, and are not held to it.


def setup_marker(root: Path) -> list[str]:
    setup = (root / "SETUP.md").read_text(encoding="utf-8")
    block = setup.split("Generated-file marker", 1)[1].split("```\n", 2)[1]
    return block.splitlines()


def marker_problems(root: Path, manifest: dict) -> list[str]:
    marker = setup_marker(root)
    problems = [] if marker and "FDE-KERNEL:GENERATED" in marker[0] else [
        "SETUP §6 declares no FDE-KERNEL:GENERATED marker block"]
    carriers = []
    for p in manifest["pair"]:
        if p["relation"] != "identical-except":
            continue
        for e in p["except"]:
            if e["kind"] == "insert":
                carriers.append((f"{p['id']} insert", e["text"]))
        src = root / p["source"]
        if src.is_file():
            carriers.append((p["source"], src.read_text(encoding="utf-8")))
    for where, text in carriers:
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if "FDE-KERNEL:GENERATED" not in ln:
                continue
            # the whole block, not a prefix of it (F11): every following
            # line in the same comment syntax, up to the comment's end
            prefix = ln[:ln.index("FDE-KERNEL:GENERATED")]
            got = []
            for x in lines[i:]:
                if not x.startswith(prefix) or x[len(prefix):].strip() in (
                        "", "-->", "*/"):
                    break
                got.append(x[len(prefix):])
            if got != marker:
                problems.append(f"{where}: marker differs from SETUP §6")
    return problems


class TestGeneratedMarker(unittest.TestCase):
    def test_every_marker_the_manifest_carries_is_setups(self):
        m = real_manifest()
        carriers = sum("FDE-KERNEL:GENERATED" in e["text"]
                       for p in m["pair"] for e in p.get("except", [])
                       if e["kind"] == "insert")
        self.assertGreaterEqual(carriers, 1)   # not vacuous
        self.assertEqual(marker_problems(ROOT, m), [])

    def test_a_reworded_setup_marker_goes_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m = real_manifest()
            repo_slice(root, m)
            setup = (root / "SETUP.md").read_text(encoding="utf-8")
            self.assertEqual(setup.count("detected as drift."), 1)
            write(root, "SETUP.md", setup.replace("detected as drift.",
                                                  "reported as drift."))
            got = marker_problems(root, m)
            self.assertIn("adversarial-role insert: marker differs from "
                          "SETUP §6", got)
            self.assertIn("templates/AGENTS.md.template: marker differs "
                          "from SETUP §6", got)


class TestGeneratedMarkerWholeBlock(unittest.TestCase):
    def test_a_shortened_setup_or_a_grown_carrier_goes_red(self):
        m = real_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_slice(root, m)
            setup = (root / "SETUP.md").read_text(encoding="utf-8")
            line = "Manual edits here are overwritten and detected as drift.\n"
            self.assertEqual(setup.count(line), 1)
            write(root, "SETUP.md", setup.replace(line, ""))
            self.assertIn("templates/fde-gate.yml: marker differs from "
                          "SETUP §6", marker_problems(root, m))
        grown = _copy.deepcopy(m)
        e = next(e for e in pair_by_id(grown, "adversarial-role")["except"]
                 if e["kind"] == "insert")
        e["text"] = e["text"].replace(
            "detected as drift.\n",
            "detected as drift.\nHand edits are fine for this file.\n")
        self.assertIn("adversarial-role insert: marker differs from "
                      "SETUP §6", marker_problems(ROOT, grown))


# --------------------------------------------------------------------------
# F2: render:attack_order formats the kernel's own plan (fde_lib.probe_plan)


class TestAttackOrderIsTheKernelsPlan(unittest.TestCase):
    QA = "spec/dimensions/quality-attributes.toml"

    def render(self, weights: str) -> tuple[list[str], list[dict]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_rel(ROOT, root, self.QA)
            write(root, "fde.config.toml", "[weights]\n" + weights)
            text = mirror.resolve(root, real_manifest(), "render:attack_order")
            plan = mirror.fde_lib.probe_plan(
                mirror.fde_lib.Config.load(root),
                mirror.fde_lib.Spec(invariants={}, quality=tomllib.loads(
                    (root / self.QA).read_text("utf-8")), domains={},
                    roles={}))
        return [ln for ln in text.splitlines() if ln.startswith("### ")], plan

    def labels(self, heads):
        return [h.split(". ", 1)[1].split(" — ", 1)[0] for h in heads]

    def test_ties_follow_the_kernels_order_not_the_configs(self):
        # usability declared before reliability, both 12: the kernel plans
        # reliability first (quality-attributes.toml order)
        heads, plan = self.render(
            "functional_correctness = 30\nmaintainability = 22\n"
            "usability_accessibility = 12\nreliability_resilience = 12\n"
            "observability = 10\nsecurity_privacy = 8\n"
            "performance_scale = 3\noperational_cost = 3\n")
        self.assertEqual(self.labels(heads), [s["label"] for s in plan])
        self.assertLess(self.labels(heads).index("Reliability & resilience"),
                        self.labels(heads).index("Usability & accessibility"))

    def test_a_missing_weight_is_planned_at_its_floor(self):
        heads, plan = self.render(
            "functional_correctness = 30\nmaintainability = 22\n"
            "reliability_resilience = 12\nusability_accessibility = 12\n"
            "observability = 10\nsecurity_privacy = 8\n"
            "performance_scale = 3\n")
        self.assertEqual(len(heads), len(plan))
        self.assertEqual(self.labels(heads), [s["label"] for s in plan])
        self.assertIn("### 8. Operational cost — weight 3", heads)

    def test_an_unknown_weight_is_source_of_truth_missing(self):
        with self.assertRaises(mirror.SourceOfTruthMissing):
            self.render("functional_correctness = 30\nvibes = 10\n")


# --------------------------------------------------------------------------

PROBES_ADDED_BY_FWD_020 = (
    "- ambiguous next action with multiple plausible controls\n",
    "- irreversible action taken with no confirmation or undo\n",
    "- state change with no visible feedback\n",
)


class TestStaleAttackOrder(unittest.TestCase):
    """FM-15 / R12, the drift this demand found live: the copy's attack
    order lacked three usability probes quality-attributes.toml has had
    since FWD-017, and D6's weight/round needles stayed green. The
    fixture is the pre-fix copy — the regenerated section with those
    three lines removed (byte-equal to the copy at the demand's base)."""

    def test_pre_fix_copy_is_reported_inside_the_usability_block(self):
        m = real_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = build_pair_root(ROOT, m, pair_by_id(m, "adversarial-role"),
                                  root)
            target = root / ".claude" / "agents" / "fde-adversarial.md"
            text = target.read_text(encoding="utf-8")
            for line in PROBES_ADDED_BY_FWD_020:
                self.assertEqual(text.count(line), 1, line)
                text = text.replace(line, "")
            target.write_text(text, encoding="utf-8")
            got = [v for v in mirror.check(root, sub)
                   if v.pair == "adversarial-role" and v.kind == "differs"]
            self.assertEqual(len(got), 1, fmt(mirror.check(root, sub)))
            line_no = int(got[0].detail.rsplit(" ", 1)[1])
            lines = text.split("\n")
            start = next(i for i, ln in enumerate(lines, 1)
                         if ln.startswith("### ")
                         and "Usability & accessibility" in ln)
            end = next(i for i, ln in enumerate(lines, 1)
                       if i > start and ln.startswith("### "))
            self.assertTrue(start < line_no < end,
                            f"line {line_no} not in block {start}-{end}")



# --------------------------------------------------------------------------
# Where each protection of the FWD-020 inventory lives now (spec.md,
# D1-D13 retired or kept, G1-G10 closed or dispositioned). Checked below:
# every pair id must be declared and every test id must exist, so this
# table cannot point at something that is gone (FM-1, FM-8, FM-13).

INVENTORY = {
    "D1": (["runtime"], ["test_mirror.TestFailClosed.test_empty_source_root",
                         "test_mirror.TestRealRepo."
                         "test_every_declared_pair_holds_on_this_repo"],
           "erosion.py/graph.py sanity pin -> empty-source/zero-checked"),
    "D2": (["spec"], [], "all file types, discovered"),
    "D3": (["runtime", "spec"],
           ["test_mirror.TestFailClosed."
            "test_missing_copy_and_orphan_all_file_types"],
           "orphan walk, all file types"),
    "D4": (["skills", "skills-init"],
           ["test_mirror.TestFailClosed.test_absent_pair"],
           "fde-init declared absent"),
    "D5": (["agents"], [], "discovered, no hand list"),
    "D6": (["adversarial-role"],
           ["test_mirror.TestRealRepo."
            "test_verified_regions_catch_plausible_wrong_values"],
           "insert + replace-section = render:attack_order, byte-exact"),
    "D7": (["agents-md"], [], "render:invariants_list (id, name, statement)"),
    "D8": (["agents-md"], [], "render:weights_list, render:depths_list, "
           "config:stack.test_command"),
    "D9": (["workflow"],
           ["test_install_sync.TestGeneratedSurfaces."
            "test_workflow_runs_tests_and_a_ranged_gate_on_full_history"],
           "identity in the pair; fetch-depth/--since needles kept"),
    "D10": (["agents-md"],
            ["test_instructions.TestPerCycleTriage."
             "test_demand_loop_states_the_per_cycle_rule"],
            "whole file; DEM-042 -> FWD-002 is one counted literal; "
            "needles kept"),
    "D11": (["agents-md"],
            ["test_instructions.TestRuleLaneIsAParagraphNotATableRow."
             "test_rule_paragraph_says_what_r5_requires"],
            "whole file; content needles kept, now in both surfaces"),
    "D12": (["agents-md"],
            ["test_scrum.TestScrumR2R3Artifacts."
             "test_both_agents_surfaces_carry_a_scrum_section"],
            "whole file; section-exists half kept"),
    "D13": (["spec"], [], "redundant with D2, retired"),
    "G1": (["agents"], [], "fde-walkthrough-evaluator.md discovered"),
    "G2": (["pre-commit"], [], "erosion_measured = true"),
    "G3": (["workflow"], [], "whole file"),
    "G4": (["adversarial-role"], [], "whole file outside declared regions"),
    "G5": (["agents-md"], [], "whole file outside declared exceptions"),
    "G6": (["runtime", "spec", "skills", "agents"],
           ["test_mirror.TestIgnore."
            "test_untracked_file_under_claude_skills_is_an_orphan",
            "test_mirror.TestMutationSuite."
            "test_every_manifest_pair_goes_red_on_every_mutation"],
           "bidirectional, all file types"),
    "G7": ([], ["test_install_sync.TestNativeLayerShape."
                "test_claude_md_imports_agents_md_on_its_first_line"],
           "content test, ADR-0016 Decision 6"),
    "G8": ([], ["test_install_sync.TestNativeLayerShape."
                "test_settings_run_the_guard_hook_and_branch_worktrees_from_head"],
           "content test, ADR-0016 Decision 6"),
    "G9": ([], ["test_mirror.TestAgreement."
                "test_manifest_agrees_with_generated_paths_and_setup",
                "test_mirror.TestAgreement.test_erosion_measured_is_exclusive",
                "test_mirror.TestAgreement.test_dropping_any_one_pair_goes_red"],
           "cross-checked, not derived, ADR-0016 Decision 4"),
    "G10": ([], [], "neither derived nor checked, ADR-0016 Decision 5"),
    "FM-15": (["adversarial-role"],
              ["test_mirror.TestStaleAttackOrder."
               "test_pre_fix_copy_is_reported_inside_the_usability_block"],
              "the drift this demand found and regenerated"),
}


def inventory_problems(manifest: dict) -> list[str]:
    """INVENTORY maps each retired or kept protection to its home. Every
    home must exist; a pair need not have a row — INVENTORY is history,
    and a new pair is not history (F1)."""
    import importlib
    declared = {p["id"] for p in manifest["pair"]}
    problems = []
    rows = [f"D{n}" for n in range(1, 14)] + [f"G{n}" for n in range(1, 11)]
    problems += [f"{r} has no row" for r in rows if r not in INVENTORY]
    for row, (pairs, tests, _why) in INVENTORY.items():
        if row != "G10" and not (pairs or tests):
            problems.append(f"{row} has no home")
        problems += [f"{row}: pair {pid!r} is not declared"
                     for pid in pairs if pid not in declared]
        for test_id in tests:
            module, cls, method = test_id.split(".")
            klass = getattr(importlib.import_module(module), cls, None)
            if not callable(getattr(klass, method, None)):
                problems.append(f"{row}: {test_id} does not exist")
    return problems


class TestInventoryMapping(unittest.TestCase):
    def test_every_row_points_at_something_that_exists(self):
        self.assertEqual(inventory_problems(real_manifest()), [])

    def test_a_row_pointing_at_nothing_is_reported(self):
        m = real_manifest()
        m["pair"] = [p for p in m["pair"] if p["id"] != "workflow"]
        got = inventory_problems(m)
        self.assertIn("D9: pair 'workflow' is not declared", got)
        self.assertIn("G3: pair 'workflow' is not declared", got)


if __name__ == "__main__":
    unittest.main()
