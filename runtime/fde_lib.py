"""
fde_lib — the framework's deterministic core.

Zero external dependencies (stdlib only). Reason: this runs in the client's
repository, in the client's CI, possibly with no permission to install
anything, and it must keep running after the FDE leaves (I6).

Format: TOML. `tomllib` is stdlib since Python 3.11.
"""

from __future__ import annotations

import os
import re
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
                f"{CONFIG_NAME} not found in {project}. Install the kernel: run the fde-init skill first."
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
# the backlog-goal switch: [backlog], and [scrum], its name before kernel
# 0.22 (FWD-039), still read so an old client's config keeps its meaning
BACKLOG_SWITCH_KEYS = ("backlog", "scrum")


def backlog_switch(raw: dict) -> tuple[str, object]:
    """The switch's section name and value: [backlog] wins, else [scrum].
    The value may be a non-table; validate() names that, callers use
    backlog_enabled()."""
    for name in BACKLOG_SWITCH_KEYS:
        if name in raw:
            return name, raw[name]
    return "backlog", {}


def backlog_enabled(raw: dict) -> bool:
    """On only for a table whose enabled is the boolean true."""
    _, table = backlog_switch(raw)
    return isinstance(table, dict) and table.get("enabled") is True


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

    # 6. the backlog switch: [backlog] (or its old name [scrum]) is a table
    #    whose enabled is a real boolean or absent — a string "false"
    #    reading as on would fire the goal check against the operator's
    #    intent, and a non-table must be a named violation, never a crash
    for name in BACKLOG_SWITCH_KEYS:
        if name not in cfg.raw:
            continue
        table = cfg.raw[name]
        if not isinstance(table, dict):
            v.append(
                Violation(
                    "BACKLOG-TABLE",
                    f"[{name}] must be a table (a [{name}] section with "
                    f"enabled = true/false), got {type(table).__name__}.",
                )
            )
        elif "enabled" in table and not isinstance(table["enabled"], bool):
            v.append(
                Violation(
                    "BACKLOG-ENABLED",
                    f"[{name}] enabled must be a TOML boolean (true/false), got "
                    f"{type(table['enabled']).__name__}.",
                )
            )
    if all(name in cfg.raw for name in BACKLOG_SWITCH_KEYS):
        v.append(
            Violation(
                "BACKLOG-ALIAS",
                "declare [backlog] only: [scrum] is its old name, and with "
                "both present [backlog] wins.",
            )
        )

    # 6b. [erosion] budget values are numbers — a typo'd threshold must
    #     not silently disable the gate it was meant to arm. The one
    #     non-numeric key is generated_paths: the paths the project
    #     declares as generated copies, excluded from churn.
    erosion = cfg.raw.get("erosion", {}) or {}
    for key, val in erosion.items():
        if key == "generated_paths":
            if not isinstance(val, list) or not all(
                isinstance(x, str) and x.strip() for x in val
            ):
                v.append(
                    Violation(
                        "EROSION-BUDGET",
                        "[erosion] generated_paths must be a list of "
                        "non-empty path strings.",
                    )
                )
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            v.append(
                Violation(
                    "EROSION-BUDGET",
                    f"[erosion] {key} must be a number, got "
                    f"{type(val).__name__}.",
                )
            )
        elif key == "max_structural_erosion" and not 0 <= val <= 1:
            v.append(
                Violation(
                    "EROSION-BUDGET",
                    f"[erosion] max_structural_erosion is a share of "
                    f"complexity mass, from 0 to 1; got {val}.",
                )
            )

    # 7. [gate] retargets I1 to the repo's real layout; it cannot empty it
    gate = cfg.raw.get("gate", {}) or {}
    for key in ("behavior_paths", "eval_paths"):
        # a bare string is not a list: tuple("src/") is four one-letter
        # "roots" that match nothing, and I1 goes quiet (B-16)
        if key in gate and gate[key] and not (
                isinstance(gate[key], list)
                and all(isinstance(x, str) and x.strip() for x in gate[key])):
            v.append(
                Violation(
                    "GATE-TYPE",
                    f"[gate] {key} must be a list of path strings "
                    f"(e.g. [\"src/\"]), got {gate[key]!r}.",
                )
            )
        if key in gate and not gate[key]:
            v.append(
                Violation(
                    "GATE-EMPTY",
                    f"[gate] {key} is empty. The gate can be retargeted to the repo's "
                    f"real roots, never emptied — an empty list would turn I1 off, and "
                    f"invariants have no key.",
                )
            )

    v += process_violations(cfg.raw)
    return v


