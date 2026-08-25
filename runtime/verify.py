#!/usr/bin/env python3
"""
verify — the gate. One verifier, three callers: pre-commit, CI, by hand.

This is where the invariant stops being a recommendation. A skill is a
suggestion; the model ignores it when context gets tight. An exit code is a
wall.

Runs on pure stdlib, in the client's environment, without the kernel
installed (I6).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import (  # noqa: E402
    DEFAULT_BEHAVIOR_PATHS,
    DEFAULT_EVAL_PATHS,
    Config,
    Spec,
    escalated_security_floor,
    gate_paths,
    path_matches,
    project_root,
    validate,
)

# git's well-known empty tree: diffing against it means "everything in HEAD"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

KNOWN_GATES = ("config", "eval", "eval-coverage", "adversarial-isolation",
               "finding-discipline", "promotion-criteria", "observability",
               "portability", "artifact-handoff", "scrum", "traceability",
               "erosion", "divergence", "survey", "walkthrough", "rule-lane")

# vendor trees never count as an observability signal (I5) — a match inside
# node_modules or a virtualenv is someone else's instrumentation
VENDOR_PATHS = ("node_modules/", ".venv/", "venv/", "vendor/", "dist/", "build/", "__pycache__/")


class GitOpFailure(RuntimeError):
    """A git subprocess genuinely failed (non-zero exit, or git missing
    from PATH) — kept distinguishable from git succeeding with a
    legitimately empty result, so a permission error, a lock, a
    corrupted object, or a disk I/O problem on `.git` can never silently
    read the same as "nothing found".

    This is `Gate._git`'s DEFAULT contract as of reviews/FWD-019 round 3
    (F9), not an opt-in reserved for one hardened call site. Three rounds
    of the identical defect class recurring is what forced the inversion:
    F4 hardened `triage._git` (its own, separate wrapper) directly; F6
    found `Gate._commits_in_range`'s own `git log` call still routed
    through the permissive `Gate._git` and fixed it by adding a SECOND,
    narrowly-scoped `_git_strict` used only there; F9 found
    `_commits_in_range` ALSO calls `_resolve_range` first, which depends
    on `_rev_ok` — untouched by either prior fix, and still silently
    reading a genuine git failure (a permission error, a lock, a
    corrupted object, a disk I/O problem) the same as "this revision does
    not exist." Hardening one call site at a time does not converge: it
    only guarantees the NEXT call site discovered repeats the mistake.
    `_git` itself is now strict for every caller.

    A caller that genuinely needs the OLD, permissive "a failure and a
    legitimately empty result read the same" behavior opts in explicitly,
    by name, via `Gate._git_lenient` below — never by catching and
    discarding `GitOpFailure` at the call site, which would silently
    recreate this exact bug. Every pre-existing caller of the old
    permissive `_git` was individually re-audited for this round's fix
    (not blanket-wrapped to keep compiling): `changed()` (I1's own file
    list) and `gate_adversarial`'s I3 review/behavior-separation scan
    both needed the strict default too — for each, an unsignaled empty
    result was reading as a false PASS on the very invariant the gate
    exists to check, the same shape of bug as F4/F6/F9. Only
    `gate_observability`'s legacy telemetry/tracing file-listing fallback
    qualifies for `_git_lenient` (see its own comment for why: a failure
    there and a legitimately empty result already produce the identical,
    safe — failing, never falsely-passing — I5 verdict)."""


class Gate:
    def __init__(self, project: Path,
                 behavior_paths: tuple[str, ...] = DEFAULT_BEHAVIOR_PATHS,
                 eval_paths: tuple[str, ...] = DEFAULT_EVAL_PATHS):
        self.project = project
        self.behavior_paths = behavior_paths
        self.eval_paths = eval_paths
        self.results: list[tuple[str, bool, str]] = []

    def add(self, gid: str, passed: bool, msg: str) -> None:
        self.results.append((gid, passed, msg))

    # -- helpers ----------------------------------------------------------
    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        """The one place a `git` subprocess is actually spawned. Raises
        `GitOpFailure` when git itself is missing from PATH; every other
        outcome — including a non-zero exit — is returned as-is, since
        "non-zero" does not always mean "the operation failed": `_rev_ok`
        below relies on this directly, because `rev-parse --verify
        --quiet` legitimately uses exit 1 to mean "no such revision",
        which is not itself a failure to report."""
        try:
            return subprocess.run(
                ["git", *args], cwd=self.project, capture_output=True, text=True, check=False
            )
        except FileNotFoundError as e:
            raise GitOpFailure(f"git not found on PATH: {e}") from e

    def _git(self, *args: str) -> list[str]:
        """The default git-invocation wrapper — strict as of reviews/
        FWD-019 round 3 (F9): raises `GitOpFailure` on a genuine failure
        (non-zero exit, or git missing) rather than collapsing it into the
        same `[]` a query that legitimately found nothing produces. See
        `GitOpFailure`'s own docstring for why this is now the default,
        not an opt-in, and `_git_lenient` below for the deliberate,
        explicitly-named opt-out."""
        out = self._run_git(*args)
        if out.returncode != 0:
            raise GitOpFailure(
                f"git {' '.join(args)} failed (exit {out.returncode}): "
                f"{(out.stderr or '').strip() or '(no stderr on the failing call)'}")
        return [l for l in out.stdout.splitlines() if l.strip()]

    def _git_lenient(self, *args: str) -> list[str]:
        """Deliberate, visible opt-in to the OLD, permissive contract
        `_git` had before round 3 (F9): a genuine git failure collapses
        into the same empty list a query that legitimately found nothing
        produces. Only correct where "git failed" and "git succeeded and
        truly found nothing" are safe to treat alike — meaning EITHER
        outcome already leads to the same, safe (failing/blocking, never
        falsely-passing) verdict for the invariant being checked, so the
        distinction has no observable effect. Call sites must name this
        wrapper explicitly — never re-derive the same leniency by
        catching and discarding `GitOpFailure` locally, which would
        silently recreate the bug this split exists to close."""
        try:
            return self._git(*args)
        except GitOpFailure:
            return []

    def _rev_ok(self, rev: str) -> bool:
        """True when `rev` resolves to a real commit; False when it
        legitimately does not — NEVER when git itself merely failed to
        answer the question, which now raises `GitOpFailure` instead of
        silently returning False (reviews/FWD-019 round 3, F9).

        The distinction this precision protects: `_resolve_range`'s
        tier-2/tier-3 fallback (a fresh repo with no `HEAD~1`, a shallow
        clone) is legitimate and must keep working exactly as before — a
        young repo where `HEAD~1` genuinely does not exist is not a
        failure. A permission error, a lock, a corrupted object, or a
        disk I/O problem while trying to answer the SAME question is a
        different fact and must not cascade to the next tier unsignaled.

        `git rev-parse --verify --quiet <rev>^{commit}` is the one
        invocation in this file where "non-zero exit" is not itself "the
        operation failed": verified empirically, with `--quiet`, git uses
        exit 1 and EMPTY stderr specifically to mean "not a valid object
        name" (true for a genuinely absent rev, and — same shape — for
        `HEAD`/`HEAD~1` in a brand-new repository with zero commits yet,
        an unborn branch, which is exactly as legitimate). A genuine
        operational failure (a corrupted/inaccessible `.git`, a bad
        `--git-dir`) instead exits 128 WITH a `fatal:` stderr message,
        even under `--quiet`. Only the exact quiet-and-silent shape reads
        as "legitimately does not exist"; anything else — including exit
        1 WITH stderr, in case some git build is less quiet than tested
        here — raises `GitOpFailure` rather than guessing."""
        r = self._run_git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
        if r.returncode == 0:
            return True
        if r.returncode == 1 and not (r.stderr or "").strip():
            return False
        raise GitOpFailure(
            f"git rev-parse --verify --quiet {rev}^{{commit}} failed "
            f"(exit {r.returncode}): "
            f"{(r.stderr or '').strip() or '(no stderr on the failing call)'}")

    def _resolve_range(self, since: str | None) -> str | None:
        """The single --since -> HEAD~1..HEAD -> "everything in HEAD"
        fallback CHAIN both changed() and _commits_in_range() apply
        (reviews/FWD-019 round 1 F3; MNT-1/MNT-8) — one place deciding
        WHICH revspec is in scope, so the two callers can no longer drift
        apart from each other by a future edit made in one and missed in
        the other. Returns the revspec to diff/log against for tiers 1-2,
        or None for tier 3 ("everything reachable from HEAD"), since the
        two callers express that tier differently: `git diff` needs the
        empty-tree sentinel as two positional args, `git log` does not
        (walking from HEAD alone already means "everything").

        As of round 3 (F9): `_rev_ok` now raises `GitOpFailure` on a
        genuine git failure instead of silently returning False, so a
        failure checking tier 1 or tier 2 no longer reads as "this
        revision does not exist" and no longer cascades to a narrower
        tier — it propagates out of this method uncaught, same as any
        other `GitOpFailure`. The legitimate fallback (a `since` that
        truly does not resolve; a repo too young for `HEAD~1`) is
        unchanged: `_rev_ok` still returns False, not raises, for that
        case."""
        if since and set(since) != {"0"} and self._rev_ok(since):
            return f"{since}..HEAD"
        if self._rev_ok("HEAD~1"):
            return "HEAD~1..HEAD"
        return None

    def changed(self, staged: bool, since: str | None = None) -> list[str]:
        if staged:
            return self._git("diff", "--cached", "--name-only")
        # CI: diff the pushed/PR range when given; else the last commit;
        # else (first commit, shallow clone) everything in HEAD. Never fall
        # back to ls-files — that made I1 vacuously green.
        rng = self._resolve_range(since)
        if rng is not None:
            return self._git("diff", "--name-only", rng)
        # tier 3 ("everything reachable from HEAD"): in a genuinely fresh
        # repository (zero commits yet, an unborn branch) HEAD itself does
        # not resolve, and `git diff EMPTY_TREE HEAD` fails (exit 128,
        # "fatal: ambiguous argument 'HEAD'") purely because of that — the
        # SAME legitimate case `_rev_ok` already distinguishes from a real
        # git failure (F9), one tier further out. Checking `_rev_ok("HEAD")`
        # first keeps that distinction consistent instead of letting a
        # brand-new project's "nothing has ever been committed" read as a
        # GitOpFailure.
        if not self._rev_ok("HEAD"):
            return []
        return self._git("diff", "--name-only", EMPTY_TREE, "HEAD")

    def _commits_in_range(self, since: str | None) -> list[tuple[str, str]]:
        """(sha, subject) pairs for the range `_resolve_range` selects
        (shared with changed(), F3) — never a range's aggregated diff;
        rule-lane evaluates each claimed commit's own diff in isolation,
        never a bundled push's combined change (FM-8, R3). ONE git log
        invocation combining the SHA list and each commit's subject line
        (reviews/FWD-019 round 1 F5) — gate_rule_lane no longer spawns a
        subprocess per commit just to read its subject.

        `_resolve_range` (F9) and the final `git log` call below (F6, now
        via `_git`'s own strict default as of round 3) can both raise
        `GitOpFailure`: a git failure anywhere in discovering WHICH
        commits are in range — resolving `since`/`HEAD~1`, or the log
        call itself — must never collapse into the same empty list "no
        commits in range" produces, since that would make gate_rule_lane
        silently skip every commit it should have re-verified. Neither is
        caught here; the one caller (`gate_rule_lane`) converts either
        into a blocking verdict.

        Tier 3 ("everything reachable from HEAD") gets the same
        HEAD-existence check `changed()` applies, for the same reason: a
        brand-new repository with zero commits yet is legitimate and must
        keep reading as "no commits in range", not as a git failure —
        `git log HEAD` on an unborn branch fails (exit 128) purely
        because HEAD does not resolve yet."""
        rng = self._resolve_range(since)
        if rng is not None:
            args = ("log", "--format=%H%x1f%s", rng)
        else:
            if not self._rev_ok("HEAD"):
                return []
            args = ("log", "--format=%H%x1f%s", "HEAD")
        pairs = []
        for line in self._git(*args):
            sha, _, subj = line.partition("\x1f")
            pairs.append((sha, subj))
        return pairs

    # -- I1: eval precedes merge ------------------------------------------
    def gate_eval_coverage(self, staged: bool, since: str | None = None,
                            all_: bool = False) -> None:
        # sharpened (FWD-017 R6): a design-surface demand's declared R#
        # criteria (acceptance.md) must each trace to a real, executed
        # journey — a parsed evals/journeys/<demand-id>/*.journey.toml
        # manifest whose `script` file actually exists on disk — not to a
        # file that merely mentions the token as text. The file-level check
        # below only proves an eval was touched, never that it verifies
        # what it claims to. Silent when no demand has a design surface
        # with R# tokens declared.
        try:
            files = self.changed(staged, since)
        except GitOpFailure as e:
            # reviews/FWD-019 round 3, F9: a git failure discovering which
            # files changed must never silently read as "no behavior
            # change" — that would let this exact failure class bypass I1
            # entirely (F9's own end-to-end repro showed this happening,
            # via the SAME _resolve_range changed() and _commits_in_range
            # share). Mechanical certainty is unavailable, so I1 blocks.
            self.add("I1-REQS", False, f"requirement coverage could not be checked: {e}")
            self.add("I1", False,
                     f"could not determine which files changed: {e} — "
                     f"mechanical certainty is unavailable, so I1 defaults "
                     f"to blocking rather than silently reading a git "
                     f"failure as \"no behavior change\"")
            return

        try:
            import design
            import graph
        except Exception as e:
            self.add("I1-REQS", False, f"requirement coverage could not be checked: {e}")
        else:
            specs_dir = self.project / "specs"
            evals_dir = self.project / "evals"
            demand_dirs = sorted(p for p in specs_dir.iterdir() if p.is_dir()) \
                if specs_dir.is_dir() else []

            # under --staged (pre-commit), an old, unrelated demand's gap
            # must not block every future commit from every contributor
            # indefinitely — scope to demands this changeset actually
            # touches, the same way touched_behavior/touched_eval below
            # already scope by `files`.
            #
            # `--since` alone does NOT scope down (FWD-017 F11). CI's own
            # invocation always passes `--since` (it is also the diff
            # range for the file-level I1 check below); treating it as an
            # equivalent blocking-avoidance tier to --staged silently
            # narrowed CI's audit to only the demands a given push
            # touches — the opposite of what the CI tier exists for.
            # --staged is the one tier where "don't block a contributor's
            # unrelated commit" applies; CI is not blocking any specific
            # commit the same way, so it keeps running the full, unscoped
            # audit regardless of --since. An explicit --all also always
            # forces the unscoped audit, as a deliberate override.
            scoped = staged and not all_
            touched_ids = None
            if scoped:
                touched_ids = {graph.canon_demand(m.group(1))
                               for f in files for m in [graph.DEMAND_RE.search(f)] if m}

            checked, r_missing, errored = 0, [], []
            for d in demand_dirs:
                did = graph.canon_demand(d.name)
                if scoped and did not in touched_ids:
                    continue
                try:
                    if not design.has_design_surface(d):
                        continue
                    acc = d / "acceptance.md"
                    acc_text = acc.read_text(encoding="utf-8", errors="ignore") \
                        if acc.is_file() else ""
                    tokens = sorted(set(re.findall(r"\bR\d+\b", acc_text)))
                    if not tokens:
                        continue
                    checked += 1
                    covered = self._journey_coverage(evals_dir, did)
                    gone = [t for t in tokens if t not in covered]
                    if gone:
                        r_missing.append(f"{d.name}: {', '.join(gone)}")
                except Exception as e:
                    # a single demand's I/O failure (permission error,
                    # symlink loop, malformed tree) must not take down
                    # traceability checking for every OTHER demand too —
                    # isolate the blast radius to the demand that broke.
                    errored.append(f"{d.name}: {e}")

            if errored or r_missing:
                parts = []
                if r_missing:
                    parts.append("declared R# missing a real journey under "
                                 f"its own evals/**: {'; '.join(r_missing[:3])}")
                if errored:
                    parts.append("requirement coverage could not be checked "
                                 f"for {len(errored)} demand(s): "
                                 f"{'; '.join(errored[:3])}")
                self.add("I1-REQS", False, "; ".join(parts))
            elif checked:
                self.add("I1-REQS", True,
                         f"{checked} design-surface demand(s), every declared R# "
                         f"traces to a real, executed journey under its own "
                         f"evals/**")

        touched_behavior = [f for f in files if path_matches(f, self.behavior_paths)]
        # .gitkeep is structure, not a measure
        touched_eval = [f for f in files
                        if path_matches(f, self.eval_paths) and not f.endswith(".gitkeep")]
        if not touched_behavior:
            self.add("I1", True, "no behavior change in this changeset")
            return
        if touched_eval:
            self.add("I1", True,
                     f"{len(touched_behavior)} behavior file(s) with "
                     f"{len(touched_eval)} eval file(s)")
            return
        msg = (f"{len(touched_behavior)} behavior file(s) with no corresponding "
               f"entry in {' or '.join(self.eval_paths)}: {', '.join(touched_behavior[:3])}"
               + (" ..." if len(touched_behavior) > 3 else ""))
        if not self._suite_exists():
            msg += (" — no suite exists yet for these roots; the first demand touching "
                    "them pays the bootstrap (runner + first eval). --no-verify only "
                    "defers this same red to CI.")
        self.add("I1", False, msg)

    def _suite_exists(self) -> bool:
        for e in self.eval_paths:
            d = self.project / e
            if d.exists() and any(f.is_file() and f.name != ".gitkeep" for f in d.rglob("*")):
                return True
        return False

    @staticmethod
    def _no_symlink_descendant(base: Path, target: Path) -> bool:
        """True only when `target` is a proper, non-symlinked descendant
        of `base`: every path component strictly between `base` and
        `target`, and `target` itself, is a real directory/file — never a
        symlink — and the relationship holds lexically (no `..` component
        anywhere in between), never merely after resolving.

        This is a categorical, per-component walk, not a
        resolve()-and-compare containment check (FWD-017 F10's original
        fix: `script_path.resolve(strict=True)
        .is_relative_to(root.resolve())`). That check only hardens the
        one leaf it resolves. It is blind to a symlink ABOVE that leaf —
        a symlinked demand-id directory, or any symlinked intermediate
        directory — because such a symlink's own resolved target still
        trivially "contains" everything walked through it. FWD-017 F13:
        `evals/journeys/<demand-id>` itself was a directory symlink to a
        different demand's real tree; every manifest and script under it
        passed the old check, which only ever compared the SCRIPT's
        resolved path against the SYMLINK'S OWN resolved target — never
        checked the root of the containment relationship at all.

        Walking every component individually from `base` down through
        `target` — the demand-id directory, any intermediate directory,
        the manifest file, the script file — and checking
        `Path.is_symlink()` on each is structurally different: a symlink
        anywhere in the chain is rejected the same way, closing the whole
        class of escape (this defect's third recurrence: F1/F2, then F10,
        then F13) instead of hardening one instance of it at a time.
        """
        try:
            rel_parts = target.relative_to(base).parts
        except ValueError:
            return False
        if not rel_parts or ".." in rel_parts:
            return False
        current = base
        for part in rel_parts:
            current = current / part
            if current.is_symlink():
                return False
        return True

    @staticmethod
    def _journey_coverage(evals_dir: Path, did: str) -> set[str]:
        """R# tokens actually traced to a real journey for demand `did`:
        parses evals/journeys/<demand-id>/**/*.journey.toml (the manifest
        shape skills/fde-design/SKILL.md's "Design QA" section documents —
        a `[meta]` table carrying `id`, `demand_id`, `requirements`,
        `script`, `authored_with`) and counts a requirement covered only
        when the manifest's own `script` file exists on disk next to it.
        Scoped to the exact `<demand-id>` path segment under
        evals/journeys/ — never a substring match against the whole path
        (FWD-017 F1) — so a demand-id that is a prefix of another
        (FWD-1/FWD-17) cannot alias. A file that only mentions the R#
        token as narrative text never satisfies this — only a parsed,
        executable manifest does (FWD-017 F2, ADR-0013).

        A malformed manifest (bad TOML) or a missing `script` file simply
        contributes nothing — that read as a genuine gap, not a checker
        failure. An OSError reading a manifest (permission denied, a
        broken symlink) is left to propagate to the caller, which scopes
        it to this one demand (FWD-017 F7) rather than reporting it as an
        indistinguishable missing requirement.

        Every path component from evals/journeys/ down through and
        including the manifest, and separately down through and including
        the `script` file it names, must be a real, non-symlinked
        directory/file with no `..` in between (FWD-017 F10, hardened to
        close F13: see `_no_symlink_descendant`) — this is what stops
        `script` naming a parent-escaping relative path
        (`../FWD-999/real.spec.ts`), an absolute path (which replaces the
        join outright under Path.__truediv__, e.g. `/bin/sh`), a symlinked
        script file, a symlinked manifest file, a symlinked intermediate
        directory, or — F13's exact case — the demand-id directory itself
        (`evals/journeys/<demand-id>`) being a symlink into a different
        demand's real tree. Any one of those makes the journey uncounted,
        the same as if it were never authored.
        """
        covered: set[str] = set()
        root = evals_dir / "journeys" / did
        if not root.is_dir():
            return covered
        journeys_root = evals_dir / "journeys"
        for manifest in sorted(root.rglob("*.journey.toml")):
            if not Gate._no_symlink_descendant(journeys_root, manifest):
                continue
            try:
                with open(manifest, "rb") as fh:
                    data = tomllib.load(fh)
            except tomllib.TOMLDecodeError:
                continue
            meta = data.get("meta", {}) or {}
            script = meta.get("script")
            if not script:
                continue
            script_path = manifest.parent / str(script)
            if not Gate._no_symlink_descendant(journeys_root, script_path):
                continue
            if not script_path.is_file():
                continue
            reqs = meta.get("requirements")
            if not isinstance(reqs, list):
                continue
            for r in reqs:
                m = re.fullmatch(r"R\d+", str(r).strip())
                if m:
                    covered.add(m.group(0))
        return covered

    # -- I2/I3: adversarial review isolated, unable to fix ----------------
    def gate_adversarial(self) -> None:
        reviews = list((self.project / "reviews").rglob("findings.toml"))
        if not reviews:
            self.add("I2", False, "no report in reviews/**/findings.toml — "
                                  "the adversarial review did not run")
            return
        # the finding must declare an isolated context and cannot come from the same hand
        bad = []
        for r in reviews:
            text = r.read_text(encoding="utf-8", errors="ignore")
            if "context_policy" not in text or "artifact_only" not in text:
                bad.append(str(r.relative_to(self.project)))
        # a promoted demand without a recorded review is a bypass, not a gap
        unreviewed = [d.parent.name for d in
                      (self.project / "promotions").rglob("decision.md")
                      if not (self.project / "reviews" / d.parent.name /
                              "findings.toml").exists()]
        if bad:
            self.add("I2", False, f"report without isolation declaration: {', '.join(bad[:3])}")
        elif unreviewed:
            self.add("I2", False,
                     f"promoted without a recorded review: {', '.join(unreviewed[:3])}")
        else:
            self.add("I2", True, f"{len(reviews)} report(s) with isolation declared")

        # I3: findings and behavior never change in the same commit — a
        # reviewer who fixes erases the record of the finding. A git
        # failure scanning this history must not silently read as "clean"
        # (reviews/FWD-019 round 3, F9's own bug class — an unsignaled
        # empty result reading as a false PASS on the invariant a gate
        # exists to check) — so this uses the strict default `_git` and
        # blocks, by name, on `GitOpFailure`, rather than catching and
        # discarding it to keep the loop simple.
        try:
            head_exists = self._rev_ok("HEAD")
        except GitOpFailure as e:
            self.add("I3", False,
                     f"could not check repository state to verify review/"
                     f"behavior separation: {e}")
            return
        if not head_exists:
            # a brand-new repository with zero commits yet is legitimate
            # (same distinction _resolve_range's tiers rely on) — there is
            # no history to scan, so vacuously nothing mixes.
            self.add("I3", True, "no commit mixes review findings with behavior changes")
            return
        try:
            recent = self._git("log", "-20", "--format=%H")
        except GitOpFailure as e:
            self.add("I3", False,
                     f"could not scan recent history to check review/"
                     f"behavior separation: {e} — mechanical certainty is "
                     f"unavailable, so I3 defaults to blocking rather than "
                     f"silently reading a git failure as \"no commit mixes "
                     f"findings with behavior\"")
            return
        dirty = []
        for c in recent:
            try:
                files = self._git("diff-tree", "--root", "--no-commit-id",
                                  "--name-only", "-r", c)
            except GitOpFailure as e:
                self.add("I3", False,
                         f"could not read commit {c[:7]}'s changed files "
                         f"while checking review/behavior separation: {e}")
                return
            # .gitkeep is structure, not a finding
            if (any(f.startswith("reviews/") and not f.endswith(".gitkeep")
                    for f in files)
                    and any(path_matches(f, self.behavior_paths) for f in files)):
                dirty.append(c[:7])
        self.add("I3", not dirty,
                 "no commit mixes review findings with behavior changes" if not dirty
                 else f"findings and behavior changed in the same commit: {', '.join(dirty[:3])}")

    # -- I8: every finding cites a probe or a principle --------------------
    def gate_finding_discipline(self) -> None:
        import tomllib
        reviews = list((self.project / "reviews").rglob("*.toml"))
        bad, total = [], 0
        for r in reviews:
            try:
                with open(r, "rb") as fh:
                    data = tomllib.load(fh)
            except Exception:
                bad.append(f"{r.relative_to(self.project)}: unparseable")
                continue
            for f in data.get("finding", []):
                total += 1
                if not (f.get("probe") or f.get("principle")):
                    bad.append(f"{r.name}: finding without probe or principle "
                               f"— naked opinion is not a finding")
        if bad:
            # an unparseable file is a failure, never a vacuous pass
            self.add("I8", False, "; ".join(bad[:3]))
        elif total == 0:
            self.add("I8", True, "no findings recorded yet — nothing to validate")
        else:
            self.add("I8", True,
                     f"{total} finding(s), every one cites a probe or a principle")

    # -- I4: criteria declared before -------------------------------------
    def gate_promotion_criteria(self) -> None:
        # per demand, not once per repository: every demand directory under
        # specs/ carries its own dated acceptance
        demand_dirs = [d for d in sorted((self.project / "specs").glob("*"))
                       if d.is_dir()]
        if not demand_dirs:
            self.add("I4", False, "no specs/<demand>/ — acceptance criteria "
                                  "were not declared")
            return
        missing = [d.name for d in demand_dirs if not (d / "acceptance.md").exists()]
        undated = [d.name for d in demand_dirs
                   if (d / "acceptance.md").exists()
                   and "date:" not in (d / "acceptance.md")
                   .read_text(encoding="utf-8", errors="ignore").lower()[:400]]
        if missing:
            self.add("I4", False, f"demand(s) without acceptance.md: {', '.join(missing[:3])}")
        elif undated:
            self.add("I4", False, f"criteria without a date: {', '.join(undated[:3])}")
        else:
            self.add("I4", True, f"{len(demand_dirs)} demand(s) with dated criteria")

    # -- I5: observability floor ------------------------------------------
    def gate_observability(self, cfg: Config, spec: Spec) -> None:
        declared = [k for k, v in cfg.raw.get("weights", {}).items() if int(v) > 0]
        obs = self.project / "observability.toml"
        if obs.exists():
            # existence is not a signal — the file must declare signals
            import tomllib
            try:
                with open(obs, "rb") as fh:
                    signals = tomllib.load(fh).get("signals", {}) or {}
            except Exception:
                signals = {}
            if signals:
                self.add("I5", True,
                         f"observability.toml declares {len(signals)} signal(s)")
            else:
                self.add("I5", False,
                         "observability.toml exists but declares no [signals] — "
                         "an empty file is not a floor")
            return
        # only the project's own files count: tracked or untracked-but-not-
        # ignored, and never inside a vendor tree.
        #
        # Deliberately `_git_lenient`, by name (F9 audit): a git failure
        # here and a query that legitimately finds nothing produce the
        # SAME safe outcome below — I5 fails either way, because it only
        # ever passes off `hits` being non-empty, never off the absence of
        # a failure. There is no false-PASS path for a swallowed failure
        # to hide behind here, unlike the F4/F6/F9 bug class this file's
        # other git calls were hardened against.
        files = self._git_lenient("ls-files", "-co", "--exclude-standard")
        hits = [f for f in files
                if ("telemetry" in f.lower() or "tracing" in f.lower())
                and not f.startswith(VENDOR_PATHS)
                and not any(f"/{v}" in f for v in VENDOR_PATHS)]
        if hits:
            self.add("I5", True, f"observability signal present ({hits[0]})")
        else:
            self.add("I5", False,
                     f"{len(declared)} declared attribute(s) with no corresponding signal — "
                     f"none of it is verifiable in production")

    # -- I6: the gate runs at the client ----------------------------------
    def gate_portability(self) -> None:
        runtime = self.project / "bin" / "fde" / "verify.py"
        hook = self.project / ".githooks" / "pre-commit"
        missing = [str(p.relative_to(self.project)) for p in (runtime, hook) if not p.exists()]
        self.add("I6", not missing,
                 "gate self-contained in the repository" if not missing
                 else f"missing: {', '.join(missing)} — the gate does not run without the FDE")

    # -- I7: handoff by artifact ------------------------------------------
    def gate_artifact_handoff(self) -> None:
        expected = ["specs", "docs/adr", "evals", "reviews"]
        missing = [d for d in expected if not (self.project / d).exists()]
        self.add("I7", len(missing) <= 1,
                 "handoff structure present" if len(missing) <= 1
                 else f"handoff directories missing: {', '.join(missing)}")

    # -- scrum mode: cadence gates, active only when [scrum] is enabled ----
    def gate_scrum(self, cfg: Config, explicit: bool = False) -> None:
        # strict boolean: enabled = "false" (a string) must not read as on;
        # validate() flags the type, this gate simply does not arm
        if (cfg.raw.get("scrum", {}) or {}).get("enabled") is not True:
            if explicit:
                self.add("SCRUM", True, "scrum mode off — cadence gates not in force")
            return

        def commits(p: Path) -> bool:
            """Non-empty 'goal:' and 'date:' HEADER LINES (first 30 lines)."""
            if not p.is_file():
                return False
            got = {"goal": False, "date": False}
            text = p.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines()[:30]:
                s = line.strip().lower()
                for k in got:
                    if s.startswith(k + ":") and s[len(k) + 1:].strip():
                        got[k] = True
            return all(got.values())

        self.add("SCRUM", commits(self.project / "backlog.md"),
                 "backlog carries a dated product goal"
                 if commits(self.project / "backlog.md") else
                 "backlog.md must declare non-empty 'goal:' and 'date:' header "
                 "lines (first 30 lines) — items without a ruler cannot be ordered")

        sprints_dir = self.project / "sprints"
        entries = [d for d in sprints_dir.iterdir()
                   if d.is_dir()] if sprints_dir.is_dir() else []
        numbered, stray = [], []
        for d in entries:
            m = re.fullmatch(r"S-(\d+)", d.name)
            (numbered.append((int(m.group(1)), d)) if m else stray.append(d.name))
        if stray:
            self.add("SCRUM-GOAL", False,
                     f"unrecognized directory under sprints/ (names are S-<number>; "
                     f"ordering is numeric): {', '.join(sorted(stray)[:3])}")
            return
        sprints = [d for _, d in sorted(numbered)]
        if not sprints:
            self.add("SCRUM-GOAL", True, "no sprint open yet")
            return
        bad_goal = [d.name for d in sprints if not commits(d / "goal.md")]
        self.add("SCRUM-GOAL", not bad_goal,
                 f"{len(sprints)} sprint(s), every goal committed and dated"
                 if not bad_goal else
                 f"goal.md must declare non-empty 'goal:' and 'date:' header lines "
                 f"(first 30 lines): {', '.join(bad_goal[:3])}")
        unclosed = [d.name for d in sprints[:-1]
                    if not (d / "retro.md").is_file()
                    or not (d / "retro.md").read_text(
                        encoding="utf-8", errors="ignore").strip()]
        self.add("SCRUM-RETRO", not unclosed,
                 "every previous sprint has its retro" if not unclosed
                 else f"no retro, no next sprint — missing or empty: "
                      f"{', '.join(unclosed[:3])}")

    # -- divergence: M/L design surfaces converged only after diverging ---
    def gate_divergence(self) -> None:
        try:
            import design
            found = design.breaches(self.project)
        except Exception as e:
            self.add("DIVERGE", False, f"divergence could not be checked: {e}")
            return
        self.add("DIVERGE", not found,
                 "every M/L design surface records its divergence" if not found
                 else "; ".join(found[:3]))

    # -- erosion: decay stays within the declared budget (opt-in) ---------
    def gate_erosion(self, explicit: bool = False) -> None:
        try:
            import erosion
            declared, breaches, unmeasured = erosion.gate(self.project)
        except Exception as e:
            self.add("EROSION", False, f"erosion could not be measured: {e}")
            return
        if not declared:
            if explicit:
                self.add("EROSION", True,
                         "no [erosion] budget declared — trend measured, not gated")
            return
        # passing with an unmeasured threshold still says so: a green that
        # measured nothing is the failure mode this gate exists to avoid
        self.add("EROSION", not breaches,
                 erosion.verdict(breaches[:3], unmeasured))

    # -- walkthrough: first-contact divergence stays within the declared
    #    budget (opt-in, ADR-0014/FWD-018) --------------------------------
    def gate_walkthrough(self, explicit: bool = False) -> None:
        try:
            import walkthrough
            declared, breaches, unmeasured = walkthrough.gate(self.project)
        except Exception as e:
            self.add("WALKTHROUGH", False, f"walkthrough could not be measured: {e}")
            return
        if not declared:
            if explicit:
                self.add("WALKTHROUGH", True,
                         "no [walkthrough] budget declared — walkthrough mode off")
            return
        self.add("WALKTHROUGH", not breaches,
                 walkthrough.verdict(breaches[:3], unmeasured))

    # -- rule-lane: RULE's own live re-verification (ADR-0015) ------------
    def gate_rule_lane(self, since: str | None = None,
                       explicit: bool = False) -> None:
        """A commit whose first message line self-declares `FORWARD: RULE`
        is re-checked against what it ACTUALLY committed — never trusted
        on the claim alone. Silent when no commit in the examined range
        declares RULE (the CI-tier default posture, matching
        gate_erosion/gate_divergence); an explicit pass only when invoked
        directly (`--gate rule-lane`). Blocking when a claimed commit does
        not actually qualify, naming the commit and the failed criterion
        (FM-2). Evaluates each commit in the range on its OWN diff, never
        the range's aggregate, so a bundled sibling commit can neither
        hide nor manufacture a false block either direction (FM-8, R3).

        A merge commit, a commit touching a binary file, or a git
        subprocess failure while checking any of this is blocking too
        (reviews/FWD-019 round 1 F1/F2/F4) — `eligibility_for_commit`
        converts each into an ineligible verdict once, centrally, so this
        gate needs no special-casing of its own to inherit the fix.

        A git failure one level up — while discovering WHICH commits are
        even in range to check, before any individual commit's diff is
        read — is likewise blocking, never a silent "nothing to
        re-verify" (reviews/FWD-019 round 2, F6): `_commits_in_range`
        raises `GitOpFailure` rather than returning `[]` on a genuine git
        failure, and that failure is mechanical uncertainty exactly as
        ADR-0015 defines it — RULE defaults to never, the same posture
        F4 already established one call site down. Round 3 (F9) found
        `_commits_in_range` calls `_resolve_range` FIRST, which depends on
        `_rev_ok` — a git failure there now raises too, one call further
        upstream, and propagates through `_commits_in_range` untouched
        (no code change needed here beyond this docstring): this `except`
        already catches `GitOpFailure` regardless of which of the two
        call sites inside `_commits_in_range` raised it.

        Never reads, imports, or branches on gate_eval_coverage — I1 is
        completely unmodified by this gate's existence (R6/FM-3)."""
        try:
            import triage
        except Exception as e:
            self.add("RULE-LANE", False, f"rule-lane could not be checked: {e}")
            return

        try:
            in_range = self._commits_in_range(since)
        except GitOpFailure as e:
            self.add("RULE-LANE", False,
                     f"rule-lane could not determine which commits are in "
                     f"range to re-verify: {e} — mechanical certainty is "
                     f"unavailable, so RULE defaults to never (ADR-0015); "
                     f"this blocks rather than silently skipping "
                     f"re-verification")
            return

        declared = [(sha, subj) for sha, subj in in_range
                   if triage.declares_rule(subj)]
        if not declared:
            if explicit:
                self.add("RULE-LANE", True,
                         "no commit in range claims RULE — nothing to "
                         "re-verify")
            return

        try:
            cfg = Config.load(self.project)
        except Exception as e:
            self.add("RULE-LANE", False,
                     f"rule-lane could not load fde.config.toml: {e}")
            return

        bad = []
        for sha, subject in declared:
            elig = triage.eligibility_for_commit(self.project, sha, cfg=cfg)
            if not elig.eligible:
                bad.append(f"{sha[:7]} claims RULE but fails "
                          f"'{elig.criterion}': {elig.detail} — run this "
                          f"demand through the normal XS/S/M/L table instead")
        if bad:
            self.add("RULE-LANE", False, "; ".join(bad[:3]))
        else:
            self.add("RULE-LANE", True,
                     f"{len(declared)} commit(s) claim RULE, all "
                     f"re-verified against their own actual diff")

    # -- survey: the brownfield map is complete, labeled and anchored -----
    def gate_survey(self, explicit: bool = False) -> None:
        try:
            import survey
            present, breaches = survey.check(self.project)
        except Exception as e:
            self.add("SURVEY", False, f"survey could not be checked: {e}")
            return
        if not present:
            if explicit:
                self.add("SURVEY", True, "no discovery/survey.md — a survey is "
                                         "owed by brownfield demands, not by every project")
            return
        self.add("SURVEY", not breaches,
                 "survey complete, every claim labeled, anchor recorded"
                 if not breaches else "; ".join(breaches[:2]))

    # -- traceability: the artifact graph has no forbidden orphans --------
    def gate_traceability(self) -> None:
        try:
            import graph
            orphans = graph.forbidden_orphans(self.project)
        except Exception as e:
            self.add("TRACE", False, f"graph could not be built: {e}")
            return
        self.add("TRACE", not orphans,
                 "artifact graph connected — no forbidden orphans" if not orphans
                 else "; ".join(orphans[:3]))

    # -- config ------------------------------------------------------------
    def gate_config(self, cfg: Config, spec: Spec) -> None:
        viol = validate(cfg, spec)
        self.add("CFG", not viol,
                 "configuration valid" if not viol
                 else "; ".join(f"[{v.code}] {v.message.splitlines()[0]}" for v in viol[:3]))
        # the config's kernel_version against the spec actually installed:
        # they diverge when one half of an update lands (review finding)
        declared = str(cfg.raw.get("project", {}).get("kernel_version", ""))
        installed = str(spec.invariants.get("meta", {}).get("kernel_version", ""))
        if declared and installed and declared != installed:
            self.add("CFG-VER", False,
                     f"fde.config.toml says kernel {declared} but the installed "
                     f".fde/spec is {installed} — an update landed half way; "
                     f"re-run fde sync")

        floor = escalated_security_floor(cfg, spec)
        w = int(cfg.weights.get("security_privacy", 0))
        self.add("CFG-SEC", w >= floor,
                 f"security {w} >= floor {floor} (data class "
                 f"{cfg.raw.get('triage', {}).get('data_class', 'internal')})"
                 if w >= floor else
                 f"security {w} < floor {floor} escalated by the data class — "
                 f"triage raises the floor and weight does not lower it")

    def report(self, fmt: str) -> int:
        failed = [r for r in self.results if not r[1]]
        if fmt == "json":
            print(json.dumps(
                {"passed": not failed,
                 "gates": [{"id": g, "passed": p, "detail": m} for g, p, m in self.results]},
                indent=2, ensure_ascii=False))
        else:
            print()
            for gid, passed, msg in self.results:
                mark = "\033[32m✓\033[0m" if passed else "\033[31m✗\033[0m"
                print(f" {mark} {gid:8} {msg}")
            print()
            if failed:
                print(f"\033[31m{len(failed)} gate(s) failed.\033[0m "
                      f"Invariants have no bypass key — the scope shrinks, the standard does not.")
            else:
                print("\033[32mall gates passed.\033[0m")
        return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="pre-commit mode")
    ap.add_argument("--all", action="store_true", help="CI mode: everything")
    ap.add_argument("--gate", default=None, help="a single specific gate")
    ap.add_argument("--since", default=None,
                    help="CI: diff this rev..HEAD for I1 (push base / PR base)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    if args.gate is not None and args.gate not in KNOWN_GATES:
        print(f"\033[31m✗\033[0m unknown gate '{args.gate}'. "
              f"Valid: {', '.join(KNOWN_GATES)}", file=sys.stderr)
        return 2
    if args.staged and args.gate and args.gate not in ("config", "eval", "eval-coverage"):
        print(f"\033[31m✗\033[0m gate '{args.gate}' runs at the commit/CI tier and is "
              f"skipped under --staged — drop --staged to run it", file=sys.stderr)
        return 2

    project = project_root()
    kernel_spec = project / ".fde"
    spec = Spec.load(kernel_spec if (kernel_spec / "spec").exists() else HERE.parent)
    try:
        cfg = Config.load(project)
    except FileNotFoundError as e:
        print(f"\033[31m✗\033[0m {e}", file=sys.stderr)
        return 1
    except tomllib.TOMLDecodeError as e:
        print(f"\033[31m✗\033[0m fde.config.toml is not valid TOML: {e}",
              file=sys.stderr)
        return 1

    behavior_paths, eval_paths = gate_paths(cfg.raw)
    g = Gate(project, behavior_paths, eval_paths)
    only = args.gate

    def want(name: str) -> bool:
        return only is None or only == name

    if want("config"):
        g.gate_config(cfg, spec)
    if want("eval-coverage") or want("eval"):
        g.gate_eval_coverage(staged=args.staged, since=args.since, all_=args.all)
    if not args.staged:  # pre-commit stays fast; the rest is CI
        if want("adversarial-isolation"):
            g.gate_adversarial()
        if want("finding-discipline"):
            g.gate_finding_discipline()
        if want("promotion-criteria"):
            g.gate_promotion_criteria()
        if want("observability"):
            g.gate_observability(cfg, spec)
        if want("portability"):
            g.gate_portability()
        if want("artifact-handoff"):
            g.gate_artifact_handoff()
        if want("scrum"):
            g.gate_scrum(cfg, explicit=(only == "scrum"))
        if want("traceability"):
            g.gate_traceability()
        if want("erosion"):
            g.gate_erosion(explicit=(only == "erosion"))
        if want("divergence"):
            g.gate_divergence()
        if want("survey"):
            g.gate_survey(explicit=(only == "survey"))
        if want("walkthrough"):
            g.gate_walkthrough(explicit=(only == "walkthrough"))
        if want("rule-lane"):
            g.gate_rule_lane(since=args.since, explicit=(only == "rule-lane"))

    if not g.results:
        print("\033[31m✗\033[0m no gate ran — check the flags", file=sys.stderr)
        return 2
    return g.report(args.format)


if __name__ == "__main__":
    raise SystemExit(main())
