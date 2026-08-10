"""
fde_lib — the framework's deterministic core.

Zero external dependencies (stdlib only). Reason: this runs in the client's
repository, in the client's CI, possibly with no permission to install
anything, and it must keep running after the FDE leaves (I6).

Format: TOML. `tomllib` is stdlib since Python 3.11.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KERNEL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_NAME = "fde.config.toml"
GENERATED_HEADER = "FDE-KERNEL:GENERATED"

# I1 targeting. Defaults fit a single-root layout; monorepos declare their
# real roots in [gate] — retargeting is allowed, emptying is not (validate()).
DEFAULT_BEHAVIOR_PATHS = ("src/", "lib/", "app/", "services/", "prompts/", "agents/")
DEFAULT_EVAL_PATHS = ("evals/", "tests/")


def path_matches(path: str, entries) -> bool:
    """Gate-path semantics: a directory entry (trailing slash optional)
    matches its whole subtree; a file entry matches exactly. 'spec' never
    matches 'specs/x' — the separator is part of the match."""
    for e in entries:
        e = e.rstrip("/")
        if path == e or path.startswith(e + "/"):
            return True
    return False


def gate_paths(raw: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """behavior_paths and eval_paths from [gate], with defaults. An empty
    list falls back to the defaults — silence is not a bypass. Entries are
    kept as declared; match with path_matches (file entries match exactly,
    directory entries match their subtree)."""
    gate = raw.get("gate", {}) or {}
    bp = tuple(gate.get("behavior_paths") or DEFAULT_BEHAVIOR_PATHS)
    ep = tuple(gate.get("eval_paths") or DEFAULT_EVAL_PATHS)
    return bp, ep


# ---------------------------------------------------------------------------
# spec loading
# ---------------------------------------------------------------------------
def load_toml(path: Path) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


@dataclass
class Spec:
    invariants: dict
    quality: dict
    domains: dict
    roles: dict

    @classmethod
    def load(cls, root: Path = KERNEL_ROOT) -> "Spec":
        s = root / "spec"
        return cls(
            invariants=load_toml(s / "invariants.toml"),
            quality=load_toml(s / "dimensions" / "quality-attributes.toml"),
            domains=load_toml(s / "dimensions" / "technical-domains.toml"),
            roles=load_toml(s / "roles.toml"),
        )

    @property
    def floors(self) -> dict:
        return self.invariants["floors"]

    @property
    def budget(self) -> int:
        return self.quality["meta"]["budget"]

    def quality_ids(self) -> list[str]:
        return [a["id"] for a in self.quality["attribute"]]

    def domain_ids(self) -> list[str]:
        return [d["id"] for d in self.domains["domain"]]

    def floor_for_quality(self, qid: str) -> int:
        for a in self.quality["attribute"]:
            if a["id"] == qid:
                return int(a.get("floor", self.floors["default_quality_floor"]))
        return int(self.floors["default_quality_floor"])


# ---------------------------------------------------------------------------
# project config
# ---------------------------------------------------------------------------
@dataclass
class Config:
    path: Path
    raw: dict
    weights: dict = field(default_factory=dict)
    depths: dict = field(default_factory=dict)

    @classmethod
    def load(cls, project: Path) -> "Config":
        p = project / CONFIG_NAME
        if not p.exists():
            raise FileNotFoundError(
                f"{CONFIG_NAME} not found in {project}. Run `fde init` first."
            )
        raw = load_toml(p)
        return cls(
            path=p,
            raw=raw,
            weights=dict(raw.get("weights", {})),
            depths=dict(raw.get("depths", {})),
        )


# ---------------------------------------------------------------------------
# validation: this is where weight stops being able to turn off an invariant
# ---------------------------------------------------------------------------
@dataclass
class Violation:
    code: str
    message: str
    fatal: bool = True


def validate(cfg: Config, spec: Spec) -> list[Violation]:
    v: list[Violation] = []

    # 1. no config key may collide with an invariant
    forbidden = {"invariants", "floors", "kernel", "gates_disabled", "skip"}
    for key in cfg.raw:
        if key in forbidden:
            v.append(
                Violation(
                    "CFG-FORBIDDEN-KEY",
                    f"'{key}' is not configurable. Invariants live in spec/invariants.toml "
                    f"and have no key. To operate without them, fork.",
                )
            )

    # 2. vector A is a CLOSED budget
    known_q = set(spec.quality_ids())
    unknown = set(cfg.weights) - known_q
    if unknown:
        v.append(Violation("VEC-A-UNKNOWN", f"unknown attributes: {sorted(unknown)}"))
    missing = known_q - set(cfg.weights)
    if missing:
        v.append(Violation("VEC-A-MISSING", f"attributes with no allocated weight: {sorted(missing)}"))

    total = sum(int(x) for x in cfg.weights.values())
    if not unknown and not missing and total != spec.budget:
        v.append(
            Violation(
                "VEC-A-BUDGET",
                f"closed budget: weights sum to {total}, required {spec.budget}. "
                f"If everything can be high, nothing was chosen and the vector carries no information.",
            )
        )

    # 3. floor: weight never goes below it. weight zero does not exist.
    for qid, w in cfg.weights.items():
        if qid not in known_q:
            continue
        floor = spec.floor_for_quality(qid)
        if int(w) < floor:
            v.append(
                Violation(
                    "VEC-A-FLOOR",
                    f"'{qid}' = {w} is below the floor {floor}. Weight redistributes emphasis "
                    f"above the floor; it does not reduce rigor below it.",
                )
            )

    # 4. vector B: depth is derived; override is upward only
    derived = cfg.raw.get("derived", {}).get("depths", {})
    for did, d in cfg.depths.items():
        if did not in set(spec.domain_ids()):
            v.append(Violation("VEC-B-UNKNOWN", f"unknown domain: {did}"))
            continue
        floor = int(derived.get(did, 0))
        if int(d) < floor:
            v.append(
                Violation(
                    "VEC-B-DOWNWARD",
                    f"'{did}': override {d} < derived depth {floor}. "
                    f"Override is upward-only — the nature of the system sets the minimum.",
                )
            )

    # 5. hard QA floor (depth 0 contradicts I1)
    qa_floor = int(spec.floors["qa_test_strategy"])
    qa = int(cfg.depths.get("qa_test_strategy", derived.get("qa_test_strategy", qa_floor)))
    if qa < qa_floor:
        v.append(
            Violation(
                "VEC-B-QA-FLOOR",
                f"qa_test_strategy = {qa}; minimum {qa_floor}. Depth 0 would mean "
                f"having no test strategy at all, which contradicts I1.",
            )
        )

    # 6. [scrum].enabled is a real boolean or absent — a string "false"
    #    reading as on would fire cadence gates against the operator's intent
    scrum = cfg.raw.get("scrum", {}) or {}
    if "enabled" in scrum and not isinstance(scrum["enabled"], bool):
        v.append(
            Violation(
                "SCRUM-ENABLED",
                f"[scrum] enabled must be a TOML boolean (true/false), got "
                f"{type(scrum['enabled']).__name__}.",
            )
        )

    # 6b. [erosion] budget values are numbers — a typo'd threshold must
    #     not silently disable the gate it was meant to arm
    erosion = cfg.raw.get("erosion", {}) or {}
    for key, val in erosion.items():
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            v.append(
                Violation(
                    "EROSION-BUDGET",
                    f"[erosion] {key} must be a number, got "
                    f"{type(val).__name__}.",
                )
            )

    # 7. [gate] retargets I1 to the repo's real layout; it cannot empty it
    gate = cfg.raw.get("gate", {}) or {}
    for key in ("behavior_paths", "eval_paths"):
        if key in gate and not gate[key]:
            v.append(
                Violation(
                    "GATE-EMPTY",
                    f"[gate] {key} is empty. The gate can be retargeted to the repo's "
                    f"real roots, never emptied — an empty list would turn I1 off, and "
                    f"invariants have no key.",
                )
            )

    return v


# ---------------------------------------------------------------------------
# floor escalation by triage (security rises with data class, never falls)
# ---------------------------------------------------------------------------
DATA_CLASS_ESCALATION = {
    "public": 0,
    "internal": 2,
    "personal": 12,
    "financial": 16,
    "health": 20,
}


def escalated_security_floor(cfg: Config, spec: Spec) -> int:
    base = spec.floor_for_quality("security_privacy")
    dc = str(cfg.raw.get("triage", {}).get("data_class", "internal")).lower()
    return max(base, DATA_CLASS_ESCALATION.get(dc, base))


# ---------------------------------------------------------------------------
# adversarial attack order — derived from vector A, not chosen
# ---------------------------------------------------------------------------
def probe_plan(cfg: Config, spec: Spec) -> list[dict]:
    plan = []
    for a in spec.quality["attribute"]:
        w = int(cfg.weights.get(a["id"], a.get("floor", 3)))
        plan.append(
            {
                "attribute": a["id"],
                "label": a["label"],
                "weight": w,
                # rounds scale with weight, minimum 1 — no dimension goes unattacked
                "rounds": max(1, round(w / 10)),
                "probes": a.get("adversarial_probes", []),
                "blocking": w >= 15,
            }
        )
    return sorted(plan, key=lambda p: -p["weight"])


# ---------------------------------------------------------------------------
# util
# ---------------------------------------------------------------------------
def fail(msg: str, code: int = 1) -> None:
    print(f"\033[31m✗\033[0m {msg}", file=sys.stderr)
    sys.exit(code)


def ok(msg: str) -> None:
    print(f"\033[32m✓\033[0m {msg}")


def warn(msg: str) -> None:
    print(f"\033[33m!\033[0m {msg}")


def project_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / CONFIG_NAME).exists() or (cand / ".git").is_dir():
            return cand
    return p


def is_ci() -> bool:
    return any(os.environ.get(k) for k in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE"))
