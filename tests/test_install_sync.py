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
import quietgit  # noqa: E402,F401  (git maintenance off in test repos)

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
             "WebFetch", "WebSearch", "mcp__claude-in-chrome")

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


def _skill() -> str:
    return read(ROOT / "skills" / "fde-sync" / "SKILL.md")


def _setup_s6() -> str:
    setup = read(ROOT / "SETUP.md")
    return setup.split("\n## 6.", 1)[1].split("\n## 7.", 1)[0]


def _adr_pair() -> dict:
    with open(ROOT / "tests" / "mirror.toml", "rb") as fh:
        pairs = tomllib.load(fh)["pair"]
    got = [p for p in pairs if p["source"] == "docs/adr/"]
    return got[0] if len(got) == 1 else {}


class TestKernelAdrsShipped(unittest.TestCase):
    """B-32 (FWD-040): client texts cite "kernel ADR-00NN"; the kernel's
    docs/adr/ reaches the client read-only at .fde/adr/, never at the
    client's own docs/adr/ (C-14 FM3)."""

    def test_the_mirror_manifest_declares_the_pair(self):
        p = _adr_pair()
        self.assertEqual((p.get("copy"), p.get("relation")),
                         (".fde/adr/", "identical"))

    def test_setup_and_sync_name_the_destination_and_the_fence(self):
        s6 = _setup_s6()
        self.assertIn("`docs/adr/` → `.fde/adr/`", s6)
        self.assertIn("read-only", s6)
        self.assertIn("own `docs/adr/`", s6)
        skill = _skill()
        self.assertIn("`.fde/adr/`", skill)
        self.assertIn("own `docs/adr/`", skill)

    def test_this_repository_carries_the_install_copy(self):
        src = sorted(f.name for f in (ROOT / "docs" / "adr").glob("*.md"))
        dst = sorted(f.name for f in (ROOT / ".fde" / "adr").glob("*.md"))
        self.assertTrue(src)
        self.assertEqual(src, dst)

    def test_install_leaves_a_clients_own_adrs_alone(self):
        # FM3 fixture: a client with its own docs/adr/0001 (a number the
        # kernel also uses) receives the manifest's pair; its directory is
        # unchanged afterwards and every kernel ADR lands under .fde/adr/
        import shutil
        import tempfile
        pair = _adr_pair()
        self.assertTrue(pair, "no docs/adr/ pair in tests/mirror.toml")
        body = "# 0001 the client's own decision\n"
        with tempfile.TemporaryDirectory() as tmp:
            client = Path(tmp)
            own = client / "docs" / "adr" / "0001-client-decision.md"
            own.parent.mkdir(parents=True)
            own.write_text(body)
            shutil.copytree(ROOT / pair["source"], client / pair["copy"],
                            dirs_exist_ok=True)
            self.assertEqual([p.name for p in own.parent.iterdir()],
                             [own.name])
            self.assertEqual(own.read_text(), body)
            for f in (ROOT / "docs" / "adr").glob("*.md"):
                self.assertEqual(
                    (client / ".fde" / "adr" / f.name).read_bytes(),
                    f.read_bytes())


# the [backlog] comment lines a sync rewrites (B-38): every form a client
# installed from an earlier template may carry
OLD_BACKLOG_COMMENTS = (
    "# optional cadence layer: backlog + sprints (fde-scrum skill)",
    "# gates the backlog's dated goal: backlog.md needs goal: and date: "
    "(fde-scrum skill)",
)


class TestSyncRewritesTheOldConfigComment(unittest.TestCase):
    """B-38 (FWD-040): the old `[scrum]` comment is rewritten to the
    template's current wording; nothing else in the config changes."""

    @staticmethod
    def _current() -> tuple[str, str]:
        lines = read(ROOT / "templates" / "fde.config.template.toml").splitlines()
        i = lines.index("# [backlog]")
        return lines[i], lines[i + 1]

    def test_sync_names_each_old_form_and_the_current_one(self):
        # the rewrite is a migration manifest the sync follows (spec/migrations/)
        skill = read(ROOT / "spec" / "migrations" / "0.21-0.22-backlog-comment.toml")
        for old in OLD_BACKLOG_COMMENTS:
            self.assertIn(old, skill)
        header, enabled = self._current()
        self.assertIn(header, skill)
        # the current wording is the template's, verbatim — a template
        # edit without the skill goes red here
        self.assertIn(enabled, skill)

    def test_sync_bounds_the_rewrite(self):
        skill = _skill()
        self.assertIn("Change nothing else in the config", skill)
        # a live [scrum] header is the FWD-039 alias: left as it is
        self.assertIn("`[scrum]` header stays", skill)
        self.assertIn("follow its `guide`", skill)


