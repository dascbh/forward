"""The code-quality view over history (runtime/codebench.py, owner request
2026-09-29): snapshots, complexity, erosion, clones, hotspots."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import codebench  # noqa: E402
import quietgit  # noqa: E402,F401  (git maintenance off in test repos)

SIMPLE = "def ok(x):\n    return x + 1\n"
def handle(n: int) -> str:
    return ("def handle(a, b):\n" + "".join(
        f"    if a == {i} and b:\n        b += {i}\n" for i in range(n))
        + "    return b\n")


GROWN = handle(8)


class TestBench(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        r = self.root = Path(self.tmp.name)

        def git(*a):
            subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)
        self.git = git
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        (r / "app").mkdir()
        (r / "tests").mkdir()
        (r / "fde.config.toml").write_text(
            '[gate]\nbehavior_paths = ["app/"]\neval_paths = ["tests/"]\n')
        (r / "app" / "core.py").write_text(SIMPLE + "\n" + handle(3))
        (r / "tests" / "test_core.py").write_text(GROWN)
        git("add", "-A")
        git("commit", "-q", "-m", "install")
        (r / "app" / "core.py").write_text(SIMPLE + "\n" + GROWN)
        for i in range(3):   # a module copied into three packages
            (r / "app" / f"pkg{i}").mkdir()
            (r / "app" / f"pkg{i}" / "shared.py").write_text(SIMPLE)
        git("add", "-A")
        git("commit", "-q", "-m", "grow")

    def test_snapshots_track_growth_and_copies_once(self):
        data = codebench.bench(self.root, points=2)
        first, head = data["snapshots"][0], data["snapshots"][-1]
        self.assertEqual(first["label"], "FORWARD installed")
        self.assertEqual(head["label"], "HEAD")
        self.assertEqual(first["complex"], 0)
        self.assertEqual(head["complex"], 1)
        self.assertEqual(head["copy_groups"], 1)
        self.assertEqual(head["files"], 2)          # core + one shared copy
        self.assertGreater(head["structural_erosion"], first["structural_erosion"])

    def test_tests_are_out_and_hotspots_show_growth(self):
        data = codebench.bench(self.root, points=2)
        hot = data["hotspots"][0]
        self.assertEqual((hot["path"], hot["function"]), ("app/core.py", "handle"))
        self.assertEqual((hot["cc_then"], hot["cc"]), (7, 17))
        self.assertNotIn("tests/", json.dumps(data["hotspots"]))

    def test_text_and_json_render(self):
        text = "\n".join(codebench.render(codebench.bench(self.root, points=2)))
        self.assertIn("CC>10", text)
        self.assertIn("← FORWARD installed", text)
        self.assertIn("CC 7 → 17", text)
        out = subprocess.run([sys.executable, str(ROOT / "runtime" / "codebench.py"),
                              "--root", str(self.root), "--format", "json"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("snapshots", json.loads(out.stdout))

    def test_skill_and_readme_point_to_it(self):
        skill = (ROOT / "skills/fde-codebench/SKILL.md").read_text()
        self.assertIn("It reports; it never gates.", skill)
        self.assertIn("`fde-codebench`", (ROOT / "README.md").read_text())



class ChangeView(unittest.TestCase):
    def test_hotspots_weigh_change_by_size_and_coupling_needs_five_together(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            for args in (["init", "-q"], ["config", "user.email", "f@t"], ["config", "user.name", "f"]):
                subprocess.run(["git", *args], cwd=p, check=True, capture_output=True)
            (p / "src").mkdir()
            big = "".join(f"x{i} = {i}\n" for i in range(50))
            (p / "src" / "big.py").write_text(big)
            (p / "src" / "small.py").write_text("y = 0\n")
            (p / "src" / "lone.py").write_text("z = 0\n")

            def commit(msg):
                subprocess.run(["git", "add", "-A"], cwd=p, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-qm", msg], cwd=p, check=True, capture_output=True)
            commit("start")
            for i in range(5):  # big and small always together
                (p / "src" / "big.py").write_text(big + f"w = {i}\n")
                (p / "src" / "small.py").write_text(f"y = {i + 1}\n")
                commit(f"pair {i}")
            for i in range(9):  # lone changes the most, alone and tiny
                (p / "src" / "lone.py").write_text(f"z = {i + 1}\n")
                commit(f"lone {i}")
            c = codebench.change_view(p)
            self.assertEqual(c["hotspots"][0]["path"], "src/big.py")
            self.assertEqual([(x["a"], x["b"]) for x in c["coupled"]],
                             [("src/big.py", "src/small.py")])
            self.assertNotIn("lone", " ".join(x["a"] + x["b"] for x in c["coupled"]))
            text = "\n".join(codebench.render_change(c))
            self.assertIn("kernel ADR-0024", text)


class ProcessView(unittest.TestCase):
    """Flow, suite size and the last suite run beside the code (owner, 2026-09-30)."""

    def test_the_process_section_reads_runs_cycles_and_suite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            for args in (["init", "-q"], ["config", "user.email", "f@t"], ["config", "user.name", "f"]):
                subprocess.run(["git", *args], cwd=p, check=True, capture_output=True)
            (p / "src").mkdir()
            (p / "src" / "a.py").write_text(SIMPLE)
            (p / "src" / "test_a.py").write_text("import a\n\n\ndef test_ok():\n    assert a.ok(1) == 2\n")
            (p / "cycles" / "C-1").mkdir(parents=True)
            (p / "cycles" / "C-1" / "plan.md").write_text("cycle: C-1\nstate: closed\n\n## Items\n\nnone\n")
            runs = p / ".fde" / "runs"
            runs.mkdir(parents=True)
            (runs / "old.json").write_text(json.dumps({"suite": {"seconds": 9.0, "exit_code": 0, "recorded_at": "2026-09-29T10:00:00Z"}}))
            (runs / "new.json").write_text(json.dumps({"suite": {"seconds": 12.5, "exit_code": 1, "recorded_at": "2026-09-30T10:00:00Z"}}))
            subprocess.run(["git", "add", "-A"], cwd=p, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "c"], cwd=p, check=True, capture_output=True)
            v = codebench.process_view(p)
            self.assertEqual(v["suite"]["production_loc"], 2)
            self.assertEqual(v["suite"]["test_loc"], 3)
            self.assertEqual(v["last_suite_run"]["seconds"], 12.5)
            self.assertEqual(v["flow"]["closed"], 1)
            text = "\n".join(codebench.render_process(v))
            self.assertIn("12.5s, exit 1", text)
            self.assertIn("codebench.py --tests", text)

    def test_no_cycles_and_no_runs_still_render(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            subprocess.run(["git", "init", "-q"], cwd=p, check=True, capture_output=True)
            v = codebench.process_view(p)
            self.assertIsNone(v["flow"])
            self.assertIsNone(v["last_suite_run"])
            self.assertIn("verify.py --all --record-suite", "\n".join(codebench.render_process(v)))

if __name__ == "__main__":
    unittest.main()


class TestIndicators(unittest.TestCase):
    """The HEAD indicators and their published references."""

    def test_function_shape_follows_pylint_and_radon(self):
        import ast
        src = ("def f(self, a, b, c, d, e, f, *rest, **kw):\n"
               "    if a:\n        for x in b:\n            while c:\n"
               "                with d:\n                    try:\n"
               "                        if e:\n                            pass\n"
               "                    except ValueError:\n                        pass\n"
               "    else:\n        return 1\n")
        fn = ast.parse(src).body[0]
        statements, branches, nesting = codebench._shape(fn)
        self.assertEqual(nesting, 6)            # if/for/while/with/try/if
        self.assertEqual(branches, 6)           # if+else, for, while, except, if
        self.assertGreater(statements, 5)
        self.assertEqual(codebench._args(fn), 8)   # self out; *rest, **kw count
        self.assertEqual([codebench.radon_rank(c) for c in (5, 6, 11, 21, 31, 41)],
                         list("ABCDEF"))

    def test_controllers_sql_and_languages(self):
        files = {
            "api/routers/items.py": 'def get():\n    return db.execute("SELECT id FROM items WHERE x = 1")\n',
            "api/routers/health.py": "def ok():\n    return {'ok': True}\n",
            "app/service.py": 'Q = "INSERT INTO items (a) VALUES (1)"\n',
            "web/src/App.tsx": "export const A = () => null\n",
            "db/schema.sql": "CREATE TABLE items (id int);\n",
        }
        is_ctrl = lambda n: n.startswith("api/routers/")   # noqa: E731
        m = codebench.measure_snapshot(files, is_ctrl)
        self.assertEqual(m["sql_embedded"], 2)
        self.assertEqual(m["sql_file_loc"], 1)
        c = m["controllers"]
        self.assertEqual((c["files"], c["with_sql"], c["with_data"]), (2, 1, 1))
        self.assertEqual(c["names"], ["api/routers/items.py"])
        self.assertEqual(set(m["loc_by_language"]), {"Python", "TypeScript", "SQL"})

    def test_controller_paths_are_declared_or_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            match, declared = codebench.controller_rule(root)
            self.assertFalse(declared)
            self.assertTrue(match("backend/lambdas/itens/handler.py"))
            self.assertTrue(match("api/routers/loops.py"))
            self.assertFalse(match("app/service.py"))
            (root / "fde.config.toml").write_text(
                '[codebench]\ncontroller_paths = ["app/http/"]\n')
            match, declared = codebench.controller_rule(root)
            self.assertTrue(declared)
            self.assertTrue(match("app/http/items.py"))
            self.assertFalse(match("api/routers/loops.py"))
