"""
Adapter contract.

The INSTRUCTION layer is agnostic (AGENTS.md + SKILL.md are standards governed
by the Agentic AI Foundation). The ENFORCEMENT layer is not and never will be:
hooks, per-role tool restrictions, and worktree isolation are per-tool
implementation, with unequal capability.

That is why the invariant lives in the REPOSITORY (pre-commit + CI), not in
the tool. The adapter is convenience: it pulls the gate into the agent's loop
and gives faster feedback. If no adapter exists for a tool, the standard still
holds — it just arrives later, at commit instead of at the write.

Three tiers, honestly declared by `fde doctor`:

  loop      — hook + per-role tool restriction. Blocks before the write.
  commit    — no hook, but subagents/worktrees exist. Real roles, gate in git.
  advisory  — instruction file only. Roles are convention, the gate is CI.

Promising parity and delivering theater in three out of five tools is what
burns an open framework. Declaring the tier is honesty that builds trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

TIERS = ("loop", "commit", "advisory")

GEN_MARK = "FDE-KERNEL:GENERATED"


def generated_header(comment: str = "#") -> str:
    lines = [
        f"{GEN_MARK} — do not edit by hand.",
        "Source of truth: fde.config.toml + spec/. Regenerate with `fde sync`.",
        "Manual edits here are overwritten and detected as drift.",
    ]
    if comment == "<!--":
        return "<!--\n" + "\n".join(lines) + "\n-->\n"
    return "".join(f"{comment} {l}\n" for l in lines)


@dataclass
class Capability:
    tool: str
    tier: str
    enforced: list[str] = field(default_factory=list)   # actually blocks
    advisory: list[str] = field(default_factory=list)   # only recommends
    notes: list[str] = field(default_factory=list)


@dataclass
class EmitContext:
    project: Path
    kernel: Path
    config: dict
    spec: object
    facts: dict
    probe_plan: list


class Adapter:
    tool = "abstract"

    def detect(self, project: Path) -> bool:          # is the tool in use here?
        raise NotImplementedError

    def capability(self) -> Capability:
        raise NotImplementedError

    def emit(self, ctx: EmitContext) -> list[Path]:    # files written
        raise NotImplementedError

    # ---- helpers ----
    @staticmethod
    def write(path: Path, content: str, comment: str = "#") -> Path:
        """
        Write with the generated marker.

        YAML frontmatter must be the FIRST thing in the file — a header before
        it breaks parsing and the agent loses name/disallowedTools/isolation.
        In that case the marker goes after the frontmatter block.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        header = generated_header(comment)
        if content.startswith("---\n"):
            end = content.find("\n---\n", 4)
            if end != -1:
                cut = end + len("\n---\n")
                content = content[:cut] + "\n" + header + content[cut:]
                path.write_text(content, encoding="utf-8")
                return path
        path.write_text(header + "\n" + content, encoding="utf-8")
        return path
