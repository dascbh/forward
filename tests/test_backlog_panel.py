"""FWD-030: the fde-backlog panel (ADR-0019 rule 9, C-5 A1, FM4).
The skill is a procedure the agent runs; its rules are pinned here, and the
edits it prescribes are applied mechanically and read back by status.py."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = "skills/fde-backlog/SKILL.md"
COPY = ".claude/skills/fde-backlog/SKILL.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def flat(text: str) -> str:
    return " ".join(text.split())


class TestSkillRules(unittest.TestCase):
    RULES = (
        "Run `python3 bin/fde/status.py --format json` and show the panel",
        "running, planned, draft, closed",
        "multi-select for items",
        "a new `cycles/C-<n>/plan.md`",
        "state: draft",
        "## Items",
        "or an existing draft",
        "list its artifacts (plan, deploy, board, review, promotion, the "
        "demand specs",
        "the ADRs it cites) and read any one on request",
        "run the planner (the fde-spec role in cycle mode) to produce plan.md "
        "and deploy.md, and stop at the owner's sign-off",
        "**exit**",
        "Assigning B-ids to a backlog without them: give the next free `B-<n>` "
        "to each item that has none, as the first cell of a table row or as "
        "the first token of a bullet. Do it in one commit, before grouping.",
        "Grouping never writes a spec and never commits to anything.",
        "Only one cycle may be running; drafts may be many.",
        "After every edit, re-run status.py. The result must still parse (FM4)",
    )

    def test_skill_states_each_rule(self):
        text = flat(read(SKILL))
        for rule in self.RULES:
            self.assertIn(flat(rule), text, rule)

    def test_skill_is_a_procedure_not_a_wrapper(self):
        self.assertIn("there is no script behind it", read(SKILL))
        self.assertFalse((ROOT / "runtime/backlog.py").exists())

    def test_installed_copy_is_identical(self):
        self.assertEqual(read(SKILL), read(COPY))

    def test_readme_lists_the_skill(self):
        self.assertTrue("- `fde-backlog` —" in read("README.md"))


FIXTURE = """\
---
goal: not set
date: 2026-09-29
---

# Backlog

| # | item | evidence |
|---|---|---|
| 1 | first idea | opinion |
| 2 | second idea | usage-data |

## Loose

- B-7 an item that already has an id
- a bullet without one
"""


def assign_ids(text: str) -> str:
    """Section 3 of the skill, applied mechanically."""
    used = [int(n) for n in re.findall(r"\bB-(\d+)\b", text)]
    nxt = max(used, default=0) + 1
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells[0] == "#":
                line = line.replace("| # |", "| id |", 1)
            elif cells[0].isdigit():
                line = line.replace(f"| {cells[0]} |", f"| B-{nxt} |", 1)
                nxt += 1
        elif re.match(r"^- (?!B-\d+\b)", line):
            line = f"- B-{nxt} {line[2:]}"
            nxt += 1
        out.append(line)
    return "\n".join(out) + "\n"


def draft_template() -> str:
    """The new-draft plan.md exactly as the skill prescribes it."""
    m = re.search(r"```markdown\n(.*?)```", read(SKILL), re.S)
    assert m, "the skill carries no plan.md template"
    return re.sub(r"^ {2}", "", m.group(1), flags=re.M)


def status_json(root: Path) -> dict:
    r = subprocess.run([sys.executable, str(ROOT / "runtime/status.py"),
                        "--root", str(root), "--format", "json"],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


class TestRoundTrip(unittest.TestCase):
    """FM4: after the panel's edits, status.py still reads everything."""

    def test_ids_and_draft_read_back(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "backlog.md").write_text(assign_ids(FIXTURE), encoding="utf-8")
            data = status_json(root)
            ids = [it["id"] for s in data["backlog"]["sections"] for it in s["items"]]
            self.assertEqual(ids, ["B-8", "B-9", "B-7", "B-10"])
            self.assertEqual(data["warnings"], [])

            texts = {it["id"]: it["text"] for s in data["backlog"]["sections"]
                     for it in s["items"]}
            plan = root / "cycles" / "C-1" / "plan.md"
            plan.parent.mkdir(parents=True)
            head, item = draft_template().rsplit("\n- ", 1)
            self.assertEqual(item.strip(), "B-<n> <the item's text>")
            head = head.replace("C-<n>", "C-1").replace(
                "<one line, the user's words>", "first two ideas")
            plan.write_text(head + "\n" + "".join(
                f"- {i} {texts[i]}\n" for i in ("B-8", "B-10")), encoding="utf-8")
            data = status_json(root)
            self.assertEqual(data["warnings"], [])
            [c] = data["cycles"]
            self.assertEqual((c["id"], c["state"], c["objective"]),
                             ("C-1", "draft", "first two ideas"))
            self.assertEqual(c["artifacts"], ["plan.md"])
            self.assertEqual(c["demands"], [])
            body = plan.read_text(encoding="utf-8")
            self.assertIn("- B-8 first idea", body)
            self.assertIn("- B-10 a bullet without one", body)


if __name__ == "__main__":
    unittest.main()
