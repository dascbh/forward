"""Every defect of a deploy plan at once, before the deploy (owner,
2026-10-01): a client's deploy stopped four times in production, each
stop a different defect of its own plan."""
from __future__ import annotations

import http.server
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import preflight  # noqa: E402
import quietgit  # noqa: E402,F401  (git maintenance off in test repos)

PLAN = "cycle: C-1\nstate: running\ndate: 2026-10-01\nsigned-off: 2026-10-01\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def log_message(self, *a):
        pass


class Preflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.p, check=True)
        (self.p / "fde.config.toml").write_text("[tooling]\nopen_permissions = false\n")
        (self.p / "cycles" / "C-1").mkdir(parents=True)
        (self.p / "cycles" / "C-1" / "plan.md").write_text(PLAN)
        (self.p / "infra").mkdir()
        (self.p / "scripts").mkdir()
        (self.p / "scripts" / "build.sh").write_text("echo ok\n")

    def deploy(self, prose: str, commands: str):
        (self.p / "cycles" / "C-1" / "deploy.md").write_text(
            f"cycle: C-1\n\n## Step 1\n\n{prose}\n\n## Commands\n\n```sh\n{commands}\n```\n")
        return preflight.preflight(self.p, "C-1", offline=True)["defects"]

    def test_a_sound_plan_has_nothing(self):
        self.assertEqual(self.deploy("Run the build, then the stack.",
                                     "bash scripts/build.sh\ncd infra\nTZ=UTC git status <args>"), [])

    def test_every_defect_is_listed_at_once(self):
        found = self.deploy("Then `cd infra && git status`.",
                            "bash scripts/missing.sh\ncd nowhere\nno-such-program-xyz --x\n"
                            "git status && git log")
        text = "\n".join(found)
        self.assertIn("scripts/missing.sh does not exist", text)
        self.assertIn("directory nowhere does not exist", text)
        self.assertIn("no-such-program-xyz is not on PATH", text)
        self.assertIn("chains commands", text)
        self.assertEqual(len(found), 4)

    def test_a_prose_step_chaining_a_declared_command_is_named(self):
        found = self.deploy("Run `cd infra && npx cdk deploy Stack`.", "cd infra\nnpx cdk deploy Stack")
        self.assertTrue(any("prose step" in d for d in found), found)

    def test_placeholders_and_environment_prefixes_are_not_defects(self):
        self.assertEqual(self.deploy("x", "AWS_PROFILE=p TZ=UTC git log <ref>\n<venv>/bin/python -V"), [])

    def test_steps_without_takes_are_noted_never_a_defect(self):
        (self.p / "cycles" / "C-1" / "deploy.md").write_text(
            "1. **back** — x\n   - Rollback: y\n   - Takes: ~10\n"
            "2. **front** — z\n   - Rollback: w\n\n## Commands\n\n```sh\ngit status\n```\n")
        r = preflight.preflight(self.p, "C-1", offline=True)
        self.assertEqual(r["defects"], [])
        self.assertIn("1 of 2 step(s) declare no `Takes:`", r["notes"][0])

    def test_no_commands_block_is_a_defect(self):
        (self.p / "cycles" / "C-1" / "deploy.md").write_text("cycle: C-1\n\n## Step 1\n\nprose\n")
        self.assertIn("no `## Commands` block",
                      preflight.preflight(self.p, "C-1", offline=True)["defects"][0])

    def test_an_address_answering_404_is_a_defect_and_200_is_not(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_port}"
        (self.p / "cycles" / "C-1" / "deploy.md").write_text(
            f"## Step 1\n\nCheck `{base}/health` and `{base}/api/v1/health` and `{base}/<id>`.\n\n"
            "## Commands\n\n```sh\ngit status\n```\n")
        r = preflight.preflight(self.p, "C-1")
        self.assertEqual(r["defects"], [f"{base}/api/v1/health answers 404"])
        self.assertTrue(r["not_fetched"])


if __name__ == "__main__":
    unittest.main()
