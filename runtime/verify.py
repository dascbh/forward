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
    backlog_enabled,
    backlog_switch,
    DEFAULT_BEHAVIOR_PATHS,
    DEFAULT_EVAL_PATHS,
    Config,
    Spec,
    canon_demand,
    cycle_dirs,
    cycle_end,
    demand_cycles,
    escalated_security_floor,
    front_demand_criteria,
    gate_paths,
    header_lines,
    path_matches,
    plan_problem,
    project_root,
    promoted_demands,
    read_text,
    reviewed_demands,
    used_backlog_ids,
    validate,
)

# git's well-known empty tree: diffing against it means "everything in HEAD"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# `scrum` is the backlog gate's name before kernel 0.22 (FWD-039), kept as
# an alias so an old client's `--gate scrum` still runs it
GATE_ALIASES = {"scrum": "backlog"}

KNOWN_GATES = ("config", "eval", "eval-coverage", "adversarial-isolation",
               "finding-discipline", "promotion-criteria", "observability",
               "portability", "artifact-handoff", "backlog", "scrum", "traceability",
               "erosion", "divergence", "survey", "walkthrough", "rule-lane",
               "untracked", "backlog-length", "process-dup", "doc-refs", "docs",
               "cycles", "map", "deploy-allow", "migration", "promotion",
               "backlog-cycle", "suite", "scope", "review-rounds")

# vendor trees never count as an observability signal (I5) — a match inside
# node_modules or a virtualenv is someone else's instrumentation
VENDOR_PATHS = ("node_modules/", ".venv/", "venv/", "vendor/", "dist/", "build/", "__pycache__/")


# A backlog item line opens with its id: `- B-<n> …` or `| B-<n> | … |`.
_ITEM_LINE = re.compile(r"^\s*(?:[-*+]\s+|\|\s*)(?:\*\*|`)?B-(\d+)(?:\*\*|`)?(?!\d)\s*(.*)$")
# What may legitimately differ between two copies of one item: the ` → C-<n>`
# grouping mark, a `— discarded…`/`— declined…` suffix, and the evidence
# label, which is re-labelled as evidence lands (fde-backlog-format).
_ITEM_MARK = re.compile(r"\s*→\s*C-\d+\b")
_ITEM_END = re.compile(r"\s+[—–-]{1,2}\s*(?:discarded|declined)\b.*$", re.I)
_ITEM_EVIDENCE = re.compile(r"(?<![\w-])(?:opinion|usage-data|user-test|production)(?![\w-])")


def backlog_items(text: str) -> list[tuple[str, str]]:
    """(`B-<n>`, normalized text) for each line of backlog.md that opens an
    item; the id is normalized as fde_lib.used_backlog_ids normalizes it."""
    out = []
    for line in text.splitlines():
        m = _ITEM_LINE.match(line)
        if not m:
            continue
        body = m.group(2)
        if line.lstrip().startswith("|"):
            # a table row's item is its title cell; the other cells are the
            # description, evidence and size, not the title a list line keeps
            body = body.strip().lstrip("|").split("|")[0]
        body = _ITEM_END.sub("", _ITEM_MARK.sub("", body))
        body = _ITEM_EVIDENCE.sub("", body)
        body = re.sub(r"\s+", " ", body).strip(" —–-")
        out.append((f"B-{int(m.group(1))}", body))
    return out


# A shortened title names the same item only when it is at least this many
# words: two words ("Add tests", "Fix parser") are what parallel checkouts
# open DIFFERENT items with, so a two-word prefix match would hide exactly
# the clash BL-IDS exists to catch; three words is the shortest opening a
# closing list keeps that still singles one item out (review F1,
# DIRECT-2026-09-29-B).
SHORTENED_TITLE_MIN_WORDS = 3


def same_item(a: str, b: str) -> bool:
    """One item, two copies: equal texts, or one the other's opening words
    (an item moved to a closing list keeps its title and drops the rest) —
    whole words only, and at least SHORTENED_TITLE_MIN_WORDS of them. A
    text cut with `…` may end mid-word, so its last word is not evidence."""
    def norm(t: str) -> str:
        t = t.casefold().strip()
        cut_mid_word = re.search(r"\w…$", t) is not None
        t = t.rstrip(" .…(")
        if cut_mid_word:
            t = t.rsplit(" ", 1)[0] if " " in t else ""
        return t.rstrip(" .…(,;:—–-")

    a, b = norm(a), norm(b)
    short, long_ = sorted((a, b), key=len)
    if not short:
        return False
    if short == long_:
        return True
    if len(short.split()) < SHORTENED_TITLE_MIN_WORDS:
        return False
    # the longer text continues at a word boundary: space, punctuation or end
    return long_.startswith(short) and not re.match(r"\w", long_[len(short):])


