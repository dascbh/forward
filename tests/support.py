"""Shared fixture: builds a minimal installed project in a temp dir."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASE_CONFIG = """\
[project]
name = "fixture"
kernel_version = "test"

[triage]
data_class = "{data_class}"
reversibility = "reversible"

[stack]
test_command = "true"
eval_command = "true"

[gate]
behavior_paths = {behavior}
eval_paths = {evals}

[weights]
functional_correctness = 26
security_privacy = {security}
reliability_resilience = 12
observability = 12
maintainability = 12
performance_scale = 9
usability_accessibility = 8
operational_cost = {cost}

[derived.depths]
qa_test_strategy = 1

[depths]
"""


def make_project(dir, data_class="internal", behavior='["src/"]',
                 evals='["evals/", "tests/"]', security=14, cost=7,
                 scrum=False) -> Path:
    p = Path(dir)
    body = BASE_CONFIG.format(
        data_class=data_class, behavior=behavior, evals=evals,
        security=security, cost=cost)
    if scrum:
        body += "\n[scrum]\nenabled = true\n"
    (p / "fde.config.toml").write_text(body, encoding="utf-8")
    dest = p / "bin" / "fde"
    dest.mkdir(parents=True, exist_ok=True)
    for f in ("fde_lib.py", "verify.py", "guard.py"):
        shutil.copy(ROOT / "runtime" / f, dest / f)
    ks = p / ".fde" / "spec" / "dimensions"
    ks.mkdir(parents=True, exist_ok=True)
    for rel in ("invariants.toml", "roles.toml"):
        shutil.copy(ROOT / "spec" / rel, ks.parent / rel)
    for rel in ("quality-attributes.toml", "technical-domains.toml"):
        shutil.copy(ROOT / "spec" / "dimensions" / rel, ks / rel)
    run_git(p, "init", "-q")
    run_git(p, "config", "user.email", "fixture@test")
    run_git(p, "config", "user.name", "fixture")
    return p


def run_git(project, *args):
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def git_out(project, *args) -> str:
    r = subprocess.run(["git", *args], cwd=project, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def commit_all(project, msg) -> str:
    run_git(project, "add", "-A")
    run_git(project, "commit", "-q", "-m", msg)
    return git_out(project, "rev-parse", "HEAD")


def verify(project, *args):
    return subprocess.run(["python3", "bin/fde/verify.py", *args],
                          cwd=project, capture_output=True, text=True)


def guard(project, payload: dict):
    return subprocess.run(
        ["python3", str(Path(project) / "bin" / "fde" / "guard.py")],
        cwd=project, input=json.dumps(payload), capture_output=True, text=True)
