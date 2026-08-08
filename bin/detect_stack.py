#!/usr/bin/env python3
"""
detect_stack — detecta, não pergunta.

Stack se detecta por artefato no repositório: lockfile, manifest, runner de teste,
formatter, CI existente. Perguntar o que dá para inferir é atrito desnecessário e
produz resposta pior que a inferência.

Saída: JSON no stdout. A profundidade do vetor B é DERIVADA daqui — o cliente
pode elevar, nunca reduzir.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fde_lib import project_root  # noqa: E402

# ---------------------------------------------------------------------------
# assinaturas: (arquivo, chave inferida)
# ---------------------------------------------------------------------------
LANG_SIGNS = {
    "package.json": "javascript",
    "tsconfig.json": "typescript",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
    "mix.exs": "elixir",
}

TEST_RUNNERS = {
    "pytest.ini": "pytest",
    "tox.ini": "pytest",
    "jest.config.js": "jest",
    "jest.config.ts": "jest",
    "vitest.config.ts": "vitest",
    "vitest.config.js": "vitest",
    "playwright.config.ts": "playwright",
    "phpunit.xml": "phpunit",
}

FRONTEND_SIGNS = ["next.config.js", "next.config.ts", "vite.config.ts", "vite.config.js",
                  "angular.json", "svelte.config.js", "nuxt.config.ts", "remix.config.js"]

DB_SIGNS = ["alembic.ini", "prisma/schema.prisma", "knexfile.js", "ecto",
            "db/migrate", "migrations", "drizzle.config.ts", "supabase"]

API_SIGNS = ["openapi.yaml", "openapi.json", "swagger.yaml", "schema.graphql",
             "proto", "asyncapi.yaml"]

CI_SIGNS = [".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", ".circleci",
            "azure-pipelines.yml", "buildkite.yml"]

IAC_SIGNS = ["Dockerfile", "docker-compose.yml", "terraform", "main.tf", "k8s",
             "helm", "serverless.yml", "template.yaml", "cdk.json", "Pulumi.yaml"]

AI_SIGNS = ["langchain", "llama_index", "anthropic", "openai", "litellm",
            "crewai", "autogen", "langgraph", "pydantic_ai", "@anthropic-ai/sdk"]

AGENT_TOOLS = {
    "CLAUDE.md": "claude-code",
    ".claude": "claude-code",
    "AGENTS.md": "agents-md-compatible",
    ".cursor": "cursor",
    ".cursorrules": "cursor",
    ".github/copilot-instructions.md": "copilot",
    ".codex": "codex",
    "GEMINI.md": "gemini-cli",
    ".kiro": "kiro",
    ".windsurfrules": "windsurf",
    ".aider.conf.yml": "aider",
}


def _exists_any(root: Path, names: list[str]) -> list[str]:
    found = []
    for n in names:
        if (root / n).exists():
            found.append(n)
    return found


def _grep_manifests(root: Path, needles: list[str]) -> list[str]:
    """Procura assinaturas dentro dos manifests, não na árvore inteira."""
    hits: set[str] = set()
    manifests = ["package.json", "pyproject.toml", "requirements.txt",
                 "go.mod", "Cargo.toml", "composer.json"]
    for m in manifests:
        p = root / m
        if not p.exists():
            continue
        try:
            text = p.read_text(errors="ignore").lower()
        except OSError:
            continue
        for n in needles:
            if n.lower() in text:
                hits.add(n)
    return sorted(hits)


def detect(root: Path) -> dict:
    facts: dict = {"root": str(root)}

    facts["languages"] = sorted({v for k, v in LANG_SIGNS.items() if (root / k).exists()})
    facts["test_runners"] = sorted({v for k, v in TEST_RUNNERS.items() if (root / k).exists()})
    facts["has_frontend"] = bool(_exists_any(root, FRONTEND_SIGNS))
    facts["has_database"] = bool(_exists_any(root, DB_SIGNS))
    facts["exposes_api"] = bool(_exists_any(root, API_SIGNS))
    facts["has_ci"] = bool(_exists_any(root, CI_SIGNS))
    facts["has_iac"] = bool(_exists_any(root, IAC_SIGNS))
    facts["ai_libraries"] = _grep_manifests(root, AI_SIGNS)
    facts["embeds_model"] = bool(facts["ai_libraries"])
    facts["agent_tools"] = sorted({v for k, v in AGENT_TOOLS.items() if (root / k).exists()})

    # o que a detecção NÃO resolve — vira pergunta na entrevista, em bloco único
    facts["unresolved"] = [
        k for k, cond in {
            "data_class": True,          # nunca inferível de arquivo
            "deploy_target": not facts["has_iac"],
            "reversibility": True,
            "has_agent_loop": facts["embeds_model"],
            "user_facing": facts["has_frontend"],
        }.items() if cond
    ]
    return facts


def derive_depths(facts: dict, answers: dict | None = None) -> dict:
    """
    Profundidade DERIVADA (0..3). É o piso do vetor B: override só para cima.
    """
    a = answers or {}
    dc = str(a.get("data_class", "interno")).lower()
    sensitive = dc in {"pessoal", "financeiro", "saude"}
    irreversible = str(a.get("reversibility", "reversivel")).lower() != "reversivel"

    surfaces = sum([facts["has_frontend"], facts["exposes_api"],
                    facts["has_database"], facts["has_iac"]])

    d = {
        "software_architecture": 1 + (1 if surfaces >= 3 else 0) + (1 if irreversible else 0),
        "data_modeling": 2 if facts["has_database"] else 0,
        "api_contract": 2 if facts["exposes_api"] else (1 if facts["has_frontend"] else 0),
        "design_system": 1 if facts["has_frontend"] else 0,
        "usability_research": (1 if a.get("user_facing") else 0) + (1 if facts["has_frontend"] else 0),
        "qa_test_strategy": 1,  # piso duro — I1
        "platform_delivery": 2 if (facts["has_ci"] or facts["has_iac"]) else 1,
        "applied_security": 2 if sensitive else (1 if facts["exposes_api"] else 0),
        "ai_agents": 2 if a.get("has_agent_loop") else (1 if facts["embeds_model"] else 0),
    }

    if facts["has_database"] and sensitive:
        d["data_modeling"] = 3
    if irreversible:
        d["platform_delivery"] = max(d["platform_delivery"], 3)

    return {k: min(3, v) for k, v in d.items()}


def main() -> int:
    root = project_root(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    facts = detect(root)
    out = {"facts": facts, "derived_depths": derive_depths(facts)}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
