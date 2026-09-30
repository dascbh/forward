"""S-002 instruction changes stay put and stay in sync (FWD-003/004/007).
The drift-detector pattern: instructions are behavior (ADR-0001), and
these assertions are their eval."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from prose import ProseTestCase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    parts = text.split(f"\n## {heading}", 1)
    assert len(parts) == 2, f"section '{heading}' missing"
    return parts[1].split("\n## ", 1)[0]


class TestPerCycleTriage(ProseTestCase):
    """FWD-003 R3, moved to the cycle by ADR-0019 rule 3 (FWD-026)."""

    def test_skill_defines_per_cycle_inputs_with_tiebreaks(self):
        skill = read("skills/fde-triage/SKILL.md")
        for needle in ("judged for THIS cycle", "always false",
                       "Unsure → true", "take the larger",
                       "hard to undo"):
            self.assertIn(needle, skill, needle)
        self.assertNotIn("judged for THIS demand", skill)

    def test_demand_loop_states_the_per_cycle_rule(self):
        # FWD-037: the inputs were duplicates of fde-triage's ## Inputs
        # (cycles/C-14/inventory.md #5-#7); step 1 keeps the cycle rule
        # and points to the skill, which keeps the tiebreaks
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            flat = " ".join(section(read(rel), "Demand loop").split())
            self.assertIn("**Triage** the cycle (`fde-triage`). Size is set "
                          "on the cycle, never on a demand.", flat, rel)
            self.assertNotIn("judged for THIS demand", flat, rel)
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            inputs = " ".join(section(read(rel), "Inputs").split())
            for needle in ("judged for THIS cycle", "sensitive is always false",
                           "Unsure → true"):
                self.assertIn(needle, inputs, f"{rel}: {needle}")

    def test_skill_sizes_the_cycle_and_bounds_the_demand(self):
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            flat = " ".join(read(rel).split())
            for needle in ("Size is set on the cycle, never on a demand.",
                           "A demand is one goal (kernel ADR-0022), at most "
                           "about 300 production lines",
                           "a goal over the ceiling splits into smaller "
                           "goals, never into layers.",
                           "## RULE"):
                self.assertIn(needle, flat, f"{rel}: {needle}")


class TestI1BluntnessDecision(ProseTestCase):
    """FWD-004: the decision is on record where I1 gets explained."""

    def test_verify_skill_records_the_kept_bluntness(self):
        skill = read("skills/fde-verify/SKILL.md")
        self.assertIn("Known bluntness, kept on purpose", skill)
        self.assertIn("instructions ARE behavior", skill)


class TestExecutionProvenance(ProseTestCase):
    """FWD-007: the transcript link is asked for wherever findings are made."""

    def test_all_provenance_surfaces_name_agent_transcript(self):
        for rel in ("templates/findings.template.toml",
                    "skills/fde-review/SKILL.md",
                    "agents/fde-adversarial.md",
                    ".claude/agents/fde-adversarial.md"):
            self.assertIn("agent_transcript", read(rel), rel)


class TestRuleLaneIsAParagraphNotATableRow(ProseTestCase):
    """FWD-019/ADR-0015, R5/R6/FM-6: RULE is introduced in its own
    paragraph, positioned immediately before the existing table/sentence
    it precedes — never a row inside it, never altering a byte of it.
    Pinned literally, not just "still mentions XS somewhere": a table row
    silently added for RULE, or a reworded score sentence, would still
    contain the word XS and pass a looser check."""

    XS_S_M_L_TABLE = (
        "| score | size | planner (`fde-spec`, `plan.md`) | cycle review rounds | ADR | timebox |\n"
        "|---|---|---|---|---|---|\n"
        "| ≤ 1 | XS | minimal plan | 1 full | no | 30 min |\n"
        "| 2–3 | S | plan | 1 full | no | 1 h |\n"
        "| 4–6 | M | plan + ADRs | 1 full + 1 delta | yes | 3 h |\n"
        "| ≥ 7 | L | full plan + ADRs | 1 full + 1 delta | yes | 1 day |"
    )

    # reviews/FWD-026 F2/F3: size sets only planner depth and cycle rounds
    SCORE_SENTENCE = "score ≤ 1 → **XS** · 2–3 → **S** · 4–6 → **M** · ≥ 7 → **L**."

    def test_skill_table_is_unmodified_and_rule_precedes_it_as_prose(self):
        skill = read("skills/fde-triage/SKILL.md")
        self.assertIn(self.XS_S_M_L_TABLE, skill)
        heading = "## Score and size"
        self.assertIn(heading, skill)
        rule_para = skill.index("## RULE")
        table_heading = skill.index(heading)
        self.assertLess(rule_para, table_heading,
                        "RULE must be introduced before the table, never "
                        "inside or after it")
        # never a row: RULE does not appear inside the pinned table block
        # itself (already implied by the exact match above, asserted
        # again directly against the shape a smuggled row would take)
        self.assertNotIn("| RULE |", skill)

    def test_agents_and_template_score_sentence_is_unmodified(self):
        # FWD-037: AGENTS.md's RULE paragraph and score sentence were
        # duplicates of fde-triage (cycles/C-14/inventory.md #8, #9);
        # the ordering rule now holds in the skill and its installed copy
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            text = read(rel)
            self.assertIn(self.XS_S_M_L_TABLE, text, rel)
            self.assertLess(text.index("## RULE"),
                            text.index("## Score and size"), rel)
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            text = read(rel)
            self.assertNotIn(self.SCORE_SENTENCE, text, rel)
            self.assertIn("commit: RULE. The RULE lane: `fde-triage`.",
                          " ".join(text.split()), rel)

    R5 = ("Categorically distinct", "data_class", "reversible",
          "rule_lane_max_loc", "eval_paths",
          "eval-coverage` gate is completely unchanged",
          "verified_by` primacy")

    def test_rule_paragraph_says_what_r5_requires(self):
        # FWD-033 (A9, FM3): the R5 conditions moved, verbatim, to
        # fde-triage's ## RULE; FWD-037 dropped AGENTS.md's pointer
        # paragraph as its duplicate (cycles/C-14/inventory.md #8)
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            text = " ".join(read(rel).split())
            for needle in ("`rule-lane` gate", "kernel ADR-0015"):
                self.assertIn(needle, text, f"{rel}: {needle}")
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            rule = " ".join(section(read(rel), "RULE").split())
            for needle in self.R5:
                self.assertIn(needle.lower(), rule.lower(), f"{rel}: {needle}")
            for needle in ("merge commit", "binary file",
                           "`FORWARD: RULE — <one-line reason>`",
                           "re-verifies the claim against the real diff"):
                self.assertIn(needle, rule, f"{rel}: {needle}")


class TestBoundedReview(ProseTestCase):
    """ADR-0018: review rounds are a budget that ends, blocking is bounded
    by a declared threat model, and weight only orders the attack."""

    SURFACES = ("skills/fde-review/SKILL.md", "agents/fde-adversarial.md",
                "skills/fde-triage/SKILL.md", "AGENTS.md",
                "templates/AGENTS.md.template", "SETUP.md")

    def test_weight_never_blocks_or_adds_rounds(self):
        for rel in self.SURFACES:
            text = read(rel)
            self.assertNotIn("BLOCKS MERGE", text, rel)
            self.assertNotIn("weight >= 15", text, rel)
            self.assertNotIn("weight/10", text, rel)
        self.assertNotIn("three review cycles",
                         read("skills/fde-review/SKILL.md"))

    def test_review_budget_is_sized_and_never_extended(self):
        budget = section(read("skills/fde-review/SKILL.md"), "Budget")
        for needle in ("| XS, S | `[review] cycle_rounds_small` (default 1) | full |",
                       "| M, L | `[review] cycle_rounds_large` (default 2) | full, delta |",
                       "A demand review is always 1 round.", "No extension",
                       "*narrow*", "*declare*", "*pause*",
                       "never reopens the"):
            self.assertIn(needle, budget, needle)
        # reviews/FWD-028 F3: ADR-0019 rule 12, no third round at L
        self.assertNotIn("| L | 3 |", budget)

    def test_blocking_needs_severity_threat_model_and_a_criterion(self):
        for rel in ("skills/fde-review/SKILL.md", "agents/fde-adversarial.md"):
            block = section(read(rel), "What blocks")
            for needle in ("critical", "threat model", "acceptance criterion",
                           "failure mode"):
                self.assertIn(needle, block.lower(), f"{rel}: {needle}")
            self.assertIn("`[review] max_findings` (default 5)",
                          section(read(rel), "Cap"), rel)

    def test_spec_carries_a_threat_model_within_a_page(self):
        for rel in ("agents/fde-spec.md", "skills/fde-triage/SKILL.md"):
            text = read(rel)
            self.assertIn("## Threat model", text, rel)
            self.assertIn("~800 words", text, rel)
        # FWD-037: step 2's plan sentence moved to fde-spec
        # (cycles/C-14/inventory.md #18)
        for rel in ("agents/fde-spec.md", ".claude/agents/fde-spec.md"):
            self.assertIn("`plan.md` carries a `## Threat model`",
                          " ".join(read(rel).split()), rel)

    def test_triage_resizes_on_the_real_diff_and_gates_come_last(self):
        skill = read("skills/fde-triage/SKILL.md")
        # reviews/FWD-026 F1: an overrun is a fact for the board, never a
        # re-split at review
        overrun = " ".join(section(skill, "Overrun on the real diff").split())
        # FWD-032: one ceiling, applied at planning
        for needle in ("split at planning to fit ~300 production lines",
                       "is not re-split at review", "timebox"):
            self.assertIn(needle, overrun, needle)
        self.assertIn("instruction", section(skill, "Smallest mechanism first"))
        # FWD-037: AGENTS.md's step 1 budget line, timebox, overrun and
        # instruction-first sentences were duplicates of fde-triage, and
        # "never by one more round" of fde-review (cycles/C-14/inventory.md
        # #14-#17, #38); each rule is pinned where it now lives
        flat_skill = " ".join(skill.split())
        for needle in ("The rounds are the cycle review's budget, not a "
                       "minimum to extend", "| ≤ 1 | XS | minimal plan | "
                       "1 full | no | 30 min |",
                       "ships it as an instruction"):
            self.assertIn(needle, flat_skill, needle)
        self.assertIn("\"One more round\" is not an option",
                      " ".join(read("skills/fde-review/SKILL.md").split()))

    def test_architecture_revises_only_when_a_decision_changes(self):
        rev = section(read("agents/fde-architecture.md"),
                      "Revisions under review")
        self.assertIn("only when a finding changes a decision", rev)
        self.assertIn("same commit", rev)


class TestDeclaredCycle(ProseTestCase):
    """FWD-026, ADR-0019: backlog > cycle > demand. The cycle plans once and
    owns approval, review, promotion and deploy; demands derive and run in
    parallel. Instruction, not a gate (ADR-0018). Each rule is pinned as the
    sentence that states it (whitespace-normalized), so rewording a rule
    away goes red (reviews/FWD-022 F1)."""

    SURFACES = ("AGENTS.md", "templates/AGENTS.md.template")

    # anywhere in the file: the loop and ## Cycle share them
    RULES = {
        "new-fact": ("A new fact always goes to the backlog — never a fix, "
                     "an amendment or a question."),
        "replan": ("The one exception is a fact that invalidates the "
                   "demand's own ADR or criteria: the demand stops and the "
                   "cycle replans."),
        # FWD-036 (C-13): "everything else goes to the backlog" repeated
        # "new-fact" and the non-blocking path of DEMAND_BLOCKER; trimmed
        "owns": ("The cycle owns its declared criteria and its blocking "
                 "findings."),
        "size": "Size is set on the cycle, never on a demand.",
        # kernel ADR-0022 superseded "exactly one layer" and the layer split
        "ceiling": ("A demand is one goal, at most about 300 production "
                    "lines (`[lanes] demand_max_loc`)"),
        "split": ("its layer cell lists every layer it touches (kernel "
                  "ADR-0022)."),
        "merge": ("Merge happens per demand; promotion and deploy happen per "
                  "cycle."),
        "approval": ("Approval happens once, at plan sign-off, and is "
                     "inherited by everything after it"),
        "reask": "Only a replan asks the owner again.",
        "parallel": ("Demands run in parallel by default, coordinated on "
                     "`cycles/C-<n>/board.md`."),
        "board-record": ("The board is the record (I7), not the "
                         "conversation."),
        "rationale": "Code starts only inside a signed-off cycle (kernel ADR-0019) or in the direct lane",
    }

    # FWD-037: rules that left AGENTS.md, each pinned in the file that now
    # holds it (cycles/C-14/inventory.md #19, #41, #44)
    MOVED_RULES = {
        "adr": ("agents/fde-spec.md",
                "An ADR is the only home of a decision;"),
        "deploy": ("agents/fde-spec.md",
                   "steps ordered infra (expand) → back → front → infra "
                   "(contract), each with its verification and rollback"),
        "cycle-review": ("skills/fde-review/SKILL.md",
                         "the objective on the integrated result; it never "
                         "re-reviews a demand"),
    }

    # reviews/FWD-032 F4, narrowed to the cycle review by reviews/C-5 F1:
    # ## Cycle defines the spent budget, once
    # reviews/FWD-043 F1: it is a replan, and plan.md is not where it lands
    BUDGET_RULE = ("A cycle review budget spent with a blocker open is a "
                   "replan, the owner's call: narrow, declare the limit, or "
                   "pause, recorded on `board.md` and marked in "
                   "`promotion.md` at close, never in `plan.md`.")

    # the demand and the states live in ## Cycle; FWD-037 moved the cycle
    # directory's layout to fde-spec (cycles/C-14/inventory.md #47)
    LAYOUT = ("`specs/<id>/spec.md` plus `reviews/<id>/findings.toml`",
              "`draft` (grouped) → `planned` (specified, awaiting sign-off) "
              "→ `running` (signed off) → `closed` or `abandoned`",
              "laid out by `fde-spec`")
    SPEC_LAYOUT = ("`plan.md`", "`deploy.md`", "`board.md`", "`review.md`",
                   "`promotion.md`", "`.fde/templates/cycle/`")

    def flat(self, rel):
        return " ".join(read(rel).split())

    def cycle(self, rel):
        return " ".join(section(read(rel), "Cycle").split())

    def test_each_rule_is_stated_verbatim(self):
        for rel in self.SURFACES:
            text = self.flat(rel)
            for rid, rule in self.RULES.items():
                self.assertIn(rule, text, f"{rel}: {rid}")
        for rid, (rel, rule) in self.MOVED_RULES.items():
            for path in (rel, ".claude/" + rel):
                self.assertIn(rule, self.flat(path), f"{path}: {rid}")

    def test_cycle_section_states_the_layout(self):
        for rel in self.SURFACES:
            text = self.cycle(rel)
            for needle in self.LAYOUT:
                self.assertIn(needle, text, f"{rel}: {needle}")
        for rel in ("agents/fde-spec.md", ".claude/agents/fde-spec.md"):
            text = self.flat(rel)
            for needle in self.SPEC_LAYOUT:
                self.assertIn(needle, text, f"{rel}: {needle}")

    def test_per_demand_planning_is_gone(self):
        # ADR-0019 rule 10: a demand has no acceptance, failure modes,
        # architecture or promotion of its own; the single-file cycle and
        # its "concluded means declined by the user" wording are retired
        for rel in self.SURFACES:
            text = self.flat(rel)
            for gone in ("specs/<demand-id>/architecture.md",
                         "`failure-modes.toml`, and `acceptance.md`",
                         "promotions/<demand-id>/decision.md",
                         "Concluded means fixed, or declined by the user",
                         "write and commit `cycles/C-<n>.md`",
                         "## Next cycle", "closes as it stands"):
                self.assertNotIn(gone, text, f"{rel}: {gone}")

    def test_budget_and_fix_it_now_agree_with_the_cycle(self):
        # reviews/FWD-023 F1, F3, F4: the rules that route findings and new
        # requests elsewhere say the same thing as ## Cycle
        for rel in self.SURFACES:
            flat = self.flat(rel)
            # reviews/C-5 F1; FWD-037: ## Cycle holds the cycle review's
            # three options and points to fde-review for a finding's path
            # (cycles/C-14/inventory.md #38, #56, #57)
            self.assertIn("A finding's path: `fde-review`.", self.cycle(rel),
                          rel)
            self.assertIn(self.BUDGET_RULE, self.cycle(rel), rel)
            # FWD-031: sprints are retired, so there is no retro to surface at
            # FWD-036 (C-13): the pointer to ## Cycle was trimmed for the
            # word budget; the rule is unchanged
            self.assertIn("\"Fix it NOW\": the direct lane when it fits, "
                          "else the next cycle's first demand.", flat, rel)
            self.assertNotIn("surfaces at the retro", flat, rel)
            self.assertNotIn("bypasses the backlog", flat, rel)
        # reviews/FWD-028 F4: the budget's way out is ADR-0019's replan
        for rel in ("skills/fde-review/SKILL.md", ".claude/skills/fde-review/SKILL.md"):
            flat = " ".join(read(rel).split())
            self.assertIn("When a cycle review's budget is spent with a "
                          "blocking finding open, the owner picks one "
                          "(AGENTS.md `## Cycle`). The choice is recorded on "
                          "the cycle's `board.md`; a narrowed or declared "
                          "item is marked in `promotion.md` at close; "
                          "`plan.md` is not edited: that pick is the replan "
                          "(kernel ADR-0019).", flat, rel)
            for gone in ("the builder picks one", "nothing is declined "
                         "without the user", "the builder records it",
                         "a dated, named limit in `plan.md`",
                         "the cycle replans and the owner picks one",
                         "`fde-promotion` records the choice"):
                self.assertNotIn(gone, flat, f"{rel}: {gone}")
        for rel in ("skills/fde-backlog-format/SKILL.md", ".claude/skills/fde-backlog-format/SKILL.md"):
            flat = " ".join(read(rel).split())
            self.assertIn("\"fix it NOW\" skips the backlog order, never the "
                          "open cycle: it becomes the next cycle's first "
                          "demand", flat, rel)
            self.assertNotIn("runs immediately", flat, rel)

    def test_no_in_band_loophole(self):
        # FWD-022 FM-3's own trigger: a "small adjacent fix" allowance
        for rel in self.SURFACES:
            self.assertNotIn("small", self.cycle(rel), rel)

    def test_sizing_step_names_the_plan(self):
        # reviews/FWD-022 F5: step 1 and fde-triage agree on the first act
        for rel in self.SURFACES:
            self.assertIn("commit `plan.md`, and stop at the sign-off.",
                          self.flat(rel), rel)
        self.assertIn("`plan.md` comes first (AGENTS.md `## Cycle`)",
                      " ".join(read("skills/fde-triage/SKILL.md").split()))

    def test_skills_point_to_the_section(self):
        for rel in ("skills/fde-triage/SKILL.md", "skills/fde-backlog-format/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-backlog-format/SKILL.md",
                    "skills/fde-status/SKILL.md",
                    ".claude/skills/fde-status/SKILL.md"):
            self.assertIn("AGENTS.md `## Cycle`", read(rel), rel)

    def test_scrum_captures_discoveries_as_found(self):
        for rel in ("skills/fde-backlog-format/SKILL.md", ".claude/skills/fde-backlog-format/SKILL.md"):
            text = " ".join(read(rel).split())
            self.assertNotIn("`## Next cycle`", text, rel)
            self.assertIn("enter `backlog.md` as they are found", text, rel)


class TestCycleTemplates(ProseTestCase):
    """FWD-026, ADR-0019 rules 10-12: one skeleton per cycle file, carrying
    the header lines and sections the ADR names."""

    FILES = {
        "plan.md": ("cycle:", "state: draft", "date:", "size:",
                    "objective:", "signed-off:", "## Threat model",
                    "## Acceptance criteria", "## Failure modes",
                    "## Demands", "| id | layer | depends on | files | what "
                    "| meets | follows |"),
        "deploy.md": ("cycle:", "date:", "infra-expand", "back", "front",
                      "infra-contract", "Verification:", "Rollback:",
                      "Irreversible:"),
        "board.md": ("cycle:", "claim", "proposes", "blocked-on",
                     "decided"),
        "review.md": ("cycle:", "date:", "round:", "## Functioning",
                      "## Readiness", "## Findings"),
        "promotion.md": ("cycle:", "date:", "decision:", "## Evidence",
                         "## Signals", "## What changes"),
    }

    def test_each_skeleton_carries_its_header_and_sections(self):
        for name, needles in self.FILES.items():
            path = ROOT / "templates" / "cycle" / name
            self.assertTrue(path.exists(), name)
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertIn(needle, text, f"{name}: {needle}")

    def test_no_other_file_in_the_directory(self):
        d = ROOT / "templates" / "cycle"
        names = sorted(p.name for p in d.iterdir()) if d.is_dir() else []
        self.assertEqual(names, sorted(self.FILES))


class TestGuardAuditDocs(ProseTestCase):
    """FWD-006 R3: SETUP names the trail and the opt-in telemetry block."""

    def test_setup_documents_audit_file_and_otel_opt_in(self):
        setup = read("SETUP.md")
        self.assertIn("guard-audit.jsonl", setup)
        self.assertIn("CLAUDE_CODE_ENABLE_TELEMETRY", setup)
        self.assertIn("never enable it unasked", setup)

    def test_kernel_gitignores_its_own_audit_trail(self):
        self.assertIn(".fde/guard-audit.jsonl", read(".gitignore"))


class TestRolesAtTheRightLevel(ProseTestCase):
    """FWD-028 (ADR-0019 rules 5, 6, 10, 12; C-5 A4, A6): each role works
    at the level that owns its artifact."""

    def flat(self, rel):
        return " ".join(read(rel).split())

    def test_spec_plans_the_cycle_and_derives_one_page_demands(self):
        text = self.flat("agents/fde-spec.md")
        for needle in ("`cycles/C-<n>/plan.md`", "`cycles/C-<n>/deploy.md`",
                       "layer (`front`/`back`/`infra`), dependencies",
                       "It decides nothing new.",
                       "No per-demand acceptance, failure modes or architecture."):
            self.assertIn(needle, text, needle)
        for gone in ("failure-modes.toml", "acceptance.md", "Always / Ask first / Never"):
            self.assertNotIn(gone, text, gone)

    def test_architecture_writes_adrs_at_the_cycle(self):
        text = self.flat("agents/fde-architecture.md")
        self.assertIn("Each ADR names the demands that realize it", text)
        self.assertIn("No per-demand `architecture.md`.", text)
        self.assertNotIn("specs/<demand-id>/architecture.md", text)

    def test_promotion_works_per_cycle_on_declared_criteria(self):
        text = self.flat("agents/fde-promotion.md")
        for needle in ("`cycles/C-<n>/promotion.md`",
                       "Checks the declared criteria only",
                       "one line in `backlog.md` with `(C-<n>)`"):
            self.assertIn(needle, text, needle)
        self.assertNotIn("- `promotions/<demand-id>/decision.md`", text)

    def test_adversarial_has_demand_and_cycle_modes(self):
        for rel in ("agents/fde-adversarial.md",
                    ".claude/agents/fde-adversarial.md",
                    "skills/fde-review/SKILL.md"):
            text = " ".join(read(rel).split())
            for needle in ("conformance to the cycle ADRs",
                           "never re-reviews a demand", "*Functioning*",
                           "*Readiness*", "`cycles/C-<n>/review.md`",
                           "rollback exercised", "(I5)"):
                self.assertIn(needle, text, f"{rel}: {needle}")

    def test_walkthrough_runs_at_the_cycle_only_with_a_front_demand(self):
        for rel in ("skills/fde-walkthrough/SKILL.md",
                    "skills/fde-design/SKILL.md", "skills/fde-review/SKILL.md"):
            text = " ".join(read(rel).split())
            self.assertIn("only when the cycle has a `front` demand", text, rel)
        self.assertNotIn("Use for an M/L demand with a UI surface",
                         read("skills/fde-walkthrough/SKILL.md"))

    def test_walkthrough_runs_at_every_size(self):
        # reviews/FWD-028 F1, ADR-0019 rule 5: a cycle that changes the
        # interface always runs one, at any size, not opt-in
        for rel in ("skills/fde-walkthrough/SKILL.md",
                    ".claude/skills/fde-walkthrough/SKILL.md"):
            text = " ".join(read(rel).split())
            self.assertIn("It runs whenever the cycle has a `front` demand, "
                          "at every size", text, rel)
            self.assertIn("`[walkthrough]` in `fde.config.toml` sets only "
                          "the divergence gate, never whether the "
                          "walkthrough runs.", text, rel)
            for gone in ("| XS / S | never |", "opt-in, via `[walkthrough]`",
                         "Opt-in at every size"):
                self.assertNotIn(gone, text, f"{rel}: {gone}")


class TestReconcileText(ProseTestCase):
    """C-5 reconcile of reviews/FWD-026 F1-F4 and FWD-028 F3 against
    ADR-0019: one answer per fact, in every place that states it."""

    SURFACES = ("AGENTS.md", "templates/AGENTS.md.template")
    ALL = SURFACES + ("skills/fde-triage/SKILL.md",
                      ".claude/skills/fde-triage/SKILL.md",
                      "skills/fde-review/SKILL.md",
                      ".claude/skills/fde-review/SKILL.md")

    def flat(self, rel):
        return " ".join(read(rel).split())

    def test_overrun_is_a_board_fact_not_a_split_at_review(self):
        # F1: ADR-0019 rules 1 and 3
        for rel in self.ALL:
            text = self.flat(rel)
            for gone in ("split, don't review", "split, not reviewed",
                         "split before any review starts",
                         "enter them in the demand list"):
                self.assertNotIn(gone, text, f"{rel}: {gone}")
        # FWD-037: AGENTS.md's overrun sentence was a duplicate of
        # fde-triage's (cycles/C-14/inventory.md #16)
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            self.assertIn("is not re-split at review", self.flat(rel), rel)
            self.assertIn("the cycle replans only if a criterion or an ADR "
                          "changes", self.flat(rel), rel)

    def test_one_round_count_everywhere(self):
        # F2 (and FWD-028 F3): ADR-0019 rule 12
        # FWD-037: AGENTS.md's round count was a duplicate of
        # fde-triage's (cycles/C-14/inventory.md #10, #11)
        for rel in self.SURFACES:
            text = self.flat(rel)
            for gone in ("3 rounds", "all six roles"):
                self.assertNotIn(gone, text, f"{rel}: {gone}")
        triage = self.flat("skills/fde-triage/SKILL.md")
        self.assertIn("a demand review is 1 round", triage)
        self.assertIn("The size sets the depth of the planner and the number "
                      "of cycle review rounds.", triage)
        self.assertIn("| 4–6 | M | plan + ADRs | 1 full + 1 delta |", triage)
        # the old role-list row; "all five roles" at M/L stays (FWD-032 #3/#5)
        for gone in ("1 full + 2 delta", "| L | all five |"):
            self.assertNotIn(gone, triage, gone)

    def test_every_size_has_a_plan_and_a_promotion(self):
        # F3: ADR-0019 rules 3 and 4
        # FWD-037: step 1's "At every size" sentence was a duplicate of
        # fde-triage's (cycles/C-14/inventory.md #11); step 8 stays
        for rel in self.SURFACES:
            text = self.flat(rel)
            self.assertIn("promotion, at every size, is `fde-promotion`'s "
                          "decision", text, rel)
            self.assertNotIn("promotion (M/L)", text, rel)
        self.assertIn("Every size: `fde-spec` writes `plan.md`, a demand "
                      "review is 1 round, and the cycle closes with a "
                      "promotion by `fde-promotion`.",
                      self.flat("skills/fde-triage/SKILL.md"))

    def test_state_has_named_writers(self):
        # F4: who moves state:, and the only edits a frozen plan takes
        # reviews/C-5 F2: fde-backlog writes draft, fde-spec planned
        rule = ("`fde-backlog` groups items (backlog → draft); `fde-spec` "
                "writes `state: planned`; the orchestrating agent writes "
                "`running` with `signed-off:` at sign-off, then `closed` or "
                "`abandoned`. The plan is frozen at sign-off; these header "
                "lines are the only edits it takes.")
        # FWD-037: moved to fde-backlog (cycles/C-14/inventory.md #50, #51)
        for rel in ("skills/fde-backlog/SKILL.md",
                    ".claude/skills/fde-backlog/SKILL.md"):
            self.assertIn(rule, self.flat(rel), rel)
        for rel in self.SURFACES:
            self.assertIn("Who writes each state, and when a cycle closes: "
                          "`fde-backlog`.",
                          " ".join(section(read(rel), "Cycle").split()), rel)
        plan = self.flat("templates/cycle/plan.md")
        self.assertIn("draft (grouped) is written by fde-backlog; planned "
                      "(specified, awaiting sign-off) by fde-spec; running "
                      "(with signed-off:), closed and abandoned by the "
                      "orchestrating agent", plan)

    def test_role_scopes_include_cycles(self):
        import tomllib
        roles = {r["id"]: r for r in tomllib.loads(read("spec/roles.toml"))["role"]}
        for rid, out in (("spec", "cycles/C-<n>/plan.md"),
                         ("spec", "cycles/C-<n>/deploy.md"),
                         ("promotion", "cycles/C-<n>/promotion.md"),
                         ("adversarial", "cycles/C-<n>/review.md")):
            self.assertIn("cycles/**", roles[rid]["write_scope"], rid)
            self.assertIn(out, roles[rid]["outputs"], rid)
        for out in roles["spec"]["outputs"] + roles["architecture"]["outputs"]:
            self.assertNotRegex(out, r"acceptance\.md|failure-modes|architecture\.md")


def description(rel: str) -> str:
    front = read(rel).split("---", 2)[1]
    lines = [l for l in front.splitlines() if l.startswith("description:")]
    assert len(lines) == 1, f"{rel}: one single-line description"
    return lines[0][len("description:"):].strip()


class TestTerse(ProseTestCase):
    """FWD-033 (C-5 A9): the text loaded in every session stays small.
    AGENTS.md at most 1,100 words (FWD-037, C-14 A1); every skill and agent description at
    most 40 words, trigger phrases only. Rationale lives in ADRs."""

    AGENTS_MAX = 1100
    DESC_MAX = 40

    def instruction_files(self):
        for base in ("skills", ".claude/skills"):
            for p in sorted((ROOT / base).glob("*/SKILL.md")):
                yield str(p.relative_to(ROOT))
        for base in ("agents", ".claude/agents"):
            for p in sorted((ROOT / base).glob("*.md")):
                yield str(p.relative_to(ROOT))

    def test_agents_md_fits_the_budget(self):
        n = len(read("AGENTS.md").split())
        self.assertLessEqual(n, self.AGENTS_MAX, f"AGENTS.md has {n} words")

    def test_every_description_fits_the_budget(self):
        files = list(self.instruction_files())
        self.assertGreaterEqual(len(files), 20)   # not vacuous
        for rel in files:
            n = len(description(rel).split())
            self.assertLessEqual(n, self.DESC_MAX, f"{rel}: {n} words")

    def test_descriptions_carry_no_history(self):
        for rel in self.instruction_files():
            desc = description(rel).lower()
            for gone in ("prancheta", "absorbs", "discontinued", "adr-"):
                self.assertNotIn(gone, desc, f"{rel}: {gone}")

    def test_cut_rationale_is_gone_from_the_loaded_text(self):
        # the discovery's cut list: each lives in its ADR now
        for rel, gone in (
                ("AGENTS.md", "Noise"),
                ("AGENTS.md", "Codex truncates"),
                ("AGENTS.md", "only measurement and review do"),
                ("skills/fde-triage/SKILL.md", "Kahneman"),
                ("skills/fde-erosion/SKILL.md", "SlopCodeBench"),
                ("skills/fde-graph/SKILL.md", "GraphRAG"),
                ("skills/fde-design/SKILL.md", "the research showed"),
                ("skills/fde-walkthrough/SKILL.md",
                 "This is a partial mitigation, not a solved problem"),
                ("skills/fde-doctor/SKILL.md", "burns an open framework")):
            self.assertNotIn(gone, read(rel), f"{rel}: {gone}")

    def test_role_bodies_drop_the_repeated_handoff_line(self):
        for base in ("agents", ".claude/agents"):
            for p in sorted((ROOT / base).glob("*.md")):
                self.assertNotIn("Do not continue another role's conversation",
                                 " ".join(p.read_text(encoding="utf-8").split()),
                                 p.name)


class TestBacklogLineIsOneFormat(ProseTestCase):
    """FWD-033, discovery item 14: AGENTS.md and fde-scrum state the backlog
    line in the same words."""

    LINE = ("A backlog line is `B-<n>`, the text, `(C-<n>)` when a cycle "
            "found it, and its evidence (`opinion < usage-data < user-test "
            "< production`).")

    def test_same_sentence_everywhere(self):
        # FWD-037: AGENTS.md's copy was a duplicate; fde-scrum keeps the
        # one statement (cycles/C-14/inventory.md #67)
        for rel in ("skills/fde-backlog-format/SKILL.md",
                    ".claude/skills/fde-backlog-format/SKILL.md"):
            self.assertIn(self.LINE, " ".join(read(rel).split()), rel)
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertNotIn("A backlog line carries", read(rel), rel)


class TestReconcileC5(ProseTestCase):
    """C-5 reconcile of reviews/FWD-033 F1-F5 and reviews/C-5 F1-F3: every
    operative sentence the terse pass dropped is restored and pinned, and
    the demand blocker path, the cycle states and kernel ADR citations say
    one thing everywhere."""

    SURFACES = ("AGENTS.md", "templates/AGENTS.md.template")

    def flat(self, rel):
        return " ".join(read(rel).split())

    def sect(self, rel, heading):
        return " ".join(section(read(rel), heading).split())

    def step(self, rel, n):
        loop = section(read(rel), "Demand loop")
        start = loop.index(f"\n{n}. **")
        end = loop.find(f"\n{n + 1}. **", start)
        return " ".join(loop[start:end if end > 0 else None].split())

    # reviews/FWD-033 F1
    def test_promotion_isolation_is_stated_in_roles(self):
        for rel in self.SURFACES:
            self.assertIn("The adversarial and promotion roles run isolated: "
                          "artifact + spec only, never the builder's thread.",
                          self.sect(rel, "Roles"), rel)

    # reviews/FWD-033 F2
    def test_never_escalate_and_not_asked_beforehand(self):
        for rel in self.SURFACES:
            self.assertIn("Never escalate kernel-interpretation questions to "
                          "the user mid-demand: resolve from the skill, take "
                          "the stricter reading, flag it afterwards.",
                          self.sect(rel, "Detail"), rel)
        # FWD-037: step 8's failed-step sentence moved to fde-spec's
        # deploy.md bullet (cycles/C-14/inventory.md #46)
        for rel in ("agents/fde-spec.md", ".claude/agents/fde-spec.md"):
            self.assertIn("A failed step rolls back and the cycle stops; the "
                          "user is told the outcome, not asked beforehand.",
                          self.flat(rel), rel)

    # reviews/FWD-033 F3
    def test_cycle_review_runs_the_walkthrough_with_a_front_demand(self):
        # FWD-037: step 7's sentence was a duplicate of fde-review's cycle
        # mode (cycles/C-14/inventory.md #42); step 7 points there
        for rel in self.SURFACES:
            self.assertIn("**Review the cycle** (`fde-review`, cycle mode).",
                          self.step(rel, 7), rel)
        for rel in ("skills/fde-review/SKILL.md",
                    ".claude/skills/fde-review/SKILL.md"):
            self.assertIn("`fde-walkthrough` runs here, only when the cycle "
                          "has a `front` demand.", self.flat(rel), rel)
        for rel in ("skills/fde-walkthrough/SKILL.md",
                    ".claude/skills/fde-walkthrough/SKILL.md"):
            desc = description(rel)
            self.assertIn("at the cycle review when the cycle has a `front` "
                          "demand", desc, rel)
            self.assertLessEqual(len(desc.split()), TestTerse.DESC_MAX, rel)

    # reviews/FWD-033 F4: ADR-0019's rules, each by its key term, in
    # AGENTS.md or, since FWD-037, in the file the rule moved to
    # (cycles/C-14/inventory.md)
    ADR0019_TERMS = {
        1: "A new fact always goes to the backlog",
        2: "The cycle owns its declared criteria and its blocking findings",
        3: "Size is set on the cycle",
        4: "Merge happens per demand",
        5: "its layer cell lists every layer it touches",   # ADR-0022
        6: ("An ADR is the only home of a decision", "agents/fde-spec.md"),
        7: ("not asked beforehand", "agents/fde-spec.md"),
        8: "Approval happens once, at plan sign-off",
        9: "`fde-backlog`",
        10: "`deploy.md`",
        11: "`cycles/C-<n>/board.md`",
        12: ("never re-reviews a demand", "skills/fde-review/SKILL.md"),
        13: ("Sprints are retired", "skills/fde-backlog-format/SKILL.md"),
        14: "Gates follow the owning level",
        15: ("opened before kernel ADR-0019 finishes under its own rules",
             "skills/fde-backlog/SKILL.md"),
    }

    def test_agents_md_names_every_adr0019_rule(self):
        for n, term in self.ADR0019_TERMS.items():
            if isinstance(term, tuple):
                term, home = term
                files = (home, ".claude/" + home)
            else:
                files = self.SURFACES
            for rel in files:
                self.assertIn(term, self.flat(rel), f"{rel}: rule {n}")

    # reviews/C-5 F1
    DEMAND_BLOCKER = ("A demand review's blocking finding is fixed inside "
                      "that demand and proven by its regression test; the "
                      "owner is asked only when the fix changes a criterion "
                      "or an ADR, which is a replan. A non-blocking finding is "
                      "triaged by the builder (`## Triage`): fixed in the "
                      "demand as a patch, deferred to `backlog.md`, or "
                      "dropped; one that shows a plan criterion unmet is "
                      "fixed by the cycle.")

    def test_demand_blocker_is_fixed_inside_the_demand(self):
        # FWD-037: AGENTS.md's copy of the demand blocker path was a
        # duplicate of fde-review's (cycles/C-14/inventory.md #38, #56,
        # #57); ## Cycle points there and keeps the cycle review's budget
        for rel in self.SURFACES:
            self.assertIn("A finding's path: `fde-review`.",
                          self.sect(rel, "Cycle"), rel)
            text = self.flat(rel)
            self.assertNotIn("Budget spent with a blocker open → the owner "
                             "picks", text, rel)
            self.assertIn(TestDeclaredCycle.BUDGET_RULE, text, rel)
        for rel in ("skills/fde-review/SKILL.md",
                    ".claude/skills/fde-review/SKILL.md"):
            text = self.flat(rel)
            self.assertIn(self.DEMAND_BLOCKER, text, rel)
            self.assertIn("When a cycle review's budget is spent with a "
                          "blocking finding open, the owner picks one", text,
                          rel)
            self.assertNotIn("When the budget is spent with a blocking "
                             "finding open", text, rel)

    # reviews/C-5 F2
    def test_states_have_one_meaning_and_one_writer(self):
        states = ("`draft` (grouped) → `planned` (specified, awaiting "
                  "sign-off) → `running` (signed off) → `closed` or "
                  "`abandoned`")
        writers = ("`fde-backlog` groups items (backlog → draft); "
                   "`fde-spec` writes `state: planned`; the orchestrating "
                   "agent writes `running` with `signed-off:` at sign-off, "
                   "then `closed` or `abandoned`. The plan is frozen at "
                   "sign-off; these header lines are the only edits it "
                   "takes.")
        for rel in self.SURFACES:
            cycle = self.sect(rel, "Cycle")
            self.assertIn(states, cycle, rel)
            self.assertNotIn("planned (signed off)", self.flat(rel), rel)
        # FWD-037: the writers moved to fde-backlog (inventory #50, #51)
        for rel in ("skills/fde-backlog/SKILL.md",
                    ".claude/skills/fde-backlog/SKILL.md"):
            self.assertIn(writers, self.flat(rel), rel)
        for rel in ("skills/fde-backlog/SKILL.md",
                    ".claude/skills/fde-backlog/SKILL.md"):
            text = self.flat(rel)
            self.assertIn(states, text, rel)
            self.assertIn("`fde-spec` writes `state: planned` when the plan "
                          "is specified", text, rel)
            self.assertNotIn("Never set `state: planned` yourself; the "
                             "owner's sign-off does", text, rel)
        for rel in ("agents/fde-spec.md", ".claude/agents/fde-spec.md"):
            self.assertIn("write `state: planned` in `plan.md`",
                          self.flat(rel), rel)
        plan = self.flat("templates/cycle/plan.md")
        self.assertIn("draft (grouped) is written by fde-backlog; planned "
                      "(specified, awaiting sign-off) by fde-spec; running "
                      "(with signed-off:), closed and abandoned by the "
                      "orchestrating agent", plan)
        self.assertIn("## Items", read("templates/cycle/plan.md"))
        adr = read("docs/adr/0019-backlog-cycle-demand.md")
        self.assertRegex(adr, r"(?m)^amended: 2026-09-29 .*rule 9")
        self.assertIn("`draft` (grouped) → `planned` (specified, awaiting "
                      "sign-off) → `running` (signed off) → `closed`",
                      " ".join(adr.split()))

    def test_agents_md_names_the_backlog_to_draft_step(self):
        # FWD-037: the step moved with the state writers to fde-backlog;
        # AGENTS.md names the three levels and points there
        for rel in self.SURFACES:
            self.assertIn("Three levels: backlog → cycle → demand",
                          self.flat(rel), rel)
        for rel in ("skills/fde-backlog/SKILL.md",
                    ".claude/skills/fde-backlog/SKILL.md"):
            self.assertIn("backlog → draft", self.flat(rel), rel)

    # reviews/C-5 F3 + note: sync migrates and bumps the version
    def test_sync_migrates_next_cycle_and_bumps_the_version(self):
        for rel in ("skills/fde-sync/SKILL.md",
                    ".claude/skills/fde-sync/SKILL.md"):
            text = self.flat(rel)
            self.assertIn("`kernel_version` in `fde.config.toml`", text, rel)
            self.assertIn("`migrations/*.toml`", text, rel)
        for rel in ("spec/migrations/0.18-0.19-next-cycle-to-backlog.toml",
                    ".fde/spec/migrations/0.18-0.19-next-cycle-to-backlog.toml"):
            text = self.flat(rel)
            for needle in ("`## Next cycle`", "`B-<n>`", "`(C-<n>)`",
                           "kernel ADR-0019 rule 15"):
                self.assertIn(needle, text, f"{rel}: {needle}")
        setup = self.flat("SETUP.md")
        self.assertIn("`## Next cycle`", section(read("SETUP.md"),
                                                 "Sync — regeneration"))
        self.assertIn("kernel_version", setup)

    def client_texts(self):
        yield from ("AGENTS.md", "templates/AGENTS.md.template", "SETUP.md")
        for base in ("skills", ".claude/skills", "agents", ".claude/agents",
                     "templates", ".fde/templates", "spec", ".fde/spec"):
            for p in sorted((ROOT / base).rglob("*")):
                if p.is_file() and p.suffix in (".md", ".toml", ".template",
                                                ".yml"):
                    yield str(p.relative_to(ROOT))

    def test_no_client_text_cites_a_bare_kernel_adr(self):
        import re
        files = list(self.client_texts())
        self.assertGreater(len(files), 40)   # not vacuous
        for rel in files:
            text = self.flat(rel)
            bare = re.findall(r"(?<!kernel )ADR-00\d\d", text)
            self.assertEqual(bare, [], rel)

    # reviews/C-5 note
    def test_readme_triage_sizes_the_cycle(self):
        readme = self.flat("README.md")
        self.assertIn("`fde-triage` — sizes the cycle", readme)
        self.assertNotIn("sizes the demand", readme)


class TestReviewByWeight(ProseTestCase):
    """FWD-036 (C-13, kernel ADR-0021): review is sized by what is at risk.
    FM1: one rule, pinned verbatim, in AGENTS.md step 5 (+ template),
    fde-review and fde-adversarial (+ installed copies), so the texts
    cannot disagree on which review a demand gets."""

    RULE = ("A coding demand inside a signed-off plan: isolated code "
            "review (diff × demand spec, ADR conformance, tests, the layer's "
            "check; `kind = \"code\"`; ~10 minutes; no scratch repositories "
            "or probe hunt). A sensitive or irreversible demand, or a real "
            "diff over ~300 production lines: adversarial review. An M/L "
            "plan, before sign-off: adversarial plan review (`kind = "
            "\"plan\"`). The cycle review is unchanged.")

    SURFACES = ("AGENTS.md", "templates/AGENTS.md.template",
                "skills/fde-review/SKILL.md",
                ".claude/skills/fde-review/SKILL.md",
                "agents/fde-adversarial.md",
                ".claude/agents/fde-adversarial.md")

    def flat(self, text):
        return " ".join(text.split())

    def test_the_rule_is_stated_verbatim_everywhere(self):
        for rel in self.SURFACES:
            text = self.flat(read(rel))
            self.assertIn(self.RULE, text, rel)
            self.assertEqual(text.count(self.RULE), 1, rel)
            self.assertIn("kernel ADR-0021", text, rel)

    def test_agents_md_states_it_in_step_5(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            loop = section(read(rel), "Demand loop")
            start = loop.index("\n5. **")
            step5 = self.flat(loop[start:loop.index("\n6. **", start)])
            self.assertIn(self.RULE, step5, rel)
            # the old one-size list is gone: the rule replaces it
            self.assertNotIn("weight-ordered: tests, code review", step5, rel)

    def test_review_skill_states_it_under_mode(self):
        for rel in ("skills/fde-review/SKILL.md",
                    ".claude/skills/fde-review/SKILL.md"):
            self.assertIn(self.RULE, self.flat(section(read(rel), "Mode")),
                          rel)

    def test_the_reviewer_knows_its_mode_and_budget(self):
        for rel in ("agents/fde-adversarial.md",
                    ".claude/agents/fde-adversarial.md"):
            mode = self.flat(section(read(rel), "Mode"))
            self.assertIn(self.RULE, mode, rel)
            for needle in ("- **code**:", "- **adversarial**:",
                           "- **plan**:", "- **cycle**:",
                           "Budget: about 10 minutes, 1 round.",
                           "Budget: 1 round.",
                           "1 round at XS/S, full + delta at M/L"):
                self.assertIn(needle, mode, f"{rel}: {needle}")
            desc = description(rel)
            for word in ("code", "adversarial", "plan", "cycle"):
                self.assertIn(word, desc.lower(), f"{rel}: {word}")

    def test_findings_template_carries_kind_and_isolation(self):
        for rel in ("templates/findings.template.toml",
                    ".fde/templates/findings.template.toml"):
            text = read(rel)
            self.assertIn('kind = "{{REVIEW_KIND}}"', text, rel)
            self.assertIn('code | adversarial | plan | cycle', text, rel)
            # a code review is isolated too (I2)
            self.assertIn('context_policy = "artifact_only"', text, rel)

    # C-13 cycle F1: the texts that run BEFORE sign-off schedule the plan
    # review, so a cold agent cannot reach the sign-off without it.
    SCHEDULE = ("At M/L, the adversarial plan review (kernel ADR-0021) runs "
                "before the sign-off: the owner signs the plan that answered "
                "its findings.")

    def test_plan_review_is_scheduled_before_sign_off(self):
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md",
                    "agents/fde-spec.md", ".claude/agents/fde-spec.md"):
            text = self.flat(read(rel))
            self.assertEqual(text.count(self.SCHEDULE), 1, rel)
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            text = self.flat(read(rel))
            # scheduled before the planner stops at the sign-off
            self.assertLess(text.index(self.SCHEDULE),
                            text.index("the planner stops at the sign-off"),
                            rel)
            self.assertIn("`FORWARD: M — spec + plan review + architecture + "
                          "impl + demand review(1r) + cycle review(full+delta) "
                          "+ promotion`", text, rel)
            self.assertIn("`FORWARD: L — full spec + plan review + "
                          "architecture + impl + demand review(1r) + cycle "
                          "review(full+delta) + promotion`", text, rel)
        for rel in ("agents/fde-spec.md", ".claude/agents/fde-spec.md"):
            text = self.flat(read(rel))
            self.assertLess(text.index(self.SCHEDULE),
                            text.index("Stop at the sign-off"), rel)
        for rel in ("skills/fde-review/SKILL.md",
                    ".claude/skills/fde-review/SKILL.md"):
            text = self.flat(section(read(rel), "Mode"))
            plan = text[text.index("- **Plan**"):text.index("- **Cycle**")]
            self.assertIn(self.SCHEDULE, plan, rel)

    # C-13 code F1: step 1 no longer says size sets "only" two things
    def test_step_1_does_not_limit_what_size_sets(self):
        # FWD-037: step 1's size sentence was a duplicate of fde-triage's
        # (cycles/C-14/inventory.md #10); the rule is pinned there
        for rel in ("AGENTS.md", "templates/AGENTS.md.template",
                    "skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            self.assertNotIn("size sets only", self.flat(read(rel)).lower(),
                             rel)
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            self.assertIn("The size sets the depth of the planner and the "
                          "number of cycle review rounds.",
                          self.flat(read(rel)), rel)

    # C-13 cycle F2: when code review and adversarial both match, risk wins
    RISK = ("The risk rule wins: a demand that is sensitive or irreversible, "
            "or whose real diff overruns ~300 production lines, gets "
            "adversarial review even inside a signed-off plan, and "
            "`plan.md`'s demand table marks it (`adversarial` in its row).")

    def test_the_risk_rule_wins(self):
        for rel in ("skills/fde-review/SKILL.md",
                    ".claude/skills/fde-review/SKILL.md"):
            mode = self.flat(section(read(rel), "Mode"))
            self.assertEqual(mode.count(self.RISK), 1, rel)
            self.assertIn("kernel ADR-0021", mode, rel)

    # C-13 cycle F4: the README names the four modes
    def test_readme_names_the_four_review_modes(self):
        text = self.flat(read("README.md"))
        start = text.index("- `fde-review` —")
        line = text[start:text.index("- `fde-debug`", start)]
        for mode in ("code", "adversarial", "plan", "cycle"):
            self.assertIn(mode, line, mode)
        self.assertNotIn("two-pass review", line)



class TestInventory(ProseTestCase):
    """FWD-037 (C-14 A1, FM1): AGENTS.md became a skeleton. The inventory,
    cycles/C-14/inventory.md, committed before any sentence moved, maps
    each sentence of the old loop, cycle, backlog and detail sections to
    stays / moves → <file> / duplicate of <file>. A moved sentence must be
    in its file verbatim, whitespace-normalized; a moved or duplicate one
    must be gone from AGENTS.md; every must-stay rule must be in AGENTS.md
    and its template."""

    INVENTORY = "cycles/C-14/inventory.md"
    SURFACES = ("AGENTS.md", "templates/AGENTS.md.template")
    ROW = re.compile(r"^\| (\d+) \| ([^|]+?) \| ([^|]+?) \| (.+) \|$")
    # files renamed after the inventory was frozen (FWD-039, B-37): the
    # inventory is the record, the test follows the file to its new name
    RENAMED = {"skills/fde-scrum/SKILL.md": "skills/fde-backlog-format/SKILL.md"}

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def rows(self):
        text = read(self.INVENTORY)
        body = text.split("\n## Sentences\n", 1)[1].split("\n## ", 1)[0]
        out = []
        for line in body.splitlines():
            m = self.ROW.match(line)
            if m:
                out.append((int(m.group(1)), m.group(3).strip(),
                            self.flat(m.group(4))))
        return out

    def must_stay(self):
        text = read(self.INVENTORY)
        body = text.split("\n## Must stay in AGENTS.md\n", 1)[1]
        out = []
        for line in body.splitlines():
            m = re.match(r"^\| ([^|]+?) \| (.+) \|$", line)
            if m and m.group(1) != "rule" and not m.group(1).startswith("-"):
                out.append((m.group(1), self.flat(m.group(2))))
        return out

    def test_inventory_is_complete_and_well_formed(self):
        rows = self.rows()
        self.assertEqual([n for n, _, _ in rows], list(range(1, len(rows) + 1)))
        self.assertGreaterEqual(len(rows), 70)   # not vacuous
        kinds = set()
        for n, tag, _ in rows:
            m = re.fullmatch(r"(stays)|moves → (\S+)|duplicate of (\S+)( .*)?",
                             tag)
            self.assertIsNotNone(m, f"#{n}: {tag}")
            kinds.add(tag.split()[0])
            target = self.RENAMED.get(m.group(2) or m.group(3),
                                      m.group(2) or m.group(3))
            if target:
                self.assertTrue((ROOT / target).is_file(), f"#{n}: {target}")
        self.assertEqual(kinds, {"stays", "moves", "duplicate"})

    def test_every_moved_sentence_is_in_its_file_verbatim(self):
        moved = [(n, tag.split("→", 1)[1].strip(), s)
                 for n, tag, s in self.rows() if tag.startswith("moves")]
        self.assertGreaterEqual(len(moved), 5)   # not vacuous
        for n, target, sentence in moved:
            for rel in (target, ".claude/" + target):
                self.assertIn(sentence, self.flat(read(rel)), f"#{n}: {rel}")

    def test_moved_and_duplicate_sentences_left_agents_md(self):
        for n, tag, sentence in self.rows():
            if tag == "stays":
                continue
            for rel in self.SURFACES:
                self.assertNotIn(sentence, self.flat(read(rel)), f"#{n}: {rel}")

    def test_every_must_stay_rule_is_in_agents_md(self):
        rules = self.must_stay()
        names = {name for name, _ in rules}
        self.assertEqual(names, {"invariants", "three levels",
                                 "one cycle running", "sign-off once",
                                 "new fact to backlog", "one layer per demand",
                                 "never --no-verify",
                                 "review sizing sentence"})
        # kernel ADR-0022 superseded this C-14 row; the closed cycle's
        # inventory stays as it was, its replacement is pinned instead
        superseded = {"one layer per demand": "A demand is one goal",
                      # kernel ADR-0024: small cycles run in parallel
                      "one cycle running": "several cycles run at once when "
                                           "their files are disjoint"}
        for rel in self.SURFACES:
            text = self.flat(read(rel))
            for name, anchor in rules:
                self.assertIn(superseded.get(name, anchor), text,
                              f"{rel}: {name}")

    def test_the_review_sizing_sentence_is_the_pinned_rule(self):
        anchor = dict(self.must_stay())["review sizing sentence"]
        self.assertEqual(anchor, TestReviewByWeight.RULE)


class TestOpenWording(ProseTestCase):
    """FWD-043 (C-14 A2): each open wording has one pinned sentence in the
    skill or template that owns its topic, source and installed copy."""

    @staticmethod
    def flat(rel: str) -> str:
        return " ".join(read(rel).split())

    def pinned(self, rels, sentence):
        for rel in rels:
            self.assertIn(sentence, self.flat(rel), rel)

    REVIEW = ("skills/fde-review/SKILL.md", ".claude/skills/fde-review/SKILL.md")

    def test_b29_budget_spent_is_a_replan(self):
        # reviews/FWD-043 F1: one statement, the replan edits no plan.md
        self.pinned(self.REVIEW, "`plan.md` is not edited: that pick is the "
                    "replan (kernel ADR-0019).")
        for rel in self.REVIEW:
            for gone in ("It is a replan (kernel ADR-0019)",
                         "`plan.md` stays frozen"):
                self.assertNotIn(gone, self.flat(rel), rel)

    def test_b11_resync_before_proposing(self):
        self.pinned(("skills/fde-backlog/SKILL.md",
                     ".claude/skills/fde-backlog/SKILL.md"),
                    "Before proposing a plan for a paused or long-running "
                    "cycle, fetch and read the log since the last known commit")

    def test_b48_b49_before_the_cycle_review(self):
        for rel in self.REVIEW:
            text = " ".join(section(read(rel), "Before the cycle review").split())
            self.assertIn("The demand reviews are committed before the cycle "
                          "review starts", text, rel)
            self.assertIn("A change to a reader or a gate is proven read-only "
                          "against a real client before the cycle review",
                          text, rel)

    def test_b40_rollback_reverts_merges_never_a_range(self):
        self.pinned(("templates/cycle/deploy.md", ".fde/templates/cycle/deploy.md",
                     "templates/cycle/plan.md", ".fde/templates/cycle/plan.md"),
                    "Rollback reverts the demand merges and the release "
                    "commit, never a range: a range would revert the cycle's "
                    "own records.")

    def test_b21_mnt9_is_resolvable(self):
        self.pinned(("AGENTS.md", "templates/AGENTS.md.template"),
                    "Nothing is fixed in-band (MNT-9 scope discipline)")
        # the gloss is the principle's own name in the catalog
        self.assertIn("MNT-9 scope discipline:",
                      read("spec/dimensions/quality-attributes.toml"))

    def test_b25_the_planner_writes_the_intended_model(self):
        self.pinned(("skills/fde-walkthrough/SKILL.md",
                     ".claude/skills/fde-walkthrough/SKILL.md"),
                    "the planner (`fde-spec`) compiles "
                    "`specs/<demand-id>/design/intended-model.md`, at every size")
        self.pinned(("agents/fde-spec.md", ".claude/agents/fde-spec.md"),
                    "For a `front` demand, at every size, the planner also "
                    "writes `specs/<demand-id>/design/intended-model.md`")
        self.assertNotIn("the `architecture` role compiles",
                         self.flat("skills/fde-walkthrough/SKILL.md"))
        for rel in ("agents/fde-architecture.md", ".claude/agents/fde-architecture.md"):
            self.assertNotIn("intended-model", read(rel), rel)
        import tomllib
        roles = {r["id"]: r for r in tomllib.loads(read("spec/roles.toml"))["role"]}
        model = "specs/<front-demand-id>/design/intended-model.md"
        self.assertIn(model, roles["spec"]["outputs"])
        self.assertNotIn(model, roles["architecture"]["outputs"])


class TestSkeletonPointsToDesignAndSurvey(ProseTestCase):
    """reviews/C-14 F4: a front or inherited-system cycle still finds its
    skill from the loop in AGENTS.md."""

    def test_plan_step_points_to_design_and_survey(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            flat = " ".join(read(rel).split())
            self.assertIn("2. **Plan** the cycle (`fde-spec`; UI: `fde-design`; "
                          "inherited system: `fde-survey`).", flat, rel)


if __name__ == "__main__":
    unittest.main()
