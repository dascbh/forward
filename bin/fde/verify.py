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
from dataclasses import dataclass
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
    cycle_config_violations,
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
               "erosion", "divergence", "survey", "walkthrough", "rule-lane",
               "cycle")

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


@dataclass(frozen=True)
class Reason:
    """Why an examined commit fails C1 against its parent (F46): `kind` is
    one of no-open-cycle, two-open, form, missing-acceptance; `text` is the
    reason with its way out."""
    kind: str
    text: str


class Gate:
    # global git options for the calls one gate makes; the cycle gate sets
    # ("--no-replace-objects",) for its own run only (R4f), every other
    # gate's calls are unchanged
    _git_global: tuple = ()

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
    def _run_git(self, *args: str, binary: bool = False,
                 input: bytes | None = None) -> subprocess.CompletedProcess:
        """The one place a `git` subprocess is actually spawned. Raises
        `GitOpFailure` when git itself cannot even be started — missing
        from PATH (`FileNotFoundError`), present but not executable
        (`PermissionError`), or any other OS-level spawn failure
        (`OSError`; reviews/FWD-019 round 4, F12: a `git` file on PATH
        with its execute bit stripped raises `PermissionError`, not
        `FileNotFoundError` — the narrower catch let that one escape
        uncaught as a raw traceback, discarding every gate result that
        had already run). Every other outcome — including a non-zero
        exit — is returned as-is, since "non-zero" does not always mean
        "the operation failed": `_rev_ok` below relies on this directly,
        because `rev-parse --verify --quiet` legitimately uses exit 1 to
        mean "no such revision", which is not itself a failure to
        report.

        `binary=True` returns stdout/stderr as bytes (FWD-021: a cycle
        file's bytes are decoded by cycle.parse, so an undecodable file is
        a labelled C2 breach, never a decode crash here). `input` feeds
        stdin, in binary mode, for `git cat-file --batch*` (R2h)."""
        try:
            return subprocess.run(
                ["git", *self._git_global, *args], cwd=self.project,
                capture_output=True, text=not binary, check=False, input=input
            )
        except OSError as e:
            raise GitOpFailure(f"git could not be run: {e}") from e

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
        return [(sha, subj) for sha, _parents, subj in self._commit_log(since)]

    def _commit_log(self, since: str | None) -> list[tuple[str, list[str], str]]:
        """(sha, parent shas, subject) for the range `_resolve_range`
        selects, in ONE `git log` (FWD-021): `_commits_in_range` above and
        gate_cycle share this, so there is one range definition, one log
        call per caller and one tier-3 HEAD check. Same failure contract
        as `_commits_in_range`: nothing here catches `GitOpFailure`."""
        return self._log_commits(self._resolve_range(since) or "HEAD")

    def _log_commits(self, rev: str) -> list[tuple[str, list[str], str]]:
        """One `git log` of `rev` (a range, or "HEAD" for everything
        reachable — which a repo with no commit yet legitimately lacks)."""
        if rev == "HEAD" and not self._rev_ok("HEAD"):
            return []
        out = []
        for line in self._git("log", "--format=%H%x1f%P%x1f%s", rev):
            sha, _, rest = line.partition("\x1f")
            parents, _, subj = rest.partition("\x1f")
            out.append((sha, parents.split(), subj))
        return out

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
        files = self.changed(staged, since)

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

    # -- cycle: declared scope, in git before it runs (ADR-0017) ----------
    def gate_cycle(self, cfg: Config, since: str | None = None,
                   explicit: bool = False) -> None:
        """Declared cycle scope. Contract: specs/FWD-021-cycle-scope/
        architecture.md, "Revision — round 4" governing over every earlier
        revision. Run order (round 4 part 0):

        1. cheap arming: a = the working tree's `[cycle] enabled is True`,
           b = `git ls-files -- cycles/` lists a file;
        2-4. under a or b: a symlinked config, a shallow clone, a project
           that is not the git top level — each one red row, then stop;
        5. the range (an unresolvable `--since` is red only under a or b);
        6. one `git log` over the range and the batched opted test over
           every parent (a `cycles` tree, or a parsed `[cycle] enabled =
           true`);
        7. c = some parent in the range is opted. Not armed (no a, b, c):
           silent, or one "not in force" pass under `--gate cycle`. Armed
           by c alone: the step 2-4 rows are checked now;
        8. armed: the working-tree checks (open-cycle C2, C5, parse), then
           every commit with an opted parent is examined. An examined
           merge is red (linear history, R3a); every other examined commit
           is judged against its single parent: own-tree config shape and
           serial order, C1, C4, the transitions' C2/C3/C6.

        Every git call made here carries `--no-replace-objects` (R4f). A
        git failure raises `GitOpFailure`, which `run_gate` turns into a
        red CYCLE row. Every breach is labelled `C<k> <where>: <reason> —
        <way out>`; one CYCLE row joins the first three; a full-history
        run adds R3e's suffix to every commit breach."""
        self._cyc_cache = {}
        self._git_global = ("--no-replace-objects",)
        try:
            self._gate_cycle(cfg, since, explicit)
        finally:
            self._git_global = ()

    def _gate_cycle(self, cfg: Config, since: str | None, explicit: bool) -> None:
        sec = cfg.raw.get("cycle")
        a = isinstance(sec, dict) and sec.get("enabled") is True
        if not a and self._no_repository():
            # never opted (no flag) and no repository at all: nothing can
            # arm the run — silent (R9/R4a). With the flag on, the git
            # failure below stays a red row through run_gate.
            if explicit:
                self.add("CYCLE", True,
                         "cycle mode off — declared-scope gate not in force")
            return
        b = bool(self._git_z("ls-files", "-z", "--", "cycles/"))
        if a or b:
            row = self._cycle_preconditions()
            if row:
                self.add("CYCLE", False, row)
                return
        rev, label, bad = self._cycle_range(since)
        commits = [] if bad else self._log_commits(rev)
        opted = self._opted_trees({p for _s, ps, _j in commits for p in ps})
        if not (a or b or opted):
            if explicit:
                self.add("CYCLE", True,
                         "cycle mode off — declared-scope gate not in force")
            return
        if not (a or b):   # armed by history alone (R4a)
            row = self._cycle_preconditions()
            if row:
                self.add("CYCLE", False, row)
                return
        try:
            import cycle
            import triage
        except Exception as e:
            self.add("CYCLE", False, f"cycle could not be checked: {e}")
            return
        stages = sec.get("stages", []) if isinstance(sec, dict) else []
        if not (isinstance(stages, list) and all(isinstance(x, str) for x in stages)):
            stages = []   # validate() reports it as CYCLE-STAGES in the CFG row
        breaches: list[str] = [bad] if bad else []

        # -- working tree, whenever armed: open cycles in full, C5 ---------
        wt, strays = self._wt_cycles(cycle)
        breaches += strays
        for c in wt:
            if not c.closed:
                breaches += cycle.check_form(c, stages, self._wt_spec_texts(cycle, c))
        breaches += cycle.check_serial(wt, "cycles/")

        # -- each commit with an opted parent -----------------------------
        full = rev == "HEAD"
        n_exam = n_pre = n_root = behavior = rule_exempt = rule_open = 0
        for sha, parents, subj in reversed(commits):
            if not parents or not any(p in opted for p in parents):
                n_pre += 1
                n_root += not parents
                continue
            n_exam += 1
            if len(parents) > 1:
                found = [f"C1 {sha[:7]}: a merge after opt-in (parents "
                         f"{', '.join(p[:7] for p in parents)}) — history must stay "
                         f"linear once cycles exist; rebase the branch onto the "
                         f"protected line (git rebase <main>) and push the result"]
            else:
                found, (b_, e_, o_) = self._examine(cycle, triage, cfg, sha,
                                                    parents[0], subj, explicit)
                behavior += b_
                rule_exempt += e_
                rule_open += o_
            if full:
                found = [f"{x} {self.FULL_HISTORY_SUFFIX}" for x in found]
            breaches += found

        if breaches:
            self.add("CYCLE", False, "; ".join(breaches[:3]))
        else:
            self.add("CYCLE", True,
                     f"{len(wt)} cycle(s); range {label}; {len(commits)} commit(s) "
                     f"in range: {n_exam} examined, {n_pre} pre-opt-in "
                     f"({n_root} root(s)); {behavior} behavior commit(s), all "
                     f"declared before ({rule_exempt} RULE-exempt)")
        if explicit:
            self._cycle_report(cycle, cfg, wt, rule_exempt, rule_open)

    FULL_HISTORY_SUFFIX = (
        "— if this commit is already on the protected line, this push did not "
        "cause it: run the branch through a pull request (its base resolves) "
        "or push again once the branch exists remotely (ADR-0017 R3e)")

    def _no_repository(self) -> bool:
        """True only when git answers that the project is not inside a
        repository; any other failure raises `GitOpFailure` (red)."""
        r = self._run_git("rev-parse", "--git-dir")
        if r.returncode == 0:
            return False
        err = r.stderr if isinstance(r.stderr, str) else r.stderr.decode("utf-8", "replace")
        if "not a git repository" in err.lower():
            return True
        raise GitOpFailure(f"git rev-parse --git-dir failed (exit {r.returncode}): "
                           f"{err.strip() or '(no stderr)'}")

    def _cycle_preconditions(self) -> str | None:
        """Round 4 part 0 steps 2-4, in order: the first red row, or None."""
        link = self.project / "fde.config.toml"
        tracked = self._git_z("ls-files", "-s", "-z", "--", "fde.config.toml")
        if link.is_symlink() or any(e.startswith("120000 ") for e in tracked):
            return ("CYCLE: fde.config.toml must be a regular file (found a "
                    "symlink) — replace the link with the file")
        if self._git("rev-parse", "--is-shallow-repository") == ["true"]:
            return ("CYCLE: shallow clone — the gate needs full history; fetch "
                    "it (fetch-depth: 0, or git fetch --unshallow)")
        prefix = self._git_z("rev-parse", "--show-prefix")
        prefix = prefix[0].strip() if prefix else ""
        if prefix:
            return (f"CYCLE: the project must be the git top level (found "
                    f"prefix {prefix}) — move fde.config.toml to the "
                    f"repository root")
        return None

    def _examine(self, cycle, triage, cfg: Config, sha: str, parent: str,
                 subj: str, explicit: bool) -> tuple[list[str], tuple[int, int, int]]:
        """One examined, single-parent commit against its parent (round 2
        parts 2, 3, 5, 6 and 7a; round 3 part 3; round 4 parts 1-2).
        Returns (breaches, (behavior, RULE-exempt, RULE-eligible-while-
        open)). RULE eligibility is computed at most once (F40)."""
        out: list[str] = []
        s7 = sha[:7]
        files = self._git_z("diff-tree", "-r", "--name-only", "-z", parent, sha)
        st = self._parent_state(parent)
        touches_cfg = "fde.config.toml" in files
        own_raw, own_problem = None, None
        if touches_cfg:   # R4e rule 1: red at the commit that introduces it
            own_raw, own_problem, _bad = self._config_at(sha)
            if own_problem:
                out.append(f"C1 {s7}: this commit makes fde.config.toml "
                           f"{own_problem} — fix it before pushing (amend or "
                           f"rebase); once pushed, the next commit repairs it "
                           f"and this one stays reported")
        if st["problem"]:   # R4e rule 2: repaired by this commit, or red
            if not touches_cfg or own_problem:
                out.append(f"C1 {s7}: parent config is {st['problem']} and this "
                           f"commit does not repair it")
                return out, (0, 0, 0)
            st = self._substituted(st, own_raw)

        by_paths = any(path_matches(f, st["bp"]) for f in files)
        by_config = False
        if touches_cfg:
            by_config = own_raw is None or any(
                st["raw"].get(k) != own_raw.get(k) for k in ("gate", "triage", "cycle"))

        cyc_files = sorted({f for f in files if f.startswith("cycles/")
                            and cycle.cycle_number(f[len("cycles/"):]) is not None})
        opens = [f for f in cyc_files if self._cycle_at(cycle, parent, f) is None
                 and self._cycle_at(cycle, sha, f) is not None]
        closes = [f for f in cyc_files if self._cycle_at(cycle, sha, f) is not None
                  and self._cycle_at(cycle, parent, f) is not None
                  and not self._cycle_at(cycle, parent, f).closed
                  and self._cycle_at(cycle, sha, f).closed]
        if opens and closes:   # R3c
            cn = self._cycle_at(cycle, parent, closes[0]).ident
            cm = self._cycle_at(cycle, sha, opens[0]).ident
            out.append(f"C4 {s7}: closes {cn} and opens {cm} in one commit — "
                       f"commit the close first, then open {cm} with its "
                       f"## Intake in a separate commit")
        if any(f.startswith("cycles/") for f in files):   # R4d: C's own tree
            out += self._serial_at(cycle, sha, opens)

        counts = (0, 0, 0)
        if by_paths or by_config:
            claim = triage.declares_rule(subj)
            may_rule = by_paths and not by_config
            elig = None
            if may_rule and (claim or explicit):
                elig = triage.eligibility_for_commit(self.project, sha, cfg=cfg).eligible
            r = self._c1_reason(cycle, parent, st["stages"])
            if r is None:
                counts = (1, 0, int(bool(elig)))
            elif claim and may_rule and elig:
                counts = (1, 1, 0)   # R1h: claimed AND verified
            else:
                counts = (1, 0, 0)
                text = r.text
                if r.kind == "no-open-cycle":
                    if by_config:
                        text += "; a change to [gate]/[triage]/[cycle] always needs an open cycle"
                    elif not claim:
                        text += ", or declare \"FORWARD: RULE — <reason>\" if it is RULE-sized"
                out.append(f"C1 {s7}: {text}")
            for f in opens:   # R1i: a behavior commit never opens a cycle
                out.append(f"C1 {s7}: a behavior commit opens {f}: close, open, "
                           f"code — three commits; commit the new cycle first, "
                           f"then the code")
            if by_config and own_raw is not None:
                out += self._stage_removal(cycle, sha, parent, st, own_raw)
        for f in cyc_files:
            out += self._cycle_transition(cycle, sha, parent, st, f)
        return out, counts

    def _serial_at(self, cycle, sha: str, opens: list[str]) -> list[str]:
        """R4d: C5 on the commit's OWN tree. Opening a cycle while another is
        open names the one legal order."""
        tree = self._tree_cycles(cycle, sha)
        found = cycle.check_serial(tree, sha[:7])
        if not found:
            return []
        open_now = sorted((c for c in tree if not c.closed), key=lambda c: c.number)
        added = [c for c in open_now if c.path in opens]
        if added and len(open_now) > 1:
            m = added[-1]
            n = [c for c in open_now if c is not m][-1]
            return [f"C5 {sha[:7]}: opens {m.ident} while {n.ident} is open — close "
                    f"{n.ident} first (separate commit), then open {m.ident}"]
        return found

    def _stage_removal(self, cycle, sha: str, parent: str, st: dict,
                       own_raw: dict) -> list[str]:
        """R2d (addendum 2026-09-28): a stage leaves [cycle].stages while the
        parent's open cycle carries its key — red unless this commit closes
        that cycle; the close is then judged against the parent's config,
        where the stage is still declared (C2, C3, capture)."""
        c_sec = own_raw.get("cycle")
        c_stages = c_sec.get("stages", []) if isinstance(c_sec, dict) else []
        c_stages = c_stages if isinstance(c_stages, list) else []
        out = []
        for s in [x for x in st["stages"] if x not in c_stages]:
            for c in self._tree_cycles(cycle, parent):
                if c.closed or not any(cycle.item_key(it) == s for it in c.done):
                    continue
                now = self._cycle_at(cycle, sha, c.path)
                if now is not None and now.closed:
                    continue   # removed in the commit that closes the carrier
                out.append(f"C1 {sha[:7]}: removes stage '{s}' while {c.ident} "
                           f"carries it — remove the stage in the commit that "
                           f"closes {c.ident} (resolve its '{s}' item; a [-] item "
                           f"is carried to ## Next cycle)")
        return out

    def _cycle_transition(self, cycle, sha: str, parent: str, st: dict,
                          f: str) -> list[str]:
        """C4 against the single parent (R3a), plus the checks that belong
        to the transition: form, size and C6 at add; form, size, closure
        and the scrum-on capture at close."""
        after = self._cycle_at(cycle, sha, f)
        before = self._cycle_at(cycle, parent, f)
        nums = [] if before is not None else self._tree_numbers(cycle, parent)
        out = cycle.check_transition(f, sha, before, after, nums)
        if out or after is None or after.fatal:
            return out
        where = f"{sha[:7]} {f}"
        ids = [i for i, _ in after.demands()]
        if before is None and not after.closed:
            out += cycle.check_form(after, st["stages"],
                                    self._tree_spec_texts(cycle, sha, ids),
                                    where=where, fix=cycle.FIX_OPENING)
            tree = self._tree_cycles(cycle, parent)
            closed_below = [c for c in tree if c.closed and c.number < after.number]
            backlog = ""
            if closed_below:
                pred = max(closed_below, key=lambda c: c.number)
                k = self._git("log", "-1", "--first-parent", "--format=%H", parent,
                              "--", pred.path)
                backlog = self._tree_text(k[0], "backlog.md") if k else ""
            out += cycle.check_opening(after, tree, backlog, sha)
        elif before is not None and not before.closed and after.closed:
            out += cycle.check_form(after, st["stages"],
                                    self._tree_spec_texts(cycle, parent, ids),
                                    where=where, fix=cycle.FIX_CLOSE)
            out += cycle.check_closure(after, where=where)
            if st["scrum"]:
                out += cycle.check_capture(after, self._tree_text(sha, "backlog.md"), sha)
        return out

    def _opted_trees(self, parents: set) -> set:
        """R3a/R2b/R2h: which of the given commits are OPTED — a `cycles`
        tree, or a config that parses with `[cycle] enabled = true` —
        decided in at most two git calls for the whole range, before
        anything is parsed or reported. Everything else (an undecodable,
        unparseable or too-deeply-nested config, or a symlink's target
        text, F36/F44) is not opted; nothing here is ever a breach."""
        if not parents:
            return set()
        order = sorted(parents)
        req = "".join(f"{p}:cycles\n{p}:fde.config.toml\n" for p in order)
        lines = self._git_input(("cat-file", "--batch-check"), req).decode(
            "utf-8", "replace").splitlines()
        if len(lines) != 2 * len(order):
            raise GitOpFailure(f"git cat-file --batch-check returned {len(lines)} "
                               f"line(s) for {2 * len(order)} object(s)")
        out, need = set(), []
        for i, p in enumerate(order):
            ctype = lines[2 * i].split()
            ftype = lines[2 * i + 1].split()
            if ctype[-1] != "missing" and ctype[1:2] == ["tree"]:
                out.add(p)
            elif ftype[-1] != "missing" and ftype[1:2] == ["blob"]:
                need.append(p)
        if need:
            blobs = self._cat_file_batch([f"{p}:fde.config.toml" for p in need])
            for p, data in zip(need, blobs):
                try:
                    raw = tomllib.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, tomllib.TOMLDecodeError, RecursionError):
                    continue
                sec = raw.get("cycle")
                if isinstance(sec, dict) and sec.get("enabled") is True:
                    out.add(p)
        return out

    def _cat_file_batch(self, objects: list[str]) -> list[bytes]:
        """One `git cat-file --batch` for `objects` (all known to exist)."""
        data = self._git_input(("cat-file", "--batch"),
                               "".join(o + "\n" for o in objects))
        out, i = [], 0
        for o in objects:
            j = data.index(b"\n", i)
            head = data[i:j].split()
            if len(head) != 3:
                raise GitOpFailure(f"git cat-file --batch could not read {o}")
            size = int(head[2])
            out.append(data[j + 1:j + 1 + size])
            i = j + 1 + size + 1
        return out

    def _git_input(self, args: tuple, text: str) -> bytes:
        out = self._run_git(*args, binary=True, input=text.encode("utf-8"))
        if out.returncode != 0:
            raise GitOpFailure(
                f"git {' '.join(args)} failed (exit {out.returncode}): "
                f"{out.stderr.decode('utf-8', 'replace').strip() or '(no stderr)'}")
        return out.stdout

    def _config_at(self, rev: str) -> tuple[dict | None, str | None, set]:
        """R2f/R4e: `rev`'s own fde.config.toml, shape-checked — (raw,
        problem, bad tables). raw is None when the file is not a regular
        file or does not parse ("*" in bad); a missing file reads as {}.
        Only [cycle], [gate] paths and [scrum] are interpreted."""
        key = ("config", rev)
        if key in self._cyc_cache:
            return self._cyc_cache[key]
        entry = [e for e in self._tree_entries(rev) if e[2] == "fde.config.toml"]
        res: tuple[dict | None, str | None, set]
        if not entry:
            res = ({}, None, set())
        elif entry[0][0] == "120000":
            res = (None, "a symlink", {"*"})
        elif entry[0][1] != "blob" or entry[0][0] not in ("100644", "100755"):
            res = (None, "not a regular file", {"*"})
        else:
            try:
                raw = tomllib.loads(self._blob(rev, "fde.config.toml").decode("utf-8"))
            except (UnicodeDecodeError, tomllib.TOMLDecodeError, RecursionError):
                res = (None, "not valid TOML", {"*"})
            else:
                problems, bad = [], set()
                if "cycle" in raw:
                    viol = cycle_config_violations(raw["cycle"])
                    if viol:
                        problems.append(f"invalid ([cycle] "
                                        f"{viol[0].message.removeprefix('[cycle] ')})")
                        bad.add("cycle")
                gate = raw.get("gate", {})
                if not isinstance(gate, dict):
                    problems.append("invalid ([gate] must be a table)")
                    bad.add("gate")
                else:
                    for k in ("behavior_paths", "eval_paths"):
                        v = gate.get(k)
                        if v is not None and not (isinstance(v, list) and all(
                                isinstance(x, str) for x in v)):
                            problems.append(f"invalid ([gate].{k} must be a list "
                                            f"of strings)")
                            bad.add("gate")
                            break
                scrum = raw.get("scrum")
                if scrum is not None and not (isinstance(scrum, dict) and isinstance(
                        scrum.get("enabled", False), bool)):
                    problems.append("invalid ([scrum] malformed)")
                    bad.add("scrum")
                res = (raw, problems[0] if problems else None, bad)
        self._cyc_cache[key] = res
        return res

    @staticmethod
    def _fill_state(raw: dict, problem: str | None, bad: set) -> dict:
        sec = raw.get("cycle") if "cycle" not in bad else None
        gate = raw.get("gate", {}) if "gate" not in bad else {}
        scrum = raw.get("scrum") if "scrum" not in bad else None
        return {"problem": problem, "bad": bad, "raw": raw,
                "stages": list(sec.get("stages", [])) if isinstance(sec, dict) else [],
                "bp": gate_paths({"gate": gate})[0],
                "scrum": isinstance(scrum, dict) and scrum.get("enabled") is True}

    def _parent_state(self, parent: str) -> dict:
        """What an examined commit is judged by, read narrowly from its
        parent's config (R2f): stages, behavior paths, scrum mode, and
        the shape problem if any (R4e)."""
        raw, problem, bad = self._config_at(parent)
        return self._fill_state(raw or {}, problem, bad)

    def _substituted(self, st: dict, own_raw: dict) -> dict:
        """R4e rule 2: the parent's malformed tables replaced by the
        commit's own, well-formed ones."""
        if "*" in st["bad"]:
            raw = dict(own_raw)
        else:
            raw = dict(st["raw"])
            for t in st["bad"]:
                if t in own_raw:
                    raw[t] = own_raw[t]
                else:
                    raw.pop(t, None)
        new = self._fill_state(raw, None, set())
        new["raw"] = st["raw"] if "*" not in st["bad"] else {}
        return new

    def _cycle_range(self, since: str | None) -> tuple[str | None, str | None, str | None]:
        """(rev for `git log`, label, breach). The shared `_resolve_range`
        chain stays as it is for I1 and rule-lane; this gate refuses to
        narrow silently (R1f, F17)."""
        if since and set(since) == {"0"}:
            return "HEAD", "full history (new branch)", None
        if since:
            if self._rev_ok(since):
                s, head = self._git("rev-parse", since, "HEAD")
                return f"{since}..HEAD", f"{s[:7]}..{head[:7]}", None
            return None, None, (
                f"CYCLE range: --since {since} does not resolve (force push or "
                f"shallow clone) — fetch full history (fetch-depth: 0) or re-run "
                f"with --since <merge-base>")
        rng = self._resolve_range(None)
        if rng is not None:
            head = self._git("rev-parse", "HEAD")[0]
            return rng, f"last commit only ({head[:7]})", None
        return "HEAD", "full history", None

    def _cycle_report(self, cycle, cfg: Config, wt, rule_exempt: int,
                      rule_open: int) -> None:
        """R16/F28: informational rows, explicit mode only. The working
        tree's [gate] paths pass R2f's shape check before any git count
        uses them (F38)."""
        open_ = [c for c in wt if not c.closed]
        head = self._rev_ok("HEAD")
        gate = cfg.raw.get("gate", {})
        paths_ok = isinstance(gate, dict) and all(
            gate.get(k) is None or (isinstance(gate.get(k), list)
                                    and all(isinstance(x, str) for x in gate.get(k)))
            for k in ("behavior_paths", "eval_paths"))
        if open_:
            c = open_[-1]
            added = self._git("log", "--diff-filter=A", "--format=%H", "-1",
                              "--", c.path) if head else []
            if not paths_ok:
                since = "n/a (working-tree [gate] paths are not a list of strings)"
            elif added:
                n = self._git("rev-list", "--count", f"{added[0]}..HEAD", "--",
                              *self.behavior_paths)
                since = f"{n[0] if n else 0} behavior commit(s) since it was added"
            else:
                since = "not committed yet"
            self.add("CYCLE-RPT", True, f"open {c.ident} (opened "
                     f"{c.header.get('opened', '?')}): {since}")
        else:
            self.add("CYCLE-RPT", True, "no open cycle — 0 behavior commit(s)")
        backlogs = {}
        wt_backlog = self.project / "backlog.md"
        for c in wt:
            if not c.closed:
                continue
            k = self._git("log", "-1", "--format=%H", "--", c.path) if head else []
            backlogs[c.number] = self._tree_text(k[0], "backlog.md") if k else (
                wt_backlog.read_text(encoding="utf-8", errors="replace")
                if wt_backlog.is_file() else "")
        disp = cycle.disposition_report(wt, backlogs)
        for c in wt:
            if not c.closed:
                continue
            d = disp[c.number]
            parts = ", ".join(f"{k} {len(d[k])}" + (f" ({' '.join(d[k])})" if d[k] else "")
                              for k in cycle.KINDS)
            self.add("CYCLE-RPT", True, f"{c.ident} closed: {len(c.next_items())} "
                                        f"next-cycle item(s) — {parts}")
        self.add("CYCLE-RPT", True,
                 f"{rule_exempt} behavior commit(s) in range RULE-exempt with no "
                 f"valid cycle; {rule_open} RULE-eligible behavior commit(s) "
                 f"made while a cycle was open")

    def _git_z(self, *args: str) -> list[str]:
        """Strict, NUL-separated file lists (F10): a git-quoted path
        (non-ASCII, tab) arrives as itself, so path matching sees it."""
        out = self._run_git(*args, binary=True)
        if out.returncode != 0:
            raise GitOpFailure(
                f"git {' '.join(args)} failed (exit {out.returncode}): "
                f"{out.stderr.decode('utf-8', 'replace').strip() or '(no stderr)'}")
        return [x for x in out.stdout.decode("utf-8", "surrogateescape").split("\0") if x]

    def _wt_cycles(self, cycle) -> tuple[list, list[str]]:
        """The tracked (or staged) files under cycles/, read from disk
        (F13): untracked droppings are ignored, a tracked stray is red."""
        found, strays = [], []
        for rel in self._git_z("ls-files", "-z", "--", "cycles/"):
            if cycle.cycle_number(rel[len("cycles/"):]) is None:
                strays.append(f"C2 {rel}: stray entry — cycles/ holds only "
                              f"C-<n>.md files; git rm it")
                continue
            try:
                data = (self.project / rel).read_bytes()
            except FileNotFoundError:
                continue   # deleted, not yet committed: C4 judges the commit
            except OSError as e:
                strays.append(f"C2 {rel}: unreadable ({e}) — fix its permissions")
                continue
            found.append(cycle.parse(rel, data))
        return sorted(found, key=lambda c: c.number), strays

    def _wt_spec_texts(self, cycle, c) -> dict:
        specs = self.project / "specs"
        ids = [i for i, _ in c.demands()]
        out = {}
        if specs.is_dir():
            for d in sorted(specs.iterdir()):
                if d.is_dir() and any(cycle.dir_matches(d.name, i) for i in ids):
                    sp = d / "spec.md"
                    out[d.name] = sp.read_text(encoding="utf-8", errors="ignore") \
                        if sp.is_file() else None
        return out

    def _tree_has(self, rev: str, path: str) -> bool:
        return path in self._git_z("ls-tree", "--name-only", "-z", rev, "--", path)

    def _blob(self, rev: str, path: str) -> bytes:
        out = self._run_git("show", f"{rev}:{path}", binary=True)
        if out.returncode != 0:
            raise GitOpFailure(
                f"git show {rev[:7]}:{path} failed (exit {out.returncode}): "
                f"{out.stderr.decode('utf-8', 'replace').strip() or '(no stderr)'}")
        return out.stdout

    def _tree_text(self, rev: str, path: str) -> str:
        return self._blob(rev, path).decode("utf-8", "replace") \
            if self._tree_has(rev, path) else ""

    def _tree_entries(self, rev: str) -> list[tuple[str, str, str]]:
        """(mode, type, path) of fde.config.toml and of the entries of
        cycles/ in `rev`, one call."""
        key = ("entries", rev)
        if key not in self._cyc_cache:
            out = []
            for e in self._git_z("ls-tree", "-z", rev, "--", "fde.config.toml", "cycles/"):
                meta, _, path = e.partition("\t")
                m = meta.split()
                out.append((m[0], m[1], path))
            self._cyc_cache[key] = out
        return self._cyc_cache[key]

    def _tree_cycle_names(self, rev: str) -> list[str]:
        return [p for _m, _t, p in self._tree_entries(rev) if p.startswith("cycles/")]

    def _tree_numbers(self, cycle, rev: str) -> list[int]:
        return [n for n in (cycle.cycle_number(x[len("cycles/"):])
                            for x in self._tree_cycle_names(rev)) if n is not None]

    def _cycle_at(self, cycle, rev: str, path: str):
        """The parsed cycle file `path` in `rev`, or None when absent."""
        key = ("cycle", rev, path)
        if key not in self._cyc_cache:
            self._cyc_cache[key] = cycle.parse(path, self._blob(rev, path)) \
                if path in self._tree_cycle_names(rev) else None
        return self._cyc_cache[key]

    def _tree_cycles(self, cycle, rev: str) -> list:
        return [c for c in (self._cycle_at(cycle, rev, n)
                            for n in self._tree_cycle_names(rev)
                            if cycle.cycle_number(n[len("cycles/"):]) is not None)]

    def _c1_reason(self, cycle, parent: str, stages: list) -> "Reason | None":
        """None when `parent`'s tree declares the work: exactly one open,
        well-formed cycle (size is not re-judged here, R1c), serial order
        intact, and every acceptance.md it names for an S+ demand already
        present. Else the first failing reason, with its way out."""
        key = ("c1", parent)
        if key in self._cyc_cache:
            return self._cyc_cache[key]
        cycles = self._tree_cycles(cycle, parent)
        opened = [c for c in cycles if not c.closed]
        reason = None
        if not opened:   # the way out is composed per commit by _examine (F37)
            reason = Reason("no-open-cycle",
                            "no open cycle — open a cycle in an earlier commit")
        elif len(opened) > 1:
            reason = Reason("two-open",
                            f"{len(opened)} open cycles in the parent tree "
                            f"({', '.join(c.ident for c in opened)}) — close all "
                            f"but one in an earlier commit")
        else:
            serial = cycle.check_serial(cycles, "parent tree")
            c = opened[0]
            if serial:
                reason = Reason("two-open", serial[0])
            else:
                form = cycle.check_form(c, stages, None)
                if form:
                    reason = Reason("form", f"the parent's open {c.ident} fails "
                                            f"its form: {form[0]}")
                else:
                    for acc in cycle.acceptance_paths(c):
                        if not self._tree_has(parent, acc):
                            reason = Reason(
                                "missing-acceptance",
                                f"{acc} is absent from the parent tree — commit "
                                f"acceptance.md in an earlier commit than the "
                                f"code it governs (I4)")
                            break
        self._cyc_cache[key] = reason
        return reason

    def _tree_spec_texts(self, cycle, rev: str, ids: list[str]) -> dict:
        """{dir: spec.md text or None} for every specs/<dir> in `rev` that
        matches one of `ids` (normalized, R1c)."""
        out = {}
        for entry in self._git_z("ls-tree", "-z", rev, "--", "specs/"):
            meta, _, path = entry.partition("\t")
            if meta.split()[1:2] != ["tree"]:
                continue
            d = path[len("specs/"):]
            if any(cycle.dir_matches(d, i) for i in ids):
                sp = f"specs/{d}/spec.md"
                out[d] = self._blob(rev, sp).decode("utf-8", "ignore") \
                    if self._tree_has(rev, sp) else None
        return out

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

    def run_gate(fn, *fnargs, gid: str = "GATE", on_git_failure=None, **fnkwargs) -> None:
        """Generic dispatch-level backstop (reviews/FWD-019 round 4, F10):
        every `g.gate_XXX(...)` call below that can raise `GitOpFailure`
        (through `changed()`/`_commits_in_range()`, the two shared range-
        resolution helpers) runs through this ONE implementation instead
        of a per-gate try/except sprinkled through the loop. A
        `GitOpFailure` that escapes the gate method is recorded as a
        blocking result — via `on_git_failure(e)` when the call site
        needs its own message shape, or a generic one keyed on `gid`
        otherwise — rather than crashing the whole `verify.py` run
        (discarding every gate result that already ran, F12's own
        "unhandled traceback" failure mode) or, the original bug this
        whole file's `GitOpFailure` history chases (F4/F6/F9), being
        silently swallowed inside the gate method itself.

        This is where round 3's F9 fix for `gate_eval_coverage` belongs:
        R6 (spec.md, non-negotiable) requires that method's body stay
        byte-identical to its pre-FWD-019 state, so the try/except cannot
        live inside it — it lives here, at the one call site that can
        raise it, instead."""
        try:
            fn(*fnargs, **fnkwargs)
        except GitOpFailure as e:
            if on_git_failure is not None:
                on_git_failure(e)
            else:
                g.add(gid, False,
                     f"{gid} could not run: a git operation failed and "
                     f"mechanical certainty is unavailable: {e}")

    def _eval_coverage_git_failure(e: GitOpFailure) -> None:
        # reviews/FWD-019 round 3, F9: a git failure discovering which
        # files changed must never silently read as "no behavior
        # change" — that would let this exact failure class bypass I1
        # entirely (F9's own end-to-end repro showed this happening,
        # via the SAME _resolve_range changed() and _commits_in_range
        # share). Mechanical certainty is unavailable, so I1 blocks.
        # Moved here from inside gate_eval_coverage's body in round 4
        # (F10) to satisfy R6 — same messages, same safety property.
        g.add("I1-REQS", False, f"requirement coverage could not be checked: {e}")
        g.add("I1", False,
             f"could not determine which files changed: {e} — "
             f"mechanical certainty is unavailable, so I1 defaults "
             f"to blocking rather than silently reading a git "
             f"failure as \"no behavior change\"")

    if want("config"):
        g.gate_config(cfg, spec)
    if want("eval-coverage") or want("eval"):
        run_gate(g.gate_eval_coverage, staged=args.staged, since=args.since,
                 all_=args.all, gid="I1", on_git_failure=_eval_coverage_git_failure)
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
            run_gate(g.gate_rule_lane, since=args.since,
                     explicit=(only == "rule-lane"), gid="RULE-LANE")
        if want("cycle"):
            run_gate(g.gate_cycle, cfg, since=args.since,
                     explicit=(only == "cycle"), gid="CYCLE")

    if not g.results:
        print("\033[31m✗\033[0m no gate ran — check the flags", file=sys.stderr)
        return 2
    return g.report(args.format)


if __name__ == "__main__":
    raise SystemExit(main())
