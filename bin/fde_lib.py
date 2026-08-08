"""
fde_lib — núcleo determinístico do framework.

Zero dependência externa (stdlib apenas). Motivo: isso roda no repositório do
cliente, no CI do cliente, possivelmente sem permissão de instalar nada, e tem
que continuar rodando depois que o FDE sai (I6).

Formato: TOML. `tomllib` é stdlib desde Python 3.11.
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


# ---------------------------------------------------------------------------
# carga de spec
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
# config do projeto
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
                f"{CONFIG_NAME} não encontrado em {project}. Rode `fde init` primeiro."
            )
        raw = load_toml(p)
        return cls(
            path=p,
            raw=raw,
            weights=dict(raw.get("weights", {})),
            depths=dict(raw.get("depths", {})),
        )


# ---------------------------------------------------------------------------
# validação: é aqui que peso deixa de poder desligar invariante
# ---------------------------------------------------------------------------
@dataclass
class Violation:
    code: str
    message: str
    fatal: bool = True


def validate(cfg: Config, spec: Spec) -> list[Violation]:
    v: list[Violation] = []

    # 1. nenhuma chave de config pode colidir com invariante
    forbidden = {"invariants", "floors", "kernel", "gates_disabled", "skip"}
    for key in cfg.raw:
        if key in forbidden:
            v.append(
                Violation(
                    "CFG-FORBIDDEN-KEY",
                    f"'{key}' não é configurável. Invariantes vivem em spec/invariants.toml "
                    f"e não têm chave. Para operar sem eles, faça fork.",
                )
            )

    # 2. vetor A é orçamento FECHADO
    known_q = set(spec.quality_ids())
    unknown = set(cfg.weights) - known_q
    if unknown:
        v.append(Violation("VEC-A-UNKNOWN", f"atributos desconhecidos: {sorted(unknown)}"))
    missing = known_q - set(cfg.weights)
    if missing:
        v.append(Violation("VEC-A-MISSING", f"atributos sem peso alocado: {sorted(missing)}"))

    total = sum(int(x) for x in cfg.weights.values())
    if not unknown and not missing and total != spec.budget:
        v.append(
            Violation(
                "VEC-A-BUDGET",
                f"orçamento fechado: soma dos pesos = {total}, exigido = {spec.budget}. "
                f"Se tudo pode ser alto, nada foi escolhido e o vetor não informa.",
            )
        )

    # 3. piso: peso nunca desce abaixo. peso zero não existe.
    for qid, w in cfg.weights.items():
        if qid not in known_q:
            continue
        floor = spec.floor_for_quality(qid)
        if int(w) < floor:
            v.append(
                Violation(
                    "VEC-A-FLOOR",
                    f"'{qid}' = {w} está abaixo do piso {floor}. Peso redistribui ênfase "
                    f"acima do piso; não reduz rigor abaixo dele.",
                )
            )

    # 4. vetor B: profundidade é derivada; override só para cima
    derived = cfg.raw.get("derived", {}).get("depths", {})
    for did, d in cfg.depths.items():
        if did not in set(spec.domain_ids()):
            v.append(Violation("VEC-B-UNKNOWN", f"domínio desconhecido: {did}"))
            continue
        floor = int(derived.get(did, 0))
        if int(d) < floor:
            v.append(
                Violation(
                    "VEC-B-DOWNWARD",
                    f"'{did}': override {d} < profundidade derivada {floor}. "
                    f"Override é upward-only — a natureza do sistema define o mínimo.",
                )
            )

    # 5. piso duro de QA (profundidade 0 contradiz I1)
    qa_floor = int(spec.floors["qa_test_strategy"])
    qa = int(cfg.depths.get("qa_test_strategy", derived.get("qa_test_strategy", qa_floor)))
    if qa < qa_floor:
        v.append(
            Violation(
                "VEC-B-QA-FLOOR",
                f"qa_test_strategy = {qa}; mínimo {qa_floor}. Profundidade 0 significaria "
                f"não haver estratégia de teste, o que contradiz I1.",
            )
        )

    return v


# ---------------------------------------------------------------------------
# escalada de piso pela triagem (segurança sobe por classe de dado, nunca desce)
# ---------------------------------------------------------------------------
DATA_CLASS_ESCALATION = {
    "publico": 0,
    "interno": 2,
    "pessoal": 12,
    "financeiro": 16,
    "saude": 20,
}


def escalated_security_floor(cfg: Config, spec: Spec) -> int:
    base = spec.floor_for_quality("security_privacy")
    dc = str(cfg.raw.get("triage", {}).get("data_class", "interno")).lower()
    return max(base, DATA_CLASS_ESCALATION.get(dc, base))


# ---------------------------------------------------------------------------
# ordem de ataque adversarial — derivada do vetor A, não escolhida
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
                # rodadas escalam com peso, mínimo 1 — nenhuma dimensão fica sem ataque
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