# -- process knobs: numbers the skills cite, tuned per project -----------------
# The ceilings and budgets the skills state are defaults, not prose to edit:
# a project tunes them in [lanes] and [review] of fde.config.toml. A key the
# kernel does not declare, or a value outside its range, is a violation — a
# misspelled key must never silently fall back to the default.

PROCESS_DEFAULTS = {
    "lanes": {
        "demand_max_loc": 300,   # a demand is split at planning to fit this
        "direct_max_loc": 300,   # the direct lane's ceiling (fde-triage)
    },
    "review": {
        "cycle_rounds_small": 1,  # cycle review rounds at XS/S
        "cycle_rounds_large": 2,  # cycle review rounds at M/L (full + delta)
        "max_findings": 5,        # [[finding]] entries per round
    },
}
PROCESS_RANGES = {
    "demand_max_loc": (50, 2000), "direct_max_loc": (10, 2000),
    "cycle_rounds_small": (1, 3), "cycle_rounds_large": (1, 3),
    "max_findings": (1, 20),
}


def process_settings(raw: dict) -> dict[str, dict]:
    """[lanes] and [review] with the kernel defaults filled in. Values are
    taken as written; validate() reports the ones it cannot accept."""
    out = {}
    for table, defaults in PROCESS_DEFAULTS.items():
        given = raw.get(table)
        given = given if isinstance(given, dict) else {}
        out[table] = {k: given.get(k, d) for k, d in defaults.items()}
    # an unset direct lane follows a lowered demand ceiling, never above it
    lanes = out["lanes"]
    given = raw.get("lanes") if isinstance(raw.get("lanes"), dict) else {}
    if "direct_max_loc" not in given and _is_int(lanes["demand_max_loc"]):
        lanes["direct_max_loc"] = min(lanes["direct_max_loc"], lanes["demand_max_loc"])
    return out


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def process_violations(raw: dict) -> list[Violation]:
    v: list[Violation] = []
    for table, defaults in PROCESS_DEFAULTS.items():
        if table not in raw:
            continue
        given = raw[table]
        if not isinstance(given, dict):
            v.append(Violation("CFG-PROCESS", f"[{table}] must be a table, got {given!r}."))
            continue
        for key, val in given.items():
            if key not in defaults:
                v.append(Violation(
                    "CFG-PROCESS",
                    f"[{table}] {key} is not a known key (known: "
                    f"{', '.join(sorted(defaults))}). A misspelled key would "
                    f"silently keep the default."))
                continue
            lo, hi = PROCESS_RANGES[key]
            if not _is_int(val) or not lo <= val <= hi:
                v.append(Violation(
                    "CFG-PROCESS", f"[{table}] {key} = {val!r}: an integer from {lo} to {hi}."))
    s = process_settings(raw)
    lanes, review = s["lanes"], s["review"]
    if all(_is_int(x) for x in lanes.values()) and lanes["direct_max_loc"] > lanes["demand_max_loc"]:
        v.append(Violation(
            "CFG-PROCESS",
            f"[lanes] direct_max_loc ({lanes['direct_max_loc']}) exceeds demand_max_loc "
            f"({lanes['demand_max_loc']}): the direct lane is never looser than a demand."))
    if (all(_is_int(x) for x in review.values())
            and review["cycle_rounds_large"] < review["cycle_rounds_small"]):
        v.append(Violation(
            "CFG-PROCESS",
            "[review] cycle_rounds_large is below cycle_rounds_small: a larger cycle never "
            "gets fewer review rounds."))
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
    """Weight orders the attack; it sets neither the number of review
    rounds (the triage size does) nor what blocks (severity inside the
    spec's declared threat model does) — ADR-0018."""
    plan = []
    for a in spec.quality["attribute"]:
        w = int(cfg.weights.get(a["id"], a.get("floor", 3)))
        plan.append(
            {
                "attribute": a["id"],
                "label": a["label"],
                "weight": w,
                "probes": a.get("adversarial_probes", []),
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


# ---------------------------------------------------------------------------
# cycle layout (ADR-0019 rules 10 and 14) — read by verify.py and graph.py
# ---------------------------------------------------------------------------
# A cycle is cycles/C-<n>/ with plan.md (dated criteria + ## Demands table)
# and, once decided, promotion.md. A demand is specs/<id>/ whose spec.md
# says `cycle: C-<n>` in its header. The old per-demand layout
# (specs/<id>/acceptance.md, promotions/<id>/decision.md) stays readable:
# repositories that used it must stay green (C-5 FM1).
# A demand id is <PREFIX>-<n>, with a prefix the project picks (FWD, DEM,
# ACME…): whatever the plan's ## Demands first cell and the spec
# directory declare. The kernel's own id families are never demands.
_ID = r"[A-Za-z][A-Za-z0-9]*-\d+(?![A-Za-z0-9])"
RESERVED_PREFIXES = frozenset({"C", "B", "S", "ADR"})
DEMAND_RE = re.compile(r"(?<![\w-])(" + _ID + ")")
CANON_RE = re.compile(r"^(" + _ID + ")")
# retired sprints (ADR-0019 rule 13) are read as history, in the grammar
# they were written in
LEGACY_DEMAND_RE = re.compile(r"\b((?:FWD|DEM)-\d+)")
CYCLE_ID_RE = re.compile(r"C-\d+")
_CYCLE_LINE_RE = re.compile(r"^cycle\s*:\s*(C-\d+)\b", re.IGNORECASE)
_HEADER_LINES = 30


def demand_id(raw: str) -> str | None:
    """The canonical <PREFIX>-<n> a name starts with, upper-cased, or None
    when the name is no demand id."""
    m = CANON_RE.match(raw)
    if not m or m.group(1).split("-")[0].upper() in RESERVED_PREFIXES:
        return None
    return m.group(1).upper()


def canon_demand(raw: str) -> str:
    """Join key: the bare <PREFIX>-<n>, so a slugged directory
    (specs/FWD-001-self-install) and a bare one (reviews/FWD-001) resolve
    to the same demand."""
    return demand_id(raw) or raw


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def header_lines(text: str) -> list[str]:
    """The header region: the first 30 lines, stopping at the first `## `
    section. Prose below the header never counts as a declaration."""
    out = []
    for line in text.splitlines()[:_HEADER_LINES]:
        if line.startswith("## "):
            break
        out.append(line.strip())
    return out


def section(text: str, keyword: str) -> list[str]:
    """Lines under the first `## ` heading whose title contains `keyword`
    (case-insensitive), up to the next `## ` heading."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = keyword.lower() in line.lower()
            continue
        if inside:
            out.append(line)
    return out


def cycle_dirs(project: Path) -> dict[str, Path]:
    """cycles/C-<n>/ directories. The old single-file cycles/C-<n>.md
    carry no criteria and are not cycle directories."""
    d = project / "cycles"
    if not d.is_dir():
        return {}
    return {p.name: p for p in d.iterdir()
            if p.is_dir() and CYCLE_ID_RE.fullmatch(p.name)}


def plan_demands(plan_text: str) -> list[str]:
    """Demand ids of a plan: the FIRST cell of each `## Demands` table
    row. Other cells (depends on, what) name demands without planning
    them."""
    ids: list[str] = []
    for line in section(plan_text, "demands"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        did = demand_id(_plain(cells[0])) if cells else None
        if did and did not in ids:
            ids.append(did)
    return ids


def plan_demand_rows(plan_text: str) -> dict[str, dict[str, str]]:
    """Demand id -> {column title (lower-case): plain cell} for each row
    of a plan's `## Demands` table, keyed by the header row's titles
    (`id | layer | depends on | what | meets | follows`). A row with no
    demand id in its first cell is skipped, as in plan_demands."""
    rows: dict[str, dict[str, str]] = {}
    titles: list[str] | None = None
    for line in section(plan_text, "demands"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [_plain(c) for c in s.strip("|").split("|")]
        if titles is None:
            titles = [c.lower() for c in cells]
            continue
        did = demand_id(cells[0]) if cells else None
        if did and did not in rows:
            rows[did] = dict(zip(titles, cells))
    return rows


def spec_fields(spec_text: str) -> dict[str, str]:
    """The `key: value` pairs of a demand spec's header, split on `·`
    (`cycle: C-14 · layer: front · meets: A1, A3`). Keys lower-case."""
    out: dict[str, str] = {}
    for line in header_lines(spec_text):
        for part in line.split("·"):
            key, sep, value = part.partition(":")
            key = key.strip().lower()
            if sep and re.fullmatch(r"[a-z][a-z_ -]*", key):
                out.setdefault(key, value.strip())
    return out


CRITERION_ID_RE = re.compile(r"(?<![\w-])([A-Z]+\d+)(?![\w-])")


def cycle_end(plan_text: str) -> str | None:
    """How a cycle plan's header ends it: "closed", "abandoned", or None
    while it has not ended (ADR-0019 rule 9, as fde-status reads it). The
    first `closed:`/`abandoned:` line with a value decides; otherwise the
    first word of `state:`."""
    header: dict[str, str] = {}
    for line in header_lines(plan_text):
        m = re.match(r"([A-Za-z_]+)\s*:\s*(.*)$", line)
        if m:
            header.setdefault(m.group(1).lower(), m.group(2).strip())
    for key in ("closed", "abandoned"):
        if header.get(key):
            return key
    words = re.findall(r"[a-z]+", header.get("state", "").lower())
    return words[0] if words and words[0] in ("closed", "abandoned") else None


def _layer_list(cell: str) -> list[str]:
    """A layer cell as a list: `back, front` → ["back", "front"]. Since
    kernel ADR-0022 a demand is one goal and its cell lists every layer
    it touches; a single value still reads as a list of one."""
    return [t for t in re.split(r"[\s,;/+]+", cell.lower()) if t]


def front_demand_criteria(project: Path, spec_dir: Path) -> list[str] | None:
    """The plan criteria a `front` demand of the cycle layout meets, or
    None when the demand is not one: no cycle links it (neither its
    spec's `cycle:` line nor a plan's `## Demands` row), or neither its
    spec header nor its plan row says `front`. The criteria are the union
    of the plan row's `meets` cell and the spec's `meets:` line — either
    link names what the demand must trace (B-27).

    Only a cycle that has not ended is read: a closed or abandoned cycle
    finished under the rules it ran with, as a cycle opened before kernel
    ADR-0019 does; its demands merged while it ran, when this check
    applied."""
    text = read_text(spec_dir / "spec.md")
    did = canon_demand(spec_dir.name)
    fields = spec_fields(text)
    cycles = cycle_dirs(project)
    own = spec_cycle(text)
    layers = set(_layer_list(fields.get("layer", "")))
    meets = fields.get("meets", "")
    linked = False
    for cid, cdir in sorted(cycles.items()):
        plan = read_text(cdir / "plan.md")
        row = plan_demand_rows(plan).get(did)
        if row is None and cid != own:
            continue
        if cycle_end(plan):
            continue
        linked = True
        row = row or {}
        layers.update(_layer_list(row.get("layer", "")))
        meets += f" {row.get('meets', '')}"
    if not linked or "front" not in layers:
        return None
    return sorted(set(CRITERION_ID_RE.findall(meets)))


def _plain(cell: str) -> str:
    """A table cell without its markdown: `[FWD-2](…)` reads FWD-2, and
    bold, italics and backticks are dropped."""
    cell = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    return cell.strip().strip("`*_ ").strip()


def spec_cycle(spec_text: str) -> str | None:
    """The `cycle: C-<n>` header line of a demand spec, if any."""
    for line in header_lines(spec_text):
        m = _CYCLE_LINE_RE.match(line)
        if m:
            return m.group(1).upper()
    return None


_DATE_LINE_RE = re.compile(r"date\s*:\s*(\S+)", re.IGNORECASE)
_CRITERION_RE = re.compile(r"^\s*[-*+]\s+[`*_]*([A-Z]+\d+)\b")
# what templates/cycle/plan.md ships in place of a criterion
_PLACEHOLDERS = ("<name>", "<observable result")


def criteria_section(text: str) -> list[str]:
    """Lines under the first `## Acceptance…` or `## …criteria…` heading,
    up to the next `## ` heading."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            title = line[3:].strip().lower()
            inside = title.startswith("acceptance") or "criteria" in title
            continue
        if inside:
            out.append(line)
    return out


def _iso_date(value: str) -> bool:
    import datetime
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def plan_problem(plan: Path) -> str | None:
    """Why a cycle plan does not carry dated criteria, or None when it
    does: the file exists, its header has `date:` with a real ISO date
    (YYYY-MM-DD), and its `## Acceptance [criteria]` section has at least
    one criterion with an id (`- **A1 — …**`) that is not the template's
    placeholder. Whether the date precedes the first demand commit is not
    checked (a declared limit, fde-verify)."""
    if not plan.is_file():
        return "no plan.md"
    text = read_text(plan)
    dates = [m.group(1) for line in header_lines(text)
             for m in [_DATE_LINE_RE.match(line)] if m]
    if not dates:
        return "plan.md has no 'date:' header line"
    if not any(_iso_date(d) for d in dates):
        return f"plan.md 'date: {dates[0]}' is not a date (YYYY-MM-DD)"
    if not any(_CRITERION_RE.match(line)
               and not any(ph in line for ph in _PLACEHOLDERS)
               for line in criteria_section(text)):
        return ("plan.md has no criterion with an id (`- **A1 — …**`) under "
                "'## Acceptance criteria' — the template's placeholder does "
                "not count")
    return None


def demand_cycles(project: Path) -> dict[str, set[str]]:
    """Canonical demand id -> the cycles it belongs to, from both links:
    a plan's ## Demands table and the spec's `cycle:` line."""
    links: dict[str, set[str]] = {}
    for cid, cdir in cycle_dirs(project).items():
        for did in plan_demands(read_text(cdir / "plan.md")):
            links.setdefault(did, set()).add(cid)
    specs = project / "specs"
    if specs.is_dir():
        for sdir in specs.iterdir():
            if sdir.is_dir():
                cid = spec_cycle(read_text(sdir / "spec.md"))
                if cid:
                    links.setdefault(canon_demand(sdir.name), set()).add(cid)
    return links


def promoted_demands(project: Path) -> dict[str, str]:
    """Canonical demand id -> where its promotion is recorded. Per demand
    (old layout: promotions/<id>/decision.md) or per cycle
    (cycles/C-<n>/promotion.md, covering each of the cycle's demands that
    was specified — a planned demand never specified was never built)."""
    out: dict[str, str] = {}
    proms = project / "promotions"
    if proms.is_dir():
        for dec in sorted(proms.rglob("decision.md")):
            out.setdefault(canon_demand(dec.parent.name),
                           str(dec.relative_to(project)))
    specs = project / "specs"
    specified = {canon_demand(p.name) for p in specs.iterdir() if p.is_dir()} \
        if specs.is_dir() else set()
    cycles = cycle_dirs(project)
    for did, cids in demand_cycles(project).items():
        for cid in sorted(cids):
            if cid in cycles and (cycles[cid] / "promotion.md").is_file() \
                    and did in specified:
                out.setdefault(did, f"cycles/{cid}/promotion.md")
    return out


def reviewed_demands(project: Path) -> set[str]:
    """Canonical ids of demands with a recorded review."""
    reviews = project / "reviews"
    return {canon_demand(p.name) for p in reviews.iterdir()
            if p.is_dir() and (p / "findings.toml").exists()} \
        if reviews.is_dir() else set()


# -- backlog ids across parallel work -----------------------------------------
# One definition of "an id is taken", shared by status.py (next free id) and
# verify.py (duplicate check). A worktree's backlog.md and cycles/ are read
# from disk, uncommitted lines included, because a parallel demand's line is
# not on main yet when the next id is chosen.

B_ID = re.compile(r"(?<![\w-])B-(\d+)(?!\d)")
ID_REFS = ("main", "origin/main")


def _git(root: Path, *args: str) -> str | None:
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                           text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _backlog_texts(tree: Path) -> list[str]:
    files = [tree / "backlog.md"]
    cycles = tree / "cycles"
    if cycles.is_dir():
        files += sorted(cycles.glob("*.md")) + sorted(cycles.glob("*/*.md"))
    return [read_text(f) for f in files if f.is_file()]


def used_backlog_ids(root: Path) -> dict[str, list[str]]:
    """Every `B-<n>` taken, mapped to where it was seen: `tree` (this
    checkout), `worktree:<path>` (every other worktree of the repository)
    and `ref:<name>` (backlog.md on main and origin/main). Without git, only
    `tree` is read."""
    seen: dict[str, set[str]] = {}

    def add(texts, where):
        for t in texts:
            for n in B_ID.findall(t):
                seen.setdefault(f"B-{int(n)}", set()).add(where)

    root = Path(root).resolve()
    add(_backlog_texts(root), "tree")
    listing = _git(root, "worktree", "list", "--porcelain") or ""
    for line in listing.splitlines():
        if line.startswith("worktree "):
            wt = Path(line[len("worktree "):]).resolve()
            if wt != root and wt.is_dir():
                add(_backlog_texts(wt), f"worktree:{wt}")
    for ref in ID_REFS:
        text = _git(root, "show", f"{ref}:backlog.md")
        if text is not None:
            add([text], f"ref:{ref}")
    return {k: sorted(v) for k, v in
            sorted(seen.items(), key=lambda kv: int(kv[0][2:]))}


def next_backlog_id(root: Path) -> str:
    """One more than the highest id taken anywhere `used_backlog_ids` reads."""
    used = used_backlog_ids(root)
    return f"B-{max((int(k[2:]) for k in used), default=0) + 1}"


# -- erosion ratchet: a project with no budget gets today's values -------------
# Install and sync measure a project that declares no [erosion] budget and
# write one from the measurement, so decay is gated from the day it is seen
# instead of never (SlopCodeBench gap: the gate stayed off in every client).
# Each ceiling is the measured value rounded UP to the next step: the gate
# runs on every commit, and a ceiling at the last decimal would fail on noise.

RATCHET_KEYS = (
    # (budget key, metric key in `erosion.py --format json`, step)
    ("max_duplication_pct", "duplication_pct", 0.5),
    ("max_add_delete_ratio", "add_delete_ratio", 0.5),
    ("max_structural_erosion", "structural_erosion", 0.01),
)


def _ceil_step(value: float, step: float) -> float:
    import math
    n = math.floor(value / step + 1e-9) + 1
    return round(n * step, 4)


def erosion_budget_declared(raw: dict) -> bool:
    """True when [erosion] carries any `max_*` ceiling: that project chose
    its budget and a ratchet never touches it."""
    ero = raw.get("erosion")
    return isinstance(ero, dict) and any(k.startswith("max_") for k in ero)


def erosion_ratchet(metrics: dict, window: int = 50) -> dict:
    """The [erosion] budget written from one measurement: `window` plus one
    ceiling per metric that was measured (a null metric is left out, never
    guessed)."""
    budget: dict = {"window": int(metrics.get("window") or window)}
    for key, metric, step in RATCHET_KEYS:
        value = metrics.get(metric)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            budget[key] = _ceil_step(float(value), step)
    return budget


def erosion_ratchet_toml(metrics: dict) -> str:
    """The same budget as the TOML lines of an `[erosion]` table."""
    lines = ["[erosion]"]
    for k, v in erosion_ratchet(metrics).items():
        lines.append(f"{k} = {v}")
    return "\n".join(lines) + "\n"
