"""The install surface beyond file identity. Source→copy identity for
every mirrored file lives in one place: tests/mirror.toml, checked by
tests/test_mirror.py (FWD-020, ADR-0016). What stays here is what is not a
file copy: value carriers (kernel version, plugin names), the plugin
distribution, content the workflow must carry, and the native-layer merge
targets (CLAUDE.md, .claude/settings.json) SETUP §8.3/§8.4 describe."""
from __future__ import annotations

import json
import os
import subprocess
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestPluginDistribution(unittest.TestCase):
    """The repo is both marketplace and plugin, so `/plugin install
    forward@forward` resolves. These keep the two manifests agreeing."""

    @classmethod
    def setUpClass(cls):
        cls.plugin = json.loads(read(ROOT / ".claude-plugin" / "plugin.json"))
        cls.market = json.loads(read(ROOT / ".claude-plugin" / "marketplace.json"))

    def test_marketplace_lists_this_repo_as_its_plugin(self):
        entries = self.market["plugins"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["source"], ".", "the repo is its own plugin")
        # `/plugin install <plugin>@<marketplace>` — both names are used
        self.assertEqual(entry["name"], self.plugin["name"])
        self.assertEqual(self.market["name"], self.plugin["name"])

    def test_manifests_require_no_second_version_carrier(self):
        # the plugin entry deliberately omits `version` so plugin.json
        # stays the single source (MNT-1); a version here would be a
        # fifth carrier to keep in sync
        self.assertNotIn("version", self.market["plugins"][0])
        self.assertTrue(self.plugin.get("version"))

    def test_the_manifests_pass_the_real_validator(self):
        # asserting the schema against itself proved nothing: `owner` as a
        # bare string passed the suite and failed `claude plugin validate`
        # (review finding, FWD-014). Skipped where the CLI is absent — CI
        # containers have no claude binary — so this hardens local work
        # without becoming a false red.
        import shutil, subprocess
        if not shutil.which("claude"):
            self.skipTest("claude CLI not available")
        r = subprocess.run(["claude", "plugin", "validate", "."],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("warning", (r.stdout + r.stderr).lower())

    def test_owner_and_author_are_objects_not_strings(self):
        # the exact shape the validator rejects, pinned so the CLI-less
        # path still catches it
        self.assertIsInstance(self.market["owner"], dict)
        self.assertTrue(self.market["owner"].get("name"))
        self.assertIsInstance(self.plugin["author"], dict)
        self.assertTrue(self.plugin["author"].get("name"))

    def test_sync_updates_the_kernel_before_re_emitting(self):
        # "/forward:fde-sync" is the single update+sync command; if it only
        # re-emitted, a user asking to update would silently rewrite the
        # old artifacts
        skill = read(ROOT / "skills" / "fde-sync" / "SKILL.md")
        self.assertIn("claude plugin update forward@forward", skill)
        self.assertIn("git -C", skill)          # the clone path too
        self.assertLess(skill.index("Update the kernel"),
                        skill.index("Re-emit the project"),
                        "update must come before re-emit")
        self.assertIn("update", skill.split("---")[1].lower())  # frontmatter trigger

    def test_the_published_licence_has_a_file_behind_it(self):
        # the manifests advertise Apache-2.0 in a public catalogue
        self.assertEqual(self.plugin["license"], "Apache-2.0")
        licence = ROOT / "LICENSE"
        self.assertTrue(licence.exists(), "licence published without a LICENSE file")
        self.assertIn("Apache License", read(licence))

    def test_the_plugin_ships_the_skills_and_roles_it_promises(self):
        # a plugin install must carry fde-init (the bootstrap skill the
        # project-level install deliberately excludes) and the six roles
        # (ADR-0014/FWD-018 added walkthrough-evaluator, its write_scope
        # empty by design — spec/roles.toml's own header now reads "Six
        # roles")
        skills = {d.name for d in (ROOT / "skills").iterdir() if d.is_dir()}
        self.assertIn("fde-init", skills)
        self.assertIn("fde-sync", skills)
        roles = {p.stem for p in (ROOT / "agents").glob("fde-*.md")}
        self.assertEqual(len(roles), 6, sorted(roles))


class TestNativeLayerShape(unittest.TestCase):
    """G7/G8 (FWD-020, ADR-0016 Decision 6): not copies — user-owned merge
    targets — so ordinary content assertions, not manifest pairs."""

    def test_claude_md_imports_agents_md_on_its_first_line(self):
        # SETUP §8.3: the whole standard reaches Claude Code through this
        first = read(ROOT / "CLAUDE.md").split("\n", 1)[0]
        self.assertEqual(first, "@AGENTS.md")

    def test_settings_run_the_guard_hook_and_branch_worktrees_from_head(self):
        # SETUP §8.4: the $CLAUDE_PROJECT_DIR form, and isolated roles on
        # the session's HEAD rather than a stale origin/HEAD
        settings = json.loads(read(ROOT / ".claude" / "settings.json"))
        commands = [h.get("command")
                    for entry in settings["hooks"]["PreToolUse"]
                    if entry.get("matcher") == "Write|Edit"
                    for h in entry.get("hooks", [])]
        self.assertIn('python3 "$CLAUDE_PROJECT_DIR/bin/fde/guard.py"',
                      commands)
        self.assertEqual(settings["worktree"]["baseRef"], "head")

    TOOLS = ("Bash", "Edit", "Write", "Read", "Glob", "Grep", "NotebookEdit",
             "WebFetch", "WebSearch")

    def test_settings_open_every_tool(self):
        # FWD-025 / ADR-0019 rule 8: the cycle sign-off is the permission;
        # the install opens the tools so no call waits on a prompt
        allow = json.loads(read(ROOT / ".claude" / "settings.json"))[
            "permissions"]["allow"]
        for tool in self.TOOLS:
            self.assertIn(tool, allow, tool)

    def test_setup_merges_the_allow_list_and_says_so(self):
        setup = " ".join(read(ROOT / "SETUP.md").split())
        self.assertIn("`permissions.allow`", setup)
        for tool in self.TOOLS:
            self.assertIn(f"`{tool}`", setup, tool)
        self.assertIn("tell the user that tool permissions are open", setup)
        # reviews/FWD-025 F2, F4, F5: opt-out survives sync, the merge keeps
        # the user's entries, and the guard's reach is stated as it is
        for rule in ("Unless `fde.config.toml` sets `[tooling] "
                     "open_permissions = false`",
                     "Keep any entries already there.",
                     "Never touch `permissions.ask` or `permissions.deny`",
                     "The guard hook still runs on every `Write`/`Edit`. "
                     "Writes made through `Bash` or `NotebookEdit` are "
                     "contained by the gate",
                     "removing entries alone is undone by the next sync"):
            self.assertIn(rule, setup, rule)
        self.assertNotIn("still runs on every write.", setup)

    def test_sync_tells_the_user_and_config_carries_the_switch(self):
        # reviews/FWD-025 F3: an update that opens permissions says so
        for rel in ("skills/fde-sync/SKILL.md", ".claude/skills/fde-sync/SKILL.md"):
            self.assertIn("tell the user which ones", " ".join(read(ROOT / rel).split()), rel)
        self.assertIn("open_permissions = true",
                      read(ROOT / "templates" / "fde.config.template.toml"))

    def test_adr_states_the_install_allow_list(self):
        # reviews/FWD-025 F1
        adr = " ".join(read(ROOT / "docs/adr/0019-backlog-cycle-demand.md").split())
        self.assertIn("Install and sync open every built-in tool", adr)
        self.assertNotIn("There is no allowlist", adr)


class TestGeneratedSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ROOT / "fde.config.toml", "rb") as fh:
            cls.cfg = tomllib.load(fh)
        with open(ROOT / "spec" / "invariants.toml", "rb") as fh:
            cls.inv = tomllib.load(fh)

    def test_workflow_runs_tests_and_a_ranged_gate_on_full_history(self):
        # content, not identity (ADR-0016 Decision 7): the workflow pair in
        # tests/mirror.toml proves the copy matches its template; this
        # proves the template still fetches full history for a ranged gate
        wf = read(ROOT / ".github" / "workflows" / "fde-gate.yml")
        self.assertIn(self.cfg["stack"]["test_command"], wf)
        self.assertIn("fetch-depth: 0", wf)
        self.assertIn("--since", wf)
        self.assertNotIn("{{TEST_COMMAND}}", wf)

    # ADR-0016 Decision 9 pins, on the template AND the installed copy (a
    # template-plus-copy edit keeps the identity pairs green; these do
    # not). Exact literals, no YAML/shell parsing (FWD-020 F3, F10).
    GATE_STEP = (
        "      - name: FDE gate\n"
        "        run: python bin/fde/verify.py --all --since "
        "\"${{ steps.range.outputs.base }}\"\n")
    # FWD-044 (B-15): the range the gate step reads is computed by the
    # step right before it, from the event's base; exact literals again.
    RANGE_ENV = (
        "        env:\n"
        "          BASE: ${{ github.event.pull_request.base.sha || "
        "github.event.before }}\n"
        "          DEFAULT_BRANCH: "
        "${{ github.event.repository.default_branch }}\n")
    TRIGGER = "\non: [push, pull_request]\n"
    NEVER_IN_THE_GATE_FILES = ("continue-on-error", "if:", '"if"', "'if'",
                               '"on"', "'on'",
                               "|| true", "|| exit 0", "; true", "exit 0")

    def test_ci_gate_step_is_the_last_step_and_cannot_be_made_advisory(self):
        for rel in ("templates/fde-gate.yml", ".github/workflows/fde-gate.yml"):
            with self.subTest(file=rel):
                wf = read(ROOT / rel)
                # every gate (--all), the last step, nothing after it
                self.assertTrue(wf.endswith(self.GATE_STEP), rel)
                # on every push and PR: the exact trigger line, once (F16)
                self.assertEqual(wf.count(self.TRIGGER), 1)
                self.assertEqual(wf.count("\non:"), 1)
                for needle in self.NEVER_IN_THE_GATE_FILES:
                    self.assertNotIn(needle, wf)

    @staticmethod
    def _range_script(wf: str) -> str:
        """The Range step's `run: |` block, dedented: the lines after it
        up to the next step."""
        lines = wf.splitlines()
        start = lines.index("      - name: Range")
        run = lines.index("        run: |", start)
        body = []
        for ln in lines[run + 1:]:
            if ln.startswith("      - "):
                break
            body.append(ln[10:])
        return "\n".join(body) + "\n"

    def test_range_step_feeds_the_gate_and_handles_the_zero_sha(self):
        # the step right before the gate, reading the event's base through
        # env (never ${{ }} inside the script), with the all-zero case
        # routed to the merge-base with the default branch (B-15)
        for rel in ("templates/fde-gate.yml", ".github/workflows/fde-gate.yml"):
            with self.subTest(file=rel):
                wf = read(ROOT / rel)
                self.assertEqual(wf.count("      - name: Range\n"
                                          "        id: range\n"), 1)
                self.assertIn(self.RANGE_ENV, wf)
                _, tail = wf.split("      - name: Range\n")
                self.assertTrue(tail.endswith(self.GATE_STEP))
                self.assertNotIn("      - ", tail[:-len(self.GATE_STEP)])
                script = self._range_script(wf)
                self.assertNotIn("${{", script)
                self.assertIn("*[!0]*) ;;", script)
                self.assertIn('git merge-base HEAD "origin/$DEFAULT_BRANCH"',
                              script)
                self.assertIn('echo "base=$base" >> "$GITHUB_OUTPUT"', script)

    def test_range_step_resolves_the_zero_sha_to_the_merge_base(self):
        # runs the Range step's own shell against a real repository: a
        # new-branch push (all-zero before) gets the merge-base with
        # origin/main, not the fallback; a real SHA passes through; HEAD
        # on the default branch itself, or no merge-base, gives "" (so
        # verify.py falls back to the last commit, never to HEAD..HEAD)
        import tempfile

        def git(cwd, *a):
            return subprocess.run(
                ["git", "-C", str(cwd), *a], check=True,
                capture_output=True, text=True).stdout.strip()

        for rel in ("templates/fde-gate.yml", ".github/workflows/fde-gate.yml"):
            script = self._range_script(read(ROOT / rel))
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "r"
                repo.mkdir()
                git(repo, "init", "-q", "-b", "main")
                git(repo, "config", "user.email", "t@example.invalid")
                git(repo, "config", "user.name", "t")
                git(repo, "config", "commit.gpgsign", "false")
                git(repo, "commit", "-q", "--allow-empty", "-m", "one")
                git(repo, "commit", "-q", "--allow-empty", "-m", "red on main")
                main = git(repo, "rev-parse", "HEAD")
                git(repo, "update-ref", "refs/remotes/origin/main", main)
                git(repo, "checkout", "-q", "-b", "feature")
                git(repo, "commit", "-q", "--allow-empty", "-m", "feature")
                feature = git(repo, "rev-parse", "HEAD")

                def base(before, ref="feature", default="main"):
                    git(repo, "checkout", "-q", ref)
                    out = Path(tmp) / "out"
                    out.write_text("")
                    env = {**os.environ, "BASE": before,
                           "DEFAULT_BRANCH": default,
                           "GITHUB_OUTPUT": str(out)}
                    subprocess.run(["bash", "-e", "-c", script], cwd=repo,
                                   env=env, check=True, capture_output=True)
                    return read(out)

                zero = "0" * 40
                with self.subTest(file=rel, case="new-branch push"):
                    self.assertEqual(base(zero), f"base={main}\n")
                with self.subTest(file=rel, case="empty base"):
                    self.assertEqual(base(""), f"base={main}\n")
                with self.subTest(file=rel, case="real SHA passes through"):
                    self.assertEqual(base(main), f"base={main}\n")
                    self.assertEqual(base(feature), f"base={feature}\n")
                with self.subTest(file=rel, case="default branch itself"):
                    self.assertEqual(base(zero, ref="main"), "base=\n")
                with self.subTest(file=rel, case="no such default branch"):
                    self.assertEqual(base(zero, default="nope"), "base=\n")

    def test_pre_commit_runs_the_staged_gate_first(self):
        # exec replaces the shell, so nothing after it runs; nothing may
        # run before it either: it is the first line that is not the
        # shebang, a comment or blank
        for rel in ("templates/pre-commit", ".githooks/pre-commit"):
            with self.subTest(file=rel):
                text = read(ROOT / rel)
                lines = text.splitlines()
                self.assertEqual(lines[0], "#!/bin/sh")
                code = [ln for ln in lines[1:]
                        if ln.strip() and not ln.lstrip().startswith("#")]
                self.assertEqual(code[0],
                                 "exec python3 bin/fde/verify.py --staged")
                for needle in self.NEVER_IN_THE_GATE_FILES:
                    self.assertNotIn(needle, text)

    def test_installed_pre_commit_is_executable(self):
        # SETUP §6 step 3: "then `chmod +x` it". Git silently skips a
        # non-executable hook, and the byte-identical pair cannot see a
        # mode (FWD-020 F21). Both what runs here (the working tree) and
        # what every clone gets (the index mode, via git — tests only,
        # ADR-0016 Decision 10) must be executable.
        hook = ROOT / ".githooks" / "pre-commit"
        self.assertTrue(os.access(hook, os.X_OK), "not executable")
        staged = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-s", "--",
             ".githooks/pre-commit"], check=True, capture_output=True,
            text=True).stdout.split()
        self.assertEqual(staged[:1], ["100755"])

    def test_kernel_version_matches_the_spec_here_too(self):
        self.assertEqual(self.cfg["project"]["kernel_version"],
                         self.inv["meta"]["kernel_version"])


if __name__ == "__main__":
    unittest.main()
