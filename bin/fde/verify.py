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
               "erosion", "divergence", "survey")

# vendor trees never count as an observability signal (I5) — a match inside
# node_modules or a virtualenv is someone else's instrumentation
VENDOR_PATHS = ("node_modules/", ".venv/", "venv/", "vendor/", "dist/", "build/", "__pycache__/")


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
    def _git(self, *args: str) -> list[str]:
        try:
            out = subprocess.run(
                ["git", *args], cwd=self.project, capture_output=True, text=True, check=False
            )
            return [l for l in out.stdout.splitlines() if l.strip()]
        except FileNotFoundError:
            return []

    def _rev_ok(self, rev: str) -> bool:
        try:
            r = subprocess.run(["git", "rev-parse", "--verify", "--quiet",
                                f"{rev}^{{commit}}"],
                               cwd=self.project, capture_output=True, text=True)
            return r.returncode == 0
        except FileNotFoundError:
            return False

    def changed(self, staged: bool, since: str | None = None) -> list[str]:
        if staged:
            return self._git("diff", "--cached", "--name-only")
        # CI: diff the pushed/PR range when given; else the last commit;
        # else (first commit, shallow clone) everything in HEAD. Never fall
        # back to ls-files — that made I1 vacuously green.
        if since and set(since) != {"0"} and self._rev_ok(since):
            return self._git("diff", "--name-only", f"{since}..HEAD")
        if self._rev_ok("HEAD~1"):
            return self._git("diff", "--name-only", "HEAD~1..HEAD")
        return self._git("diff", "--name-only", EMPTY_TREE, "HEAD")

    # -- I1: eval precedes merge ------------------------------------------
    def gate_eval_coverage(self, staged: bool, since: str | None = None) -> None:
        files = self.changed(staged, since)
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
        # reviewer who fixes erases the record of the finding
        dirty = []
        for c in self._git("log", "-20", "--format=%H"):
            files = self._git("diff-tree", "--root", "--no-commit-id",
                              "--name-only", "-r", c)
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
        # ignored, and never inside a vendor tree
        files = self._git("ls-files", "-co", "--exclude-standard")
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
        g.gate_eval_coverage(staged=args.staged, since=args.since)
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

    if not g.results:
        print("\033[31m✗\033[0m no gate ran — check the flags", file=sys.stderr)
        return 2
    return g.report(args.format)


if __name__ == "__main__":
    raise SystemExit(main())