def _cycle_closed(plan: Path) -> bool:
    """A cycle plan's header ends it closed (ADR-0019 rule 9, as fde-status
    reads it): the first `closed:`/`abandoned:` line with a value decides;
    otherwise the first word of `state:`."""
    return cycle_end(read_text(plan)) == "closed"


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
        self.warned: set[int] = set()

    def add(self, gid: str, passed: bool, msg: str) -> None:
        self.results.append((gid, passed, msg))

    def warn(self, gid: str, msg: str) -> None:
        """A finding that never blocks: recorded as passed, shown as ⚠ and
        marked `warning` in JSON. For checks whose false positives are too
        common to fail on (a draft spec, a stale doc path)."""
        self.warned.add(len(self.results))
        self.results.append((gid, True, msg))

    # -- helpers ----------------------------------------------------------
    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
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
        report."""
        try:
            return subprocess.run(
                ["git", *args], cwd=self.project, capture_output=True, text=True, check=False
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

    def _git_paths(self, cmd: str, *args: str) -> list[str]:
        """A file list from git, NUL-separated (`-z`) and never quoted.
        Without -z, git C-quotes any path with non-ASCII bytes or a tab
        ("src/a\\303\\247.py"); a quoted name matches no declared root, so
        I1 read a behavior change there as no behavior change at all
        (B-12). Strict, like `_git`."""
        out = self._run_git(cmd, "-z", *args)
        if out.returncode != 0:
            raise GitOpFailure(
                f"git {cmd} -z {' '.join(args)} failed (exit {out.returncode}): "
                f"{(out.stderr or '').strip() or '(no stderr on the failing call)'}")
        return [n for n in out.stdout.split("\0") if n.strip()]

    def _git_lenient(self, *args: str, paths: bool = False) -> list[str]:
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
            return self._git_paths(*args) if paths else self._git(*args)
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
            return self._git_paths("diff", "--cached", "--name-only")
        # CI: diff the pushed/PR range when given; else the last commit;
        # else (first commit, shallow clone) everything in HEAD. Never fall
        # back to ls-files — that made I1 vacuously green.
        rng = self._resolve_range(since)
        if rng is not None:
            return self._git_paths("diff", "--name-only", rng)
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
        return self._git_paths("diff", "--name-only", EMPTY_TREE, "HEAD")

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
                touched_ids = {did for f in files for part in Path(f).parts
                               for did in [graph.demand_id(part)] if did}

            checked, r_missing, errored = 0, [], []
            for d in demand_dirs:
                did = graph.canon_demand(d.name)
                if scoped and did not in touched_ids:
                    continue
                try:
                    tokens: set[str] = set()
                    # old layout: a design surface's R# in acceptance.md
                    if design.has_design_surface(d):
                        acc = d / "acceptance.md"
                        acc_text = acc.read_text(encoding="utf-8", errors="ignore") \
                            if acc.is_file() else ""
                        tokens |= set(re.findall(r"\bR\d+\b", acc_text))
                    # cycle layout: the plan criteria a front demand meets
                    # (B-27), from the plan's ## Demands row or its spec
                    tokens |= set(front_demand_criteria(self.project, d) or ())
                    tokens = sorted(tokens)
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
                    parts.append("declared criterion (R#, or a front demand's plan A#) "
                                 "missing a real journey under "
                                 f"its own evals/**: {'; '.join(r_missing[:3])}")
                if errored:
                    parts.append("requirement coverage could not be checked "
                                 f"for {len(errored)} demand(s): "
                                 f"{'; '.join(errored[:3])}")
                self.add("I1-REQS", False, "; ".join(parts))
            elif checked:
                self.add("I1-REQS", True,
                         f"{checked} design-surface or front demand(s), every "
                         f"declared criterion traces to a real, executed "
                         f"journey under its own evals/**")

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
                m = re.fullmatch(r"[A-Z]+\d+", str(r).strip())
                if m:
                    covered.add(m.group(0))
        return covered

    # -- I2/I3: adversarial review isolated, unable to fix ----------------
    def gate_adversarial(self) -> None:
        # every review record: findings.toml, and the plan and delta
        # records beside it (findings-plan.toml, findings-delta.toml)
        reviews = sorted((self.project / "reviews").rglob("findings*.toml"))
        if not reviews:
            self.add("I2", False, "no report in reviews/**/findings*.toml — "
                                  "the adversarial review did not run")
            return
        # the finding must declare an isolated context and cannot come from the same hand
        bad = []
        for r in reviews:
            text = r.read_text(encoding="utf-8", errors="ignore")
            if "context_policy" not in text or "artifact_only" not in text:
                bad.append(str(r.relative_to(self.project)))
        # a promoted demand without a recorded review is a bypass, not a
        # gap — promoted per demand (promotions/<id>/decision.md, the old
        # layout) or per cycle (cycles/C-<n>/promotion.md, ADR-0019)
        reviewed = reviewed_demands(self.project)
        unreviewed = [f"{did} ({src})" for did, src
                      in sorted(promoted_demands(self.project).items())
                      if did not in reviewed]
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
                files = self._git_paths("diff-tree", "--root", "--no-commit-id",
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
        # specs/ has dated criteria — its own acceptance.md (the old
        # layout), or the plan of the cycle it belongs to (ADR-0019 rule
        # 14: cycles/C-<n>/plan.md, linked by the plan's ## Demands table
        # or the spec's `cycle: C-<n>` header line)
        demand_dirs = [d for d in sorted((self.project / "specs").glob("*"))
                       if d.is_dir()]
        cycles = cycle_dirs(self.project)
        # a closed directory cycle is promoted at the cycle level: without
        # promotion.md nothing checked that its demands were reviewed
        # (C-5 F5). Old single-file cycles are not directories.
        unpromoted = [f"{cid} is closed without promotion.md"
                      for cid, cdir in sorted(cycles.items())
                      if _cycle_closed(cdir / "plan.md")
                      and not (cdir / "promotion.md").is_file()]
        if unpromoted:
            self.add("I4", False, "; ".join(unpromoted[:3]))
            return

        def problem(cid: str) -> str | None:
            if cid not in cycles:
                return f"no cycles/{cid}/plan.md"
            return plan_problem(cycles[cid] / "plan.md")

        if not demand_dirs:
            dated = [cid for cid in cycles if problem(cid) is None]
            if dated:
                self.add("I4", True, f"{len(dated)} cycle plan(s) with dated "
                                     f"criteria, no demand specified yet")
            else:
                self.add("I4", False, "no specs/<demand>/ and no dated "
                                      "cycles/C-<n>/plan.md — acceptance "
                                      "criteria were not declared")
            return

        links = demand_cycles(self.project)
        missing, undated, bad_plan = [], [], []
        inherited = 0
        for d in demand_dirs:
            acc = d / "acceptance.md"
            if acc.exists():
                if "date:" not in acc.read_text(
                        encoding="utf-8", errors="ignore").lower()[:400]:
                    undated.append(d.name)
                continue
            cids = sorted(links.get(canon_demand(d.name), ()))
            if not cids:
                missing.append(d.name)
                continue
            probs = [f"{d.name} → {cid}: {problem(cid)}"
                     for cid in cids if problem(cid)]
            if probs:
                bad_plan.extend(probs)
            else:
                inherited += 1
        if missing:
            self.add("I4", False,
                     f"demand(s) without dated criteria — neither "
                     f"specs/<id>/acceptance.md nor a cycle plan (a "
                     f"`cycle: C-<n>` spec line or a row in the plan's "
                     f"## Demands table): {', '.join(missing[:3])}")
        elif undated:
            self.add("I4", False, f"criteria without a date: {', '.join(undated[:3])}")
        elif bad_plan:
            self.add("I4", False, f"cycle criteria not dated or not declared: "
                                  f"{'; '.join(bad_plan[:3])}")
        else:
            self.add("I4", True,
                     f"{len(demand_dirs)} demand(s) with dated criteria"
                     + (f" ({inherited} from their cycle's plan.md)"
                        if inherited else ""))

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
        files = self._git_lenient("ls-files", "-co", "--exclude-standard",
                                   paths=True)
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

    # -- the backlog switch: the backlog's dated goal, only when on --------
    def gate_backlog(self, cfg: Config, explicit: bool = False) -> None:
        # strict boolean and a real table ([backlog], or its old name
        # [scrum]): anything else does not arm; validate() names it
        if not backlog_enabled(cfg.raw):
            if explicit:
                self.add("BACKLOG", True,
                         "backlog switch off — the backlog goal check is not in force")
            return
        name, _ = backlog_switch(cfg.raw)
        p = self.project / "backlog.md"
        # the header only: the lines before the first `## `, as every
        # other header is read (fde_lib.header_lines) — prose below it
        # never counts as a declaration
        got: dict[str, str] = {}
        if p.is_file():
            for line in header_lines(read_text(p)):
                low = line.lower()
                for k in ("goal", "date"):
                    if k not in got and low.startswith(k + ":"):
                        got[k] = line[len(k) + 1:].strip()
        goal, date = got.get("goal", ""), got.get("date", "")
        if goal.lower() == "not set":
            self.add("BACKLOG", False,
                     f"backlog.md says 'goal: not set' but [{name}] enabled = "
                     f"true requires a product goal — set one, or turn the "
                     f"switch off")
            return
        ok = bool(goal and date)
        self.add("BACKLOG", ok,
                 "backlog carries a dated product goal" if ok else
                 "backlog.md must declare non-empty 'goal:' and 'date:' header "
                 "lines (before the first '## ') — items without a ruler "
                 "cannot be ordered")
        # sprints are retired (kernel ADR-0019 rule 13): sprints/ stays
        # readable as history (graph.py) and gates nothing.

    # -- backlog ids: one id, one item, across parallel checkouts ---------
    def _backlog_md(self, place: str) -> str | None:
        if place == "tree":
            p = self.project / "backlog.md"
        elif place.startswith("worktree:"):
            p = Path(place[len("worktree:"):]) / "backlog.md"
        elif place.startswith("ref:"):
            out = self._run_git("show", f"{place[4:]}:backlog.md")
            return out.stdout if out.returncode == 0 else None
        else:
            return None
        return read_text(p) if p.is_file() else None

    def gate_backlog_ids(self, explicit: bool = False) -> None:
        """Where an id is seen (fde_lib.used_backlog_ids) is not where it is
        defined: a plan's `## Items` names an item, backlog.md opens it. A
        duplicate is one id opening two item lines with different texts —
        inside this tree's backlog.md, or between it and another worktree's
        or main's backlog.md."""
        try:
            used = used_backlog_ids(self.project)
        except OSError as e:
            self.add("BL-IDS", False, f"backlog ids could not be read: {e}")
            return
        places = sorted({w for ws in used.values() for w in ws},
                        key=lambda w: (w != "tree", w))
        defs: dict[str, dict[str, list[str]]] = {}
        for place in places:
            text = self._backlog_md(place)
            for bid, item in backlog_items(text or ""):
                defs.setdefault(bid, {}).setdefault(place, []).append(item)
        here = defs and any("tree" in d for d in defs.values())
        problems = []
        for bid, by_place in sorted(defs.items(), key=lambda kv: int(kv[0][2:])):
            mine = by_place.get("tree")
            if not mine:
                continue
            clash = [(a, b) for i, a in enumerate(mine) for b in mine[i + 1:]
                     if not same_item(a, b)]
            if clash:
                a, b = clash[0]
                problems.append(f"{bid} opens two items in backlog.md: "
                                f"'{a}' and '{b}'")
            for place, items in by_place.items():
                other = [t for t in items
                         if not any(same_item(t, m) for m in mine)]
                if place != "tree" and other:
                    problems.append(f"{bid} is '{mine[0]}' in backlog.md but "
                                    f"'{other[0]}' in {place}")
        if problems:
            self.add("BL-IDS", False,
                     "duplicate backlog id — " + "; ".join(problems[:5]) +
                     (f" (+{len(problems) - 5} more)" if len(problems) > 5 else "") +
                     " — give the later item the next free id "
                     "(`fde-backlog`)")
        elif here or explicit:
            self.add("BL-IDS", True,
                     f"backlog ids unique across {len(places) or 1} place(s)")

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

    def gate_erosion_staged(self) -> None:
        """Pre-commit: the add/delete ratio, the one erosion signal cheap
        enough for every commit (owner, 2026-10-01)."""
        try:
            import erosion
            ok, msg = erosion.staged_check(self.project)
        except Exception as e:  # noqa: BLE001 — measured, never a crash
            self.warn("EROSION", f"add/delete could not be measured at commit: {e}")
            return
        if not ok:
            self.add("EROSION", False, msg)

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
                     f"unavailable, so RULE defaults to never (kernel ADR-0015); "
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
                     f"re-run the fde-sync skill")

        floor = escalated_security_floor(cfg, spec)
        w = int(cfg.weights.get("security_privacy", 0))
        self.add("CFG-SEC", w >= floor,
                 f"security {w} >= floor {floor} (data class "
                 f"{cfg.raw.get('triage', {}).get('data_class', 'internal')})"
                 if w >= floor else
                 f"security {w} < floor {floor} escalated by the data class — "
                 f"triage raises the floor and weight does not lower it")

    # -- records the kernel's decisions live in are tracked (I7) -----------
    # A decision on disk but outside git is no record: in one client a
    # demand's spec, review and promotion decision sat untracked for days.
    # Decision records fail; drafts (specs, plan/board/deploy) only warn.
    RECORD_FAIL = (r"^reviews/", r"^promotions/", r"^docs/adr/",
                   r"^cycles/[^/]+/review\.md$", r"^cycles/[^/]+/promotion\.md$")
    RECORD_WARN = (r"^specs/", r"^cycles/[^/]+/(plan|board|deploy)\.md$")

    def gate_untracked_records(self, explicit: bool = False) -> None:
        out = self._run_git("status", "--porcelain", "-z", "--untracked-files=all")
        if out.returncode != 0:
            if explicit:
                self.add("UNTRACKED", True, "not a git checkout — nothing to check")
            return
        untracked = [e[3:] for e in out.stdout.split("\0") if e.startswith("?? ")]
        fail = [p for p in untracked if any(re.search(r, p) for r in self.RECORD_FAIL)]
        draft = [p for p in untracked if p not in fail
                 and any(re.search(r, p) for r in self.RECORD_WARN)]
        if fail:
            self.add("UNTRACKED", False,
                     f"{len(fail)} decision record(s) outside git — commit them "
                     f"(I7): {', '.join(fail[:4])}{' …' if len(fail) > 4 else ''}")
        if draft:
            self.warn("UNTRACKED", f"{len(draft)} draft(s) outside git: "
                      f"{', '.join(draft[:4])}{' …' if len(draft) > 4 else ''}")
        if not fail and not draft and explicit:
            self.add("UNTRACKED", True, "every decision record is tracked")

    # -- a backlog item is one line with a pointer, not a mini-spec --------
    # Calibrated on 2026-09-30 on two client backlogs: their lines have a
    # median of 38-40 words, so the default ceiling is 60 (p90 55-71; the
    # forward's own maximum is 56). Only NEW lines are held to it; the
    # explicit run (`--gate backlog-length`, used by the sync's reconcile)
    # lists every open item over it.
    ITEM_LINE = re.compile(r"^\s*(?:[-*]\s+|\|\s*)(?!\s*[-:]+\s*\|)")

    @staticmethod
    def _item_words(line: str) -> int:
        text = re.split(r"\s[—-]\s*discarded\b", line, maxsplit=1)[0]
        return len(text.replace("|", " ").split())

    def gate_backlog_length(self, cfg: Config, staged: bool, since: str | None = None,
                            explicit: bool = False) -> None:
        from fde_lib import backlog_max_item_words
        limit = backlog_max_item_words(cfg.raw)
        path = self.project / "backlog.md"
        if not path.is_file():
            return
        if explicit:
            lines = [l for l in path.read_text(encoding="utf-8", errors="ignore").splitlines()
                     if self.ITEM_LINE.match(l) and "discarded" not in l.lower()]
            scope = "open item(s)"
        else:
            if staged:
                diff = self._run_git("diff", "--cached", "-U0", "--", "backlog.md")
            else:
                rng = self._resolve_range(since)
                if rng is None:
                    return
                diff = self._run_git("diff", "-U0", rng, "--", "backlog.md")
            if diff.returncode != 0:
                return
            lines = [l[1:] for l in diff.stdout.splitlines()
                     if l.startswith("+") and not l.startswith("+++")
                     and self.ITEM_LINE.match(l[1:])]
            scope = "new line(s)"
        long = [l for l in lines if self._item_words(l) > limit]
        if long:
            ids = [re.search(r"B-\d+", l).group(0) if re.search(r"B-\d+", l)
                   else l.strip()[:30] for l in long]
            self.add("BL-LEN", False,
                     f"{len(long)} backlog {scope} over [backlog] max_item_words "
                     f"({limit}): {', '.join(ids[:5])} — one line with a pointer "
                     f"to the doc that holds the detail")
        elif explicit or lines:
            self.add("BL-LEN", True, f"{len(lines)} backlog {scope} within {limit} words")

    # -- a demand spec cites the plan and the ADRs, it does not rewrite them
    def gate_process_duplication(self, explicit: bool = False) -> None:
        import erosion
        from fde_lib import plan_demands
        k = erosion.CLONE_K

        def windows(text: str) -> set:
            lines = [erosion._normalize(l) for l in text.splitlines()]
            lines = [l for l in lines if len(l) > 3 and not l.startswith(("#", "|---", "```"))]
            return {"\n".join(lines[i:i + k]) for i in range(len(lines) - k + 1)}

        found = []
        for cid, cdir in sorted(cycle_dirs(self.project).items()):
            plan = cdir / "plan.md"
            if not plan.is_file() or _cycle_closed(plan):
                continue
            ptext = plan.read_text(encoding="utf-8", errors="ignore")
            refs = [ptext]
            for adr in sorted(set(re.findall(r"ADR[- ]0*(\d+)", ptext))):
                for f in (self.project / "docs" / "adr").glob(f"{int(adr):04d}*.md"):
                    refs.append(f.read_text(encoding="utf-8", errors="ignore"))
            ref_w = set().union(*(windows(t) for t in refs))
            for did in plan_demands(ptext):
                for spec in (self.project / "specs").glob(f"{did}*/spec.md"):
                    shared = windows(spec.read_text(encoding="utf-8", errors="ignore")) & ref_w
                    if shared:
                        found.append(f"{spec.parent.name} ({len(shared)} block(s))")
        if found:
            self.warn("PROC-DUP", f"spec text repeated from its plan or ADRs, "
                      f"{erosion.CLONE_K}+ lines: {', '.join(found[:4])} — cite the "
                      f"id instead of rewriting it")
        elif explicit:
            self.add("PROC-DUP", True, "no demand spec repeats its plan or ADRs")

    # -- paths the instructions name still exist ----------------------------
    DOC_FILES = ("CLAUDE.md", "README.md", "AGENTS.md")
    DOC_PATH = re.compile(r"`([A-Za-z0-9_.\-/]+)`")

    def gate_doc_refs(self, explicit: bool = False) -> None:
        stale = []
        for name in self.DOC_FILES:
            f = self.project / name
            if not f.is_file():
                continue
            for tok in sorted(set(self.DOC_PATH.findall(f.read_text(encoding="utf-8",
                                                                    errors="ignore")))):
                # a repo path: it has a `/` and starts at a real top-level
                # directory — a bare `plan.md` names a concept and a
                # `owner/repo` slug names a remote, neither is checked
                if tok.startswith(("-", ".", "/", "http")) or "//" in tok or "/" not in tok:
                    continue
                if not (self.project / tok.split("/", 1)[0]).is_dir():
                    continue
                if not (self.project / tok.rstrip("/")).exists():
                    stale.append(f"{name}: {tok}")
        if stale:
            self.warn("DOC-REFS", f"{len(stale)} path(s) named in the docs no longer "
                      f"exist: {', '.join(stale[:5])}{' …' if len(stale) > 5 else ''}")
        elif explicit:
            self.add("DOC-REFS", True, "every path the docs name exists")

    # -- the cycle close reconciles the docs agents load --------------------
    # From 2026-10-01 a promotion.md carries `docs: <files reconciled> | none`,
    # so the risks and priorities CLAUDE.md lists are reread at every close
    # (a client's CLAUDE.md listed two P0s already solved). A close before
    # the rule shipped is not failed after the fact.
    DOCS_LINE_SINCE = "2026-10-01"

    def gate_docs_line(self, explicit: bool = False) -> None:
        missing = []
        for cid, cdir in sorted(cycle_dirs(self.project).items()):
            promo = cdir / "promotion.md"
            if not promo.is_file() or not _cycle_closed(cdir / "plan.md"):
                continue
            text = promo.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^date:\s*(\d{4}-\d\d-\d\d)", text, re.M)
            if not m or m.group(1) < self.DOCS_LINE_SINCE:
                continue
            if not re.search(r"^docs:\s*\S", text, re.M):
                missing.append(cid)
        if missing:
            self.add("DOCS", False, f"closed without a `docs:` line in promotion.md "
                     f"(the files reconciled, or `none`): {', '.join(missing[:4])}")
        elif explicit:
            self.add("DOCS", True, "every recent close names the docs it reconciled")

    # -- cycles running at once do not edit the same files (ADR-0024) -------
    def gate_cycles(self, explicit: bool = False) -> None:
        from fde_lib import running_cycle_conflicts
        plans = {cid: (cdir / "plan.md").read_text(encoding="utf-8", errors="ignore")
                 for cid, cdir in cycle_dirs(self.project).items()
                 if (cdir / "plan.md").is_file()}
        msgs = running_cycle_conflicts(plans)
        clash = [m for m in msgs if "declares no `files`" not in m]
        blind = [m for m in msgs if m not in clash]
        for m in clash[:3]:
            self.add("CYCLES", False, m)
        for m in blind[:3]:
            self.warn("CYCLES", m)
        if not msgs and explicit:
            self.add("CYCLES", True, "running cycles touch disjoint files")

    # -- the product map still matches the code (fde-map) --------------------
    # First version: it warns and never fails. It fails only once usage
    # shows the warning is reliable (owner rule: evidence before a gate).
    def gate_map(self, explicit: bool = False) -> None:
        conv_path = self.project / "docs" / "map" / "conventions.toml"
        if not conv_path.is_file():
            if explicit:
                self.add("MAP", True, "no docs/map/conventions.toml — no product map")
            return
        try:
            import productmap
            conv = productmap.load_conventions(self.project)
            stale = []
            for feature in conv.get("feature", []):
                _, md = productmap.generate(self.project, conv, feature)
                target = self.project / "docs" / "map" / f"{feature['slug']}.md"
                old = target.read_text(encoding="utf-8") if target.is_file() else ""
                if productmap.comparable(old) != productmap.comparable(md):
                    stale.append(str(target.relative_to(self.project)))
        except (Exception, SystemExit) as e:  # a map that cannot build is a warning
            self.warn("MAP", f"the product map could not be built: {e}")
            return
        if stale:
            self.warn("MAP", f"{len(stale)} product map(s) out of date — "
                      f"`python3 bin/fde/productmap.py --write`: {', '.join(stale[:4])}")
        elif explicit:
            self.add("MAP", True, "every product map matches the code")

    # -- a signed deploy carries its own permission (kernel ADR-0025) ------
    def gate_deploy_allow(self, explicit: bool = False) -> None:
        import deployallow
        p = deployallow.plan(self.project)
        if not p["open"]:
            if explicit:
                self.add("DEPLOY-ALLOW", True, "[tooling] open_permissions = false — "
                         "the owner keeps the prompts")
            return
        notes = ([f"{cid} deploy.md has no `## Commands`" for cid in p["no_commands"]]
                 + [f"{cid} has a chained command line (split it)" for cid in p["refused"]]
                 + [f"{cid}: {len(spans)} step(s) chain a declared command"
                    for cid, spans in p["chained_prose"].items()]
                 + ([f"{len(p['missing'])} allow rule(s) missing from .claude/settings.json"]
                    if p["missing"] else []))
        if notes:
            self.warn("DEPLOY-ALLOW", "; ".join(notes[:4]) + " — the signed deploy would stop "
                      "for a permission: declare the commands under `## Commands` "
                      "(fde-spec), then `python3 bin/fde/deployallow.py --write`")
        elif explicit:
            self.add("DEPLOY-ALLOW", True, "every signed deploy carries its allow rules")

    # -- a migration is reversible by construction (kernel ADR-0026) -------
    MIGRATION_MENTION = re.compile(r"\.sql\b|\bmigrations?\b", re.I)
    MIGRATION_FIELDS = ("Migration:", "Checkpoint:", "Rehearsal:", "Rollback:")

    def gate_migration(self, explicit: bool = False) -> None:
        from fde_lib import plan_header
        notes = []
        for cid, cdir in sorted(cycle_dirs(self.project).items()):
            plan, deploy = cdir / "plan.md", cdir / "deploy.md"
            if not plan.is_file() or not deploy.is_file():
                continue
            state = plan_header(plan.read_text(encoding="utf-8", errors="ignore"), "state").lower()
            if not state.startswith(("running", "planned")):
                continue
            text = deploy.read_text(encoding="utf-8", errors="ignore")
            body = re.split(r"^## Commands\s*$", text, maxsplit=1, flags=re.M)[0]
            body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
            if not self.MIGRATION_MENTION.search(body):
                continue
            missing = [f for f in self.MIGRATION_FIELDS if f not in body]
            if missing:
                notes.append(f"{cid} ({', '.join(m.rstrip(':') for m in missing)})")
        if notes:
            self.warn("MIGRATION", "deploy touches the database without declaring "
                      f"{', '.join(notes[:4])} — expand/contract, a checkpoint, a "
                      "rehearsal on a clone and the rollback (kernel ADR-0026)")
        elif explicit:
            self.add("MIGRATION", True, "every live migration declares its protection")

    # -- promotion decides; it does not hand the owner conditions ----------
    # The template's decision is promote | hold (limits per criterion).
    # One client wrote `promote_with_conditions` on every promotion, each
    # with an owner acceptance of residual risks at the end of the cycle —
    # what the sign-off already covered (owner, 2026-10-01).
    PROMOTION_DECISIONS = ("promote", "promote-with-limits", "hold")

    def gate_promotion_decision(self, explicit: bool = False) -> None:
        from fde_lib import plan_header
        notes = []
        for cid, cdir in sorted(cycle_dirs(self.project).items()):
            plan, promo = cdir / "plan.md", cdir / "promotion.md"
            if not plan.is_file() or not promo.is_file():
                continue
            state = plan_header(plan.read_text(encoding="utf-8", errors="ignore"), "state").lower()
            if not state.startswith("running"):
                continue
            decision = plan_header(promo.read_text(encoding="utf-8", errors="ignore"), "decision")
            word = re.split(r"[\s(—–:;,]", decision.strip().strip("*").lower(), maxsplit=1)[0]
            if word and word not in self.PROMOTION_DECISIONS:
                notes.append(f"{cid} ({word})")
        if notes:
            self.warn("PROMOTION", f"decision {', '.join(notes[:4])} is none of promote, "
                      "promote-with-limits, hold — a risk goes to the backlog or the signed "
                      "threat model, a production check to deploy.md, never a condition "
                      "for the owner (fde-promotion)")
        elif explicit:
            self.add("PROMOTION", True, "every running cycle's decision is promote or hold")

    # -- the backlog, the suite and the gate's reach (owner, 2026-10-01) ----
    BL_CYCLE_MAX = 5
    SCOPE_SKIP = (".fde/", ".claude/", "bin/fde/", "cycles/", "specs/", "reviews/", "docs/",
                  "discovery/", "promotions/", "node_modules/", ".venv/", "venv/", "vendor/",
                  "dist/", "build/")

    def gate_backlog_per_cycle(self, explicit: bool = False) -> None:
        """A running cycle adding more than 5 backlog lines (`(C-<n>)`) is
        copying review findings: they stay in findings.toml (fde-review)."""
        from fde_lib import plan_header
        bl = self.project / "backlog.md"
        if not bl.is_file():
            return
        text = re.split(r"(?im)^##[^\n]*(discard|descart)", bl.read_text(encoding="utf-8", errors="ignore"))[0]
        notes = []
        for cid, cdir in sorted(cycle_dirs(self.project).items()):
            plan = cdir / "plan.md"
            if not plan.is_file():
                continue
            if not plan_header(plan.read_text(encoding="utf-8", errors="ignore"), "state").lower().startswith("running"):
                continue
            n = len(re.findall(rf"^\s*[-*]\s+(?:\[.\]\s+)?B-\d+\b.*\({re.escape(cid)}\b", text, re.M))
            if n > self.BL_CYCLE_MAX:
                notes.append(f"{cid} ({n})")
        if notes:
            self.warn("BL-CYCLE", f"{', '.join(notes[:4])} open backlog lines from one cycle, over "
                      f"{self.BL_CYCLE_MAX}: a review finding stays in its findings.toml unless it is "
                      "worth work of its own (fde-review Triage); fde-sync sanitizes")
        elif explicit:
            self.add("BL-CYCLE", True, "no running cycle over 5 backlog lines")

    def gate_suite_record(self, explicit: bool = False) -> None:
        """The last recorded suite run fails: a red main, or a suite that does
        not even collect — then every record says "failed" and means nothing."""
        runs = sorted((self.project / RUNS_DIR).glob("*.json"),
                      key=lambda f: f.stat().st_mtime, reverse=True)
        for f in runs:
            try:
                suite = json.loads(f.read_text(encoding="utf-8")).get("suite") or {}
            except (OSError, ValueError):
                continue
            if "exit_code" not in suite:
                continue
            if suite["exit_code"] != 0:
                self.warn("SUITE", f"the last recorded suite run exits {suite['exit_code']} "
                          f"({str(suite.get('summary', ''))[:80]}): fix or quarantine the reds "
                          "(fde-verify — main is green)")
            elif explicit:
                self.add("SUITE", True, "the last recorded suite run is green")
            return

    def gate_scope(self, explicit: bool = False) -> None:
        """Source code outside every root the gate declares: a change there
        reads as "no behavior change" to I1 (a client's scripts/*.py)."""
        import erosion
        behavior, evals = gate_paths(self.cfg_raw) if hasattr(self, "cfg_raw") else ((), ())
        roots = tuple(behavior) + tuple(evals) + erosion.generated_paths(self.project)
        out = subprocess.run(["git", "ls-files"], cwd=self.project, capture_output=True, text=True)
        dirs: dict[str, int] = {}
        for name in out.stdout.splitlines():
            if Path(name).suffix.lower() not in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
                                                 ".java", ".rb", ".sh"):
                continue
            if name.startswith(self.SCOPE_SKIP) or "/" not in name or erosion._is_test_path(name):
                continue
            if any(v in f"/{name}" for v in ("/layers/", "/third_party/", "/vendor/", "/site-packages/")):
                continue  # someone else's code, carried along
            if any(name == r.rstrip("/") or name.startswith(r.rstrip("/") + "/") for r in roots):
                continue
            top = name.split("/", 1)[0] + "/"
            dirs[top] = dirs.get(top, 0) + 1
        if dirs:
            listed = ", ".join(f"{d} ({n})" for d, n in sorted(dirs.items(), key=lambda kv: -kv[1])[:5])
            self.warn("SCOPE", f"source outside the gate's roots: {listed} — a change there reads as "
                      "no behavior change; add it to [gate] behavior_paths (fde-sync)")
        elif explicit:
            self.add("SCOPE", True, "all source sits under the gate's roots")

    # -- a demand review is one round (fde-review, 2026-10-01) -------------
    def gate_review_rounds(self, explicit: bool = False) -> None:
        from fde_lib import plan_demand_rows, plan_header
        live = set()
        for cid, cdir in cycle_dirs(self.project).items():
            plan = cdir / "plan.md"
            if plan.is_file():
                text = plan.read_text(encoding="utf-8", errors="ignore")
                if plan_header(text, "state").lower().startswith("running"):
                    live |= set(plan_demand_rows(text))
        extra = []
        for did in sorted(live):
            f = self.project / "reviews" / did / "findings.toml"
            if not f.is_file():
                continue
            n = max([int(m) for m in re.findall(r'^\s*id\s*=\s*"R(\d+)-',
                                                 f.read_text(encoding="utf-8", errors="ignore"),
                                                 re.M)] or [1])
            if n > 1:
                extra.append(f"{did} ({n} rounds)")
        if extra:
            self.warn("REVIEW-ROUNDS", "a demand review is one round; its blocker's "
                      f"regression test is the re-check (fde-review): {', '.join(extra[:5])}")
        elif explicit:
            self.add("REVIEW-ROUNDS", True, "every running demand was reviewed in one round")

    def report(self, fmt: str) -> int:
        failed = [r for r in self.results if not r[1]]
        if fmt == "json":
            print(json.dumps(
                {"passed": not failed,
                 "gates": [dict({"id": g, "passed": p, "detail": m},
                                **({"warning": True} if i in self.warned else {}))
                           for i, (g, p, m) in enumerate(self.results)]},
                indent=2, ensure_ascii=False))
        else:
            print()
            for i, (gid, passed, msg) in enumerate(self.results):
                mark = ("\033[33m⚠\033[0m" if i in self.warned else
                        "\033[32m✓\033[0m" if passed else "\033[31m✗\033[0m")
                print(f" {mark} {gid:8} {msg}")
            print()
            if failed:
                print(f"\033[31m{len(failed)} gate(s) failed.\033[0m "
                      f"Invariants have no bypass key — the scope shrinks, the standard does not.")
            else:
                print("\033[32mall gates passed.\033[0m")
        return 1 if failed else 0