class TestSyncWarnsAboutPermissionsUpFront(unittest.TestCase):
    """B-42 (FWD-040): the sync says before it starts that it writes
    .claude/settings.json, and what to do when auto mode blocks it."""

    def test_the_notice_precedes_the_first_step(self):
        head = _skill().split("## 1. Update the kernel", 1)[0]
        self.assertIn("`.claude/settings.json`", head)
        self.assertIn("auto mode", head)
        self.assertIn("re-run", head)
        self.assertIn("half way", head)


class TestSyncRemovesRetiredKernelSkills(unittest.TestCase):
    """FWD-039 review F1 (FWD-040): a client keeps .claude/skills/fde-scrum/
    after the rename unless the sync removes installed `fde-` skills the
    kernel no longer has — and only those."""

    RULE = ("starts with `fde-`", "absent from the kernel's `skills/`",
            "Tell the user which ones were removed")

    def test_sync_and_setup_state_the_rule(self):
        skill = " ".join(_skill().split())
        for needle in self.RULE:
            self.assertIn(needle, skill)
        s8 = read(ROOT / "SETUP.md").split("\n## 8.", 1)[1].split("\n## 9.", 1)[0]
        s8 = " ".join(s8.split())
        self.assertIn("starts with `fde-`", s8)
        self.assertIn("no longer exists in the kernel's `skills/`", s8)
        self.assertIn("tell the user which ones", s8)

    def test_the_rule_on_a_client_removes_only_retired_kernel_skills(self):
        # the rule as the skill states it, applied to a client that
        # carries the renamed fde-scrum and a skill of its own
        import shutil
        import tempfile
        kernel = {d.name for d in (ROOT / "skills").iterdir() if d.is_dir()}
        self.assertNotIn("fde-scrum", kernel)
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / ".claude" / "skills"
            for name in ("fde-scrum", "fde-sync", "my-deploy", "scrum"):
                (installed / name).mkdir(parents=True)
                (installed / name / "SKILL.md").write_text(name)
            removed = sorted(d.name for d in installed.iterdir()
                             if d.name.startswith("fde-")
                             and d.name not in kernel)
            for name in removed:
                shutil.rmtree(installed / name)
            self.assertEqual(removed, ["fde-scrum"])
            self.assertEqual(sorted(d.name for d in installed.iterdir()),
                             ["fde-sync", "my-deploy", "scrum"])

    def test_this_repository_has_no_retired_kernel_skill_installed(self):
        kernel = {d.name for d in (ROOT / "skills").iterdir() if d.is_dir()}
        stale = [d.name for d in (ROOT / ".claude" / "skills").iterdir()
                 if d.is_dir() and d.name.startswith("fde-")
                 and d.name not in kernel]
        self.assertEqual(stale, [])


KERNEL_0_21_0 = "5127c29"   # "0.21.0: review by weight" — before FWD-039/040


