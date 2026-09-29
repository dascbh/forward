"""FM-1/R1: the PreToolUse guard — allowlist role scopes, gate paths,
absolute paths.

Honesty note (finding F3): payloads here fabricate agent_name to exercise
the role branch as a unit. The real hook payload carries a role identity
only where the harness provides one; the always-on protection is the
no-suite I1 branch, and role scopes are charged at commit by I2/I3.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import guard, make_project


class TestGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name,
                              behavior='["backend/app/", "src/", "SETUP.md"]')

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, rel, agent=""):
        return {"tool_input": {"file_path": str(Path(self.p) / rel)},
                "agent_name": agent}

    # -- judging roles are ALLOWLISTED to their write scope ---------------
    def test_adversarial_writes_only_in_reviews(self):
        for target in ("src/x.py", "backend/app/x.py",
                       "promotions/D-1/decision.md", "docs/adr/0001.md",
                       "bin/fde/verify.py", ".fde/spec/invariants.toml"):
            r = guard(self.p, self.payload(target, "fde-adversarial"))
            self.assertEqual(r.returncode, 2, target)
            self.assertIn("writes only in", r.stderr)
        r = guard(self.p, self.payload("reviews/D-1/findings.toml",
                                       "fde-adversarial"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_promotion_writes_in_its_cycle_file_and_legacy_promotions(self):
        r = guard(self.p, self.payload("reviews/D-1/findings.toml",
                                       "fde-promotion"))
        self.assertEqual(r.returncode, 2)
        # primary: the cycle layout (ADR-0019); legacy: pre-ADR-0019 cycles
        for target in ("cycles/C-1/promotion.md", "promotions/D-1/decision.md"):
            r = guard(self.p, self.payload(target, "fde-promotion"))
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_implementation_cannot_rewrite_its_own_judges(self):
        for target in ("cycles/C-1/plan.md", "reviews/D-1/findings.toml",
                       "specs/D-1/acceptance.md"):  # the last: legacy layout
            r = guard(self.p, self.payload(target, "fde-implementation"))
            self.assertEqual(r.returncode, 2, target)

    # -- the always-on branch: no suite, no behavior write ----------------
    def test_behavior_write_blocked_while_no_suite_exists(self):
        (self.p / "evals").mkdir()
        (self.p / "evals" / ".gitkeep").touch()  # structure, not a suite
        r = guard(self.p, self.payload("backend/app/x.py", "fde-implementation"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("I1", r.stderr)

    def test_file_entry_behavior_paths_are_guarded_too(self):
        r = guard(self.p, self.payload("SETUP.md", "fde-implementation"))
        self.assertEqual(r.returncode, 2)  # no suite yet

    def test_behavior_write_allowed_once_suite_exists(self):
        (self.p / "tests").mkdir()
        (self.p / "tests" / "test_x.py").write_text("assert True\n")
        r = guard(self.p, self.payload("backend/app/x.py", "fde-implementation"))
        self.assertEqual(r.returncode, 0, r.stderr)

    # -- boundaries -------------------------------------------------------
    def test_paths_outside_the_project_are_not_its_jurisdiction(self):
        r = guard(self.p, {"tool_input": {"file_path": "/etc/hosts"},
                           "agent_name": "fde-adversarial"})
        self.assertEqual(r.returncode, 0)

    def test_unreadable_payload_never_blocks_by_accident(self):
        r = guard(self.p, {})
        self.assertEqual(r.returncode, 0)


class TestGuardIdentityFromMetadata(unittest.TestCase):
    """FWD-005: no agent_name in the payload — identity derived from the
    worktree cwd + harness metadata (agentType)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        self.meta_root = Path(self._tmp.name) / "meta"
        # metadata lookup is scoped to this project's slug (FWD-005 fix)
        slug = str(Path(self._tmp.name).resolve()).replace("/", "-")
        d = self.meta_root / slug / "sess" / "subagents"
        d.mkdir(parents=True)
        (d / "agent-abc123.meta.json").write_text(
            '{"agentType": "fde-adversarial"}')
        self.env = {"FDE_AGENT_META_DIR": str(self.meta_root)}

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, rel, worktree="agent-abc123"):
        return {"tool_input": {"file_path": str(Path(self.p) / rel)},
                "cwd": f"/x/.claude/worktrees/{worktree}"}

    def test_worktree_subagent_is_scoped_without_payload_identity(self):
        r = guard(self.p, self.payload("src/x.py"), env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("fde-adversarial", r.stderr)
        r = guard(self.p, self.payload("reviews/D-1/findings.toml"),
                  env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_metadata_no_role_block_with_suite_present(self):
        (self.p / "tests").mkdir(exist_ok=True)
        (self.p / "tests" / "t.py").write_text("assert True\n")
        r = guard(self.p, self.payload("src/x.py", worktree="agent-ffffff"),
                  env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_corrupt_metadata_never_crashes_or_blocks(self):
        slug = str(Path(self._tmp.name).resolve()).replace("/", "-")
        d = self.meta_root / slug / "sess" / "subagents"
        (d / "agent-badbad.meta.json").write_text("{not json")
        (self.p / "tests").mkdir(exist_ok=True)
        (self.p / "tests" / "t.py").write_text("assert True\n")
        r = guard(self.p, self.payload("src/x.py", worktree="agent-badbad"),
                  env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_worktree_writes_are_judged_by_their_repo_relative_path(self):
        """The reviewer's own false-block, fixed: a role writing its
        handoff artifact INSIDE its worktree is in scope."""
        wt_rel = ".claude/worktrees/agent-abc123"
        r = guard(self.p,
                  self.payload(f"{wt_rel}/reviews/D-1/findings.toml"),
                  env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = guard(self.p, self.payload(f"{wt_rel}/src/x.py"), env=self.env)
        self.assertEqual(r.returncode, 2)  # still scoped, correctly


class TestGuardAudit(unittest.TestCase):
    """FWD-006: every block and every identified allow leaves a trail;
    auditing never affects the decision."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        self.log = self.p / ".fde" / "guard-audit.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, rel, agent=""):
        return {"tool_input": {"file_path": str(Path(self.p) / rel)},
                "agent_name": agent}

    def entries(self):
        import json as j
        return [j.loads(l) for l in
                self.log.read_text().strip().splitlines()]

    def test_block_is_recorded_with_rule_and_agent(self):
        guard(self.p, self.payload("src/x.py", "fde-adversarial"))
        e = self.entries()[-1]
        self.assertEqual((e["decision"], e["rule"], e["agent"]),
                         ("block", "role-scope", "fde-adversarial"))
        self.assertIn("ts", e)

    def test_identified_allow_is_recorded_anonymous_is_not(self):
        guard(self.p, self.payload("reviews/D/f.toml", "fde-adversarial"))
        self.assertEqual(self.entries()[-1]["decision"], "allow")
        n = len(self.entries())
        guard(self.p, self.payload("docs/notes.md"))  # anonymous, in scope
        self.assertEqual(len(self.entries()), n)  # not logged

    def test_generic_agent_allows_are_not_logged(self):
        guard(self.p, self.payload("reviews/D/f.toml", "fde-adversarial"))
        n = len(self.entries())
        guard(self.p, self.payload("docs/notes.md", "general-purpose"))
        self.assertEqual(len(self.entries()), n)  # non-fde roles are noise

    def test_audit_failure_never_changes_the_decision(self):
        self.log.mkdir(parents=True)  # a directory where the log should be
        r = guard(self.p, self.payload("src/x.py", "fde-adversarial"))
        self.assertEqual(r.returncode, 2)  # still blocks
        self.assertNotIn("Traceback", r.stderr)


class TestGuardCycleFiles(unittest.TestCase):
    """FWD-028: inside cycles/<C-n>/ each role writes only its own file;
    board.md is shared; implementation never writes a judging file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def code(self, rel, agent):
        return guard(self.p, {"tool_input": {"file_path": str(Path(self.p) / rel)},
                              "agent_name": agent}).returncode

    def test_each_role_writes_its_own_cycle_file(self):
        own = {"fde-spec": ("plan.md", "deploy.md"),
               "fde-adversarial": ("review.md",),
               "fde-promotion": ("promotion.md",)}
        every = ("plan.md", "deploy.md", "review.md", "promotion.md")
        for agent, files in own.items():
            for f in every:
                want = 0 if f in files else 2
                self.assertEqual(self.code(f"cycles/C-1/{f}", agent), want,
                                 f"{agent} {f}")
            self.assertEqual(self.code("cycles/C-1/board.md", agent), 0, agent)

    def test_every_role_writes_the_backlog_and_the_board(self):
        # reviews/FWD-028 F2, ADR-0019 rules 1 and 11: a new fact or a
        # non-blocking finding goes to backlog.md, and every role posts on
        # the cycle's board — from any role
        for agent in ("fde-spec", "fde-architecture", "fde-implementation",
                      "fde-adversarial", "fde-promotion"):
            for rel in ("backlog.md", "cycles/C-1/board.md"):
                self.assertEqual(self.code(rel, agent), 0, f"{agent} {rel}")
        # shared means those two files, not their neighbours
        self.assertEqual(self.code("cycles/C-1/x/board.md", "fde-architecture"), 2)
        self.assertEqual(self.code("docs/backlog.md", "fde-adversarial"), 2)

    def test_implementation_never_writes_what_judges_it(self):
        for f in ("plan.md", "deploy.md", "review.md", "promotion.md"):
            self.assertEqual(self.code(f"cycles/C-1/{f}", "fde-implementation"),
                             2, f)
        self.assertEqual(self.code("cycles/C-1/board.md", "fde-implementation"), 0)


class TestRuntimeMessagesCiteKernelADRs(unittest.TestCase):
    """B-28 (FWD-041): a client has its own docs/adr/, so a bare ADR id in
    a runtime message points at the wrong decision. Every string a
    runtime module prints says "kernel ADR-…"; comments and docstrings
    are not messages."""

    def test_no_bare_adr_id_in_a_runtime_string(self):
        import ast
        import re
        root = Path(__file__).resolve().parent.parent / "runtime"
        bare = []
        for src in sorted(root.glob("*.py")):
            tree = ast.parse(src.read_text(encoding="utf-8"))
            docs = set()
            for node in ast.walk(tree):
                body = getattr(node, "body", None)
                if isinstance(body, list) and body and \
                        isinstance(body[0], ast.Expr) and \
                        isinstance(body[0].value, ast.Constant):
                    docs.add(id(body[0].value))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and \
                        isinstance(node.value, str) and id(node) not in docs:
                    for m in re.finditer(r"ADR-\d{4}", node.value):
                        if not node.value[:m.start()].endswith("kernel "):
                            bare.append(f"{src.name}:{node.lineno}: "
                                        f"{node.value!r}")
        self.assertEqual(bare, [])

    def test_guard_legacy_note_names_the_kernel_adr(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            r = guard(p, {"tool_input": {"file_path": str(Path(p) / "src/x.py")},
                          "agent_name": "fde-promotion"})
            self.assertEqual(r.returncode, 2)
            self.assertIn("before kernel ADR-0019", r.stderr)


if __name__ == "__main__":
    unittest.main()