# ---------------------------------------------------------------------------
# run record — a result is a fact about a tree, recorded once and read back
# ---------------------------------------------------------------------------
# `--all` writes its outcome to .fde/runs/<tree>.json, where <tree> is
# `git write-tree` of the index (HEAD's tree when the index is clean);
# `--record-suite` adds the unit suite's exit code to the same record, and
# `--status` reads it. Reviewers and promotion read the record instead of
# rerunning the suite at the same tree. Recording is a side channel: it
# runs after the verdict and a failure to record never changes it.
RUNS_DIR = Path(".fde") / "runs"


# The record's key is the CODE in the index, not the whole tree: a board
# line, a review or a promotion changes no test result, and on one client
# two commits in three touched only those — each one sent a full suite
# (npm ci, builds, a database, ~4,800 tests) to run again before a deploy.
RECORD_SKIP = ("reviews/", "cycles/", "promotions/", "backlog.md", "specs/", "discovery/")


def current_tree(project: Path) -> str | None:
    """The key of the index's code: its entries minus the process files,
    hashed. Same code, same key, whatever the board says."""
    import hashlib
    try:
        out = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=project,
                             capture_output=True, check=False)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    kept = [e for e in out.stdout.split(b"\0") if e and not
            e.split(b"\t", 1)[-1].decode("utf-8", "replace").startswith(RECORD_SKIP)]
    return hashlib.sha1(b"\n".join(kept)).hexdigest()