class TestDowngradeIgnoresTheNewShapes(unittest.TestCase):
    """C-14 deploy step 3: a client that rolls back keeps a `[backlog]`
    key and a `.fde/adr/` directory; the older gate must judge the project
    exactly as it would without them."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT / "tests"))

    @staticmethod
    def _run(p: Path) -> tuple[int, str]:
        from support import verify
        r = verify(p, "--all")
        return r.returncode, r.stdout

    def _with_and_without(self, p: Path, add) -> tuple:
        from support import commit_all
        commit_all(p, "base")
        before = self._run(p)
        add(p)
        commit_all(p, "new shapes")
        return before, self._run(p)

    @staticmethod
    def _adr(p: Path) -> None:
        import shutil
        shutil.copytree(ROOT / "docs" / "adr", p / ".fde" / "adr")

    def test_the_0_21_0_gate_ignores_fde_adr_and_backlog(self):
        import shutil
        import tempfile
        from support import make_project
        have = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e",
                               f"{KERNEL_0_21_0}^{{commit}}"],
                              capture_output=True)
        if have.returncode:
            self.skipTest("0.21.0 is not in this clone's history")
        with open(ROOT / "spec" / "invariants.toml", "rb") as fh:
            current = tomllib.load(fh)["meta"]["kernel_version"]
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            # the runtime and spec a client has after rolling back to 0.21.0
            shutil.rmtree(p / "bin" / "fde")
            shutil.rmtree(p / ".fde" / "spec")
            arc = subprocess.run(
                ["git", "-C", str(ROOT), "archive", KERNEL_0_21_0,
                 "runtime", "spec"], check=True, capture_output=True).stdout
            subprocess.run(["tar", "-x", "-C", str(p)], input=arc, check=True)
            (p / "runtime").rename(p / "bin" / "fde")
            (p / "spec").rename(p / ".fde" / "spec")
            cfg = p / "fde.config.toml"
            cfg.write_text(cfg.read_text().replace(
                f'kernel_version = "{current}"', 'kernel_version = "0.21.0"'))
            self.assertIn('kernel_version = "0.21.0"',
                          read(p / ".fde" / "spec" / "invariants.toml"))

            def add(q):
                self._adr(q)
                cfg.write_text(cfg.read_text()
                               + "\n[backlog]\nenabled = true\n")
            before, after = self._with_and_without(p, add)
            # the fixture is not a full install, so some gates are red;
            # what matters is that the new shapes change nothing
            self.assertIn("configuration valid", after[1])
            self.assertEqual(after, before)

    def test_the_current_gate_ignores_a_leftover_fde_adr_under_scrum(self):
        import tempfile
        from support import make_project
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp, scrum=True)
            before, after = self._with_and_without(p, self._adr)
            self.assertIn("configuration valid", after[1])
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()


class TestRetiredAndMigrations(unittest.TestCase):
    """Retired names and migrations are data the sync reads (learned from
    BMAD's bmod.toml and v6-v7-migration.toml), so their shape is checked
    here rather than trusted."""

    @staticmethod
    def _ver(v: str) -> tuple:
        return tuple(int(x) for x in v.split("."))

    def test_a_retired_skill_is_gone_and_its_new_name_ships(self):
        import tomllib
        retired = tomllib.loads(read(ROOT / "spec" / "retired.toml"))
        skills = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
        froms = set()
        for entry in retired.get("renamed", []) + retired.get("removed", []):
            self.assertIn(entry["kind"], ("skill", "config"), entry)
            self.assertNotIn(entry["from"], froms, "a retired name is listed twice")
            froms.add(entry["from"])
            if entry["kind"] == "skill":
                self.assertNotIn(entry["from"], skills,
                                 f"{entry['from']} is retired but still ships")
                if "to" in entry:
                    self.assertIn(entry["to"], skills, entry)
        tos = {e.get("to") for e in retired.get("renamed", [])}
        self.assertFalse(froms & tos, "a retired name was reused")

    def test_every_migration_carries_its_whole_contract(self):
        import tomllib
        kernel = tomllib.loads(read(ROOT / "spec" / "invariants.toml"))["meta"]["kernel_version"]
        files = sorted((ROOT / "spec" / "migrations").glob("*.toml"))
        self.assertGreaterEqual(len(files), 2)
        ids = set()
        for f in files:
            m = tomllib.loads(read(f))["migration"]
            for key in ("id", "from", "to", "title", "summary", "detect", "guide"):
                self.assertTrue(str(m.get(key, "")).strip(), f"{f.name}: {key}")
            self.assertTrue(m.get("checklist"), f"{f.name}: checklist")
            self.assertLess(self._ver(m["from"]), self._ver(m["to"]), f.name)
            self.assertLessEqual(self._ver(m["to"]), self._ver(kernel), f.name)
            self.assertNotIn(m["id"], ids, f.name)
            ids.add(m["id"])

    def test_install_copies_both_and_the_sync_reads_both(self):
        setup = " ".join(read(ROOT / "SETUP.md").split())
        self.assertIn("`spec/retired.toml`, `spec/migrations/*.toml` → `.fde/spec/`", setup)
        skill = " ".join(_skill().split())
        self.assertIn("## 3. Retired names and migrations", skill)
        self.assertIn("A retired name is never reused.", skill)
        self.assertIn("check its `detect` signals (read only)", skill)


class TestErosionRatchetAtInstallAndSync(unittest.TestCase):
    """SlopCodeBench gap 3: no client declared an [erosion] budget, so the
    gate never ran. Install and sync now write one from the project's own
    measurement and tell the owner; a declared budget is never touched."""

    def test_setup_and_sync_state_the_ratchet(self):
        setup = " ".join(read(ROOT / "SETUP.md").split())
        self.assertIn("8. Erosion ratchet.", setup)
        self.assertIn("`python3 bin/fde/erosion.py --ratchet`", setup)
        self.assertIn("A project that already declares a ceiling is never touched.", setup)
        self.assertIn("Tell the owner, in one line, the ceilings written", setup)
        skill = " ".join(_skill().split())
        self.assertIn("declares no `[erosion]` ceiling gets one now", skill)
        self.assertIn("A declared budget is never touched.", skill)
        tpl = read(ROOT / "templates" / "fde.config.template.toml")
        self.assertIn("max_structural_erosion", tpl)

    def test_the_ratchet_prints_a_budget_the_gate_accepts(self):
        import sys
        import tempfile
        from support import commit_all, make_project
        sys.path.insert(0, str(ROOT / "runtime"))
        from fde_lib import Config, Spec, validate
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            (p / "src").mkdir(exist_ok=True)
            (p / "src" / "a.py").write_text(
                "def f(x):\n    if x:\n        return 1\n    return 2\n")
            commit_all(p, "code")
            out = subprocess.run(
                [sys.executable, str(p / "bin" / "fde" / "erosion.py"), "--ratchet"],
                cwd=p, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            budget = tomllib.loads(out.stdout)["erosion"]
            self.assertIn("window", budget)
            self.assertTrue(any(k.startswith("max_") for k in budget), budget)
            c = Config(path=p / "fde.config.toml", raw={"erosion": budget},
                       weights={}, depths={})
            self.assertNotIn("EROSION-BUDGET",
                             {v.code for v in validate(c, Spec.load())})


class TestReconcileReadsAClientShapedProject(unittest.TestCase):
    """The sync's step 4 reads what the new rules flag. On a project shaped
    like a client project at 0.22 — an unsigned L cycle of 14 demands with no `files`,
    a draft cycle, long backlog items — every tool it names runs and names
    the work."""

    def test_the_reconcile_tools_name_the_work(self):
        import sys
        import tempfile
        from support import commit_all, make_project
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            rows = "".join(f"| CTR-{i} | back | — | — | slice {i} | A1 | — |\n"
                           for i in range(1, 15))
            (p / "cycles" / "C-4").mkdir(parents=True)
            (p / "cycles" / "C-4" / "plan.md").write_text(
                "cycle: C-4\nstate: planned\ndate: 2026-09-30\nsize: L\n\n"
                "## Acceptance criteria\n\n- A1 (2026-09-30) contracts ship\n\n"
                "## Demands\n\n| id | layer | depends on | files | what | meets | follows |\n"
                "|---|---|---|---|---|---|---|\n" + rows)
            (p / "cycles" / "C-5").mkdir()
            (p / "cycles" / "C-5" / "plan.md").write_text("cycle: C-5\nstate: draft\n")
            (p / "backlog.md").write_text(
                "goal: x\ndate: 2026-09-30\n\n## Backlog\n\n"
                "- B-57 short item with a pointer to docs/vision.md\n"
                "- B-58 " + " ".join(["design detail"] * 40) + "\n")
            commit_all(p, "client-shaped")
            run = lambda *a: subprocess.run([sys.executable, *a], cwd=p,
                                            capture_output=True, text=True)
            panel = run("bin/fde/status.py", "--panel")
            self.assertEqual(panel.returncode, 0, panel.stderr)
            self.assertIn("C-4", panel.stdout)
            waves = run("bin/fde/status.py", "--waves", "C-4")
            self.assertEqual(waves.returncode, 0, waves.stderr)
            self.assertIn("no `files` declared", waves.stdout)
            length = run("bin/fde/verify.py", "--gate", "backlog-length")
            self.assertIn("B-58", length.stdout)
            self.assertNotIn("B-57", length.stdout)
            full = run("bin/fde/verify.py", "--all")
            self.assertNotIn("Traceback", full.stderr)