def dirty_paths(project: Path, roots: tuple) -> list[str] | None:
    """Untracked or unstaged paths under `roots`: what the gate read from
    the working tree but the record's key (the index tree) does not hold.
    None when git cannot say."""
    try:
        out = subprocess.run(["git", "status", "--porcelain", "-z",
                              "--untracked-files=all"], cwd=project,
                             capture_output=True, text=True, check=False)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    found, entries = [], out.stdout.split("\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        x, y, path = e[0], e[1], e[3:]
        if x in "RC":
            i += 1  # the rename's source path follows
        if (x == "?" or y != " ") and path_matches(path, roots):
            found.append(path)
    return sorted(found)


def _worktree_matches_index(project: Path) -> bool | None:
    try:
        out = subprocess.run(["git", "diff", "--quiet"], cwd=project,
                             capture_output=True, check=False)
    except OSError:
        return None
    return {0: True, 1: False}.get(out.returncode)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_run(project: Path, tree: str) -> dict | None:
    path = project / RUNS_DIR / f"{tree}.json"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) and rec.get("tree") == tree else None


def _worktrees(project: Path) -> list[Path]:
    try:
        out = subprocess.run(["git", "worktree", "list", "--porcelain"],
                             cwd=project, capture_output=True, text=True,
                             check=False)
    except OSError:
        return []
    return [Path(l[len("worktree "):]) for l in out.stdout.splitlines()
            if l.startswith("worktree ")]


def find_run(project: Path, tree: str) -> dict | None:
    """This checkout's record first, then any other worktree's: a record is
    keyed by the tree's content hash, so a builder's run in its worktree is
    the same fact for a reviewer in another one."""
    rec = read_run(project, tree)
    if rec is not None:
        return rec
    here = project.resolve()
    for wt in _worktrees(project):
        if wt.resolve() != here:
            rec = read_run(wt, tree)
            if rec is not None:
                return {**rec, "found_in": str(wt)}
    return None


# The instructions the run was made under. The tree hash already covers
# instructions committed to the project; a plugin install loads skills from
# outside it (CLAUDE_PLUGIN_ROOT), so the record also carries the kernel
# version and one hash over every instruction file actually in reach.
INSTRUCTION_PATHS = ("AGENTS.md", "CLAUDE.md", ".claude/skills", ".claude/agents",
                     ".fde/spec")
PLUGIN_PATHS = ("skills", "agents", "spec")


def _instruction_files(base: Path, rels) -> list[Path]:
    files = []
    for rel in rels:
        p = base / rel
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += sorted(f for f in p.rglob("*")
                            if f.is_file() and "__pycache__" not in f.parts)
    return files


def instructions_fingerprint(project: Path) -> dict:
    """{kernel_version, sha256, files, plugin_root}: sha256 over the path
    and bytes of each instruction file, project first, then the plugin's."""
    import hashlib
    import os
    h, n = hashlib.sha256(), 0
    sources = [(project, INSTRUCTION_PATHS)]
    plugin = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin and Path(plugin).is_dir():
        sources.append((Path(plugin), PLUGIN_PATHS))
    for base, rels in sources:
        for f in _instruction_files(base, rels):
            try:
                data = f.read_bytes()
            except OSError:
                continue
            h.update(str(f.relative_to(base)).encode() + b"\0" + data + b"\0")
            n += 1
    version = None
    try:
        meta = tomllib.loads((project / ".fde" / "spec" / "invariants.toml")
                             .read_text(encoding="utf-8")).get("meta", {})
        version = meta.get("kernel_version")
    except (OSError, ValueError):
        pass
    return {"kernel_version": version, "sha256": h.hexdigest(), "files": n,
            "plugin_root": plugin if plugin and Path(plugin).is_dir() else None}


def record_run(project: Path, tree: str, **parts) -> Path:
    """Write `parts` (gate=…, suite=…, dirty=…) as the tree's record. One
    record is one run: an earlier run's blocks are dropped, never merged,
    so a suite line can never sit beside another run's gate line (review
    F3, DIRECT-2026-09-29-B)."""
    runs = project / RUNS_DIR
    runs.mkdir(parents=True, exist_ok=True)
    rec = {"tree": tree, **parts}
    rec["worktree_matches_index"] = _worktree_matches_index(project)
    rec["instructions"] = instructions_fingerprint(project)
    path = runs / f"{tree}.json"
    tmp = runs / f".{tree}.json.tmp"
    tmp.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def run_suite(project: Path, command: str) -> dict:
    import time
    t0 = time.monotonic()
    try:
        out = subprocess.run(command, shell=True, cwd=project,
                             capture_output=True, text=True, check=False)
        code, text = out.returncode, (out.stdout or "") + (out.stderr or "")
    except OSError as e:
        code, text = 127, str(e)
    # the last lines that say something (a runner's `----` rule says nothing)
    lines = [l.strip() for l in text.splitlines() if re.search(r"\w", l)]
    # and which tests failed, so a red record never needs a rerun to say so
    fails = list(dict.fromkeys(l[:200] for l in lines if re.search(
        r"^(FAILED|FAIL:|ERROR:|ERROR |✗|×)|\bFAILED\b|AssertionError|Traceback", l)))[:15]
    return {"command": command, "exit_code": code, "failures": fails if code else [],
            "summary": " · ".join(lines[-3:]), "recorded_at": _now(),
            "seconds": round(time.monotonic() - t0, 1)}


def print_status(project: Path, fmt: str) -> int:
    tree = current_tree(project)
    rec = find_run(project, tree) if tree else None
    if fmt == "json":
        print(json.dumps({"tree": tree, "record": rec}, indent=2,
                         ensure_ascii=False))
        return 0
    if tree is None:
        print("no record for this tree (git write-tree failed)")
        return 0
    if rec is None:
        print(f"tree {tree}: no record for this tree")
        return 0
    where = f" (recorded in {rec['found_in']})" if rec.get("found_in") else ""
    print(f"tree {tree}{where}")
    gate = rec.get("gate")
    if isinstance(gate, dict):
        failed = [x.get("id") for x in gate.get("gates", []) if not x.get("passed")]
        verdict = "passed" if gate.get("passed") else f"failed ({', '.join(map(str, failed))})"
        print(f"  gate: {verdict} · {len(gate.get('gates', []))} results · "
              f"{gate.get('recorded_at')} · {gate.get('command')}")
    else:
        print("  gate: not recorded")
    suite = rec.get("suite")
    # a suite block counts only beside the gate block of its own run
    if (isinstance(suite, dict) and isinstance(gate, dict)
            and suite.get("run_id") and suite.get("run_id") == gate.get("run_id")):
        took = f" · {suite['seconds']}s" if suite.get("seconds") is not None else ""
        print(f"  suite: exit {suite.get('exit_code')}{took} · {suite.get('summary')} · "
              f"{suite.get('recorded_at')} · {suite.get('command')}")
        for line in suite.get("failures") or []:
            print(f"    ✗ {line}")
    else:
        print("  suite: not recorded (verify.py --all --record-suite)")
    ins = rec.get("instructions")
    if isinstance(ins, dict):
        now = instructions_fingerprint(project)
        same = "same as now" if now["sha256"] == ins.get("sha256") else \
            "CHANGED since this run — judge it under the instructions it ran with"
        print(f"  instructions: kernel {ins.get('kernel_version')} · "
              f"{ins.get('files')} files · {str(ins.get('sha256'))[:12]} · {same}")
    else:
        print("  instructions: not recorded (an older record)")
    if rec.get("dirty") is not False:
        paths = rec.get("dirty_paths") or []
        what = (", ".join(paths[:5]) + (" …" if len(paths) > 5 else "")
                if paths else "dirty state unknown")
        print(f"  dirty tree — rerun before relying on it ({what})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="pre-commit mode")
    ap.add_argument("--all", action="store_true", help="CI mode: everything")
    ap.add_argument("--gate", default=None, help="a single specific gate")
    ap.add_argument("--since", default=None,
                    help="CI: diff this rev..HEAD for I1 (push base / PR base)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--status", action="store_true",
                    help="print the recorded run for the current tree")
    ap.add_argument("--record-suite", nargs="?", const="", default=None,
                    metavar="CMD",
                    help="with --all: also run the unit suite once (CMD, else "
                         "[stack].test_command) and record its exit code")
    args = ap.parse_args()

    if args.status:
        return print_status(project_root(), args.format)
    if args.record_suite is not None and (not args.all or args.gate or args.staged):
        print("\033[31m✗\033[0m --record-suite runs with --all only "
              "(no --gate, no --staged)", file=sys.stderr)
        return 2

    if args.gate is not None and args.gate not in KNOWN_GATES:
        print(f"\033[31m✗\033[0m unknown gate '{args.gate}'. "
              f"Valid: {', '.join(KNOWN_GATES)}", file=sys.stderr)
        return 2
    if args.staged and args.gate and args.gate not in ("config", "eval", "eval-coverage",
                                                       "untracked", "backlog-length"):
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
    only = GATE_ALIASES.get(args.gate, args.gate)

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
    # cheap and only visible before the commit (CI checks out clean), so
    # they run at the commit tier too: a record left out of git, a long
    # new backlog line
    if want("untracked"):
        g.gate_untracked_records(explicit=(only == "untracked"))
    if want("backlog-length"):
        run_gate(g.gate_backlog_length, cfg, args.staged, since=args.since,
                 explicit=(only == "backlog-length"), gid="BL-LEN")
    if args.staged and want("erosion"):
        g.gate_erosion_staged()
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
        if want("backlog"):
            g.gate_backlog(cfg, explicit=(only == "backlog"))
            g.gate_backlog_ids(explicit=(only == "backlog"))
        if want("traceability"):
            g.gate_traceability()
        if want("erosion"):
            g.gate_erosion(explicit=(only == "erosion"))
        if want("process-dup"):
            g.gate_process_duplication(explicit=(only == "process-dup"))
        if want("doc-refs"):
            g.gate_doc_refs(explicit=(only == "doc-refs"))
        if want("docs"):
            g.gate_docs_line(explicit=(only == "docs"))
        if want("cycles"):
            g.gate_cycles(explicit=(only == "cycles"))
        if want("map"):
            g.gate_map(explicit=(only == "map"))
        if want("deploy-allow"):
            g.gate_deploy_allow(explicit=(only == "deploy-allow"))
        if want("migration"):
            g.gate_migration(explicit=(only == "migration"))
        if want("promotion"):
            g.gate_promotion_decision(explicit=(only == "promotion"))
        if want("backlog-cycle"):
            g.gate_backlog_per_cycle(explicit=(only == "backlog-cycle"))
        if want("suite"):
            g.gate_suite_record(explicit=(only == "suite"))
        if want("scope"):
            g.cfg_raw = cfg.raw
            g.gate_scope(explicit=(only == "scope"))
        if want("review-rounds"):
            g.gate_review_rounds(explicit=(only == "review-rounds"))
        if want("divergence"):
            g.gate_divergence()
        if want("survey"):
            g.gate_survey(explicit=(only == "survey"))
        if want("walkthrough"):
            g.gate_walkthrough(explicit=(only == "walkthrough"))
        if want("rule-lane"):
            run_gate(g.gate_rule_lane, since=args.since,
                     explicit=(only == "rule-lane"), gid="RULE-LANE")

    if not g.results:
        print("\033[31m✗\033[0m no gate ran — check the flags", file=sys.stderr)
        return 2
    code = g.report(args.format)
    if args.all and only is None and not args.staged:
        _record(project, cfg, args, code, g)
    return code


def _record(project: Path, cfg: Config, args, code: int, g: Gate) -> None:
    """After the verdict, never before: nothing here can change `code`."""
    try:
        tree = current_tree(project)
        if tree is None:
            raise RuntimeError("git write-tree failed")
        import uuid
        run_id = uuid.uuid4().hex
        behavior_paths, eval_paths = gate_paths(cfg.raw)
        dirty = dirty_paths(project, tuple(behavior_paths) + tuple(eval_paths))
        parts = {"gate": {
            "run_id": run_id,
            "passed": code == 0,
            "gates": [{"id": i, "passed": p, "detail": m} for i, p, m in g.results],
            "recorded_at": _now(),
            "command": " ".join(["python3", "bin/fde/verify.py", *sys.argv[1:]]),
        }}
        if args.record_suite is not None:
            cmd = args.record_suite or str(
                cfg.raw.get("stack", {}).get("test_command") or "")
            if not cmd:
                raise RuntimeError("no suite command: pass one or set "
                                   "[stack].test_command")
            parts["suite"] = {"run_id": run_id, **run_suite(project, cmd)}
        # the key is the index tree; the gate read the working tree — an
        # untracked or unstaged path under the gate's roots is a difference
        parts["dirty"] = dirty is None or bool(dirty)
        parts["dirty_paths"] = dirty or []
        record_run(project, tree, **parts)
        suite = parts.get("suite")
        tail = f"; suite exit {suite['exit_code']}" if suite else ""
        print(f"recorded for tree {tree[:12]}{tail}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — a record never breaks the gate
        print(f"\033[33m!\033[0m run not recorded: {e}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
