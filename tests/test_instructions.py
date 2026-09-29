"""S-002 instruction changes stay put and stay in sync (FWD-003/004/007).
The drift-detector pattern: instructions are behavior (ADR-0001), and
these assertions are their eval."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    parts = text.split(f"\n## {heading}", 1)
    assert len(parts) == 2, f"section '{heading}' missing"
    return parts[1].split("\n## ", 1)[0]


class TestPerCycleTriage(unittest.TestCase):
    """FWD-003 R3, moved to the cycle by ADR-0019 rule 3 (FWD-026)."""

    def test_skill_defines_per_cycle_inputs_with_tiebreaks(self):
        skill = read("skills/fde-triage/SKILL.md")
        for needle in ("judged for THIS cycle", "always false",
                       "Unsure → true", "take the larger",
                       "hard to undo"):
            self.assertIn(needle, skill, needle)
        self.assertNotIn("judged for THIS demand", skill)

    def test_demand_loop_states_the_per_cycle_rule(self):
        # content only: that the template and AGENTS.md carry the same
        # section is the agents-md pair in tests/mirror.toml (FWD-020)
        flat = " ".join(section(read("AGENTS.md"), "Demand loop").split())
        for needle in ("judged for THIS cycle", "always false",
                       "Unsure on either → true"):
            self.assertIn(needle, flat, needle)
        self.assertNotIn("judged for THIS demand", flat)

    def test_skill_sizes_the_cycle_and_bounds_the_demand(self):
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            flat = " ".join(read(rel).split())
            for needle in ("Size is set on the cycle, never on a demand.",
                           "A demand is at most about 300 production lines "
                           "and has exactly one layer: `front`, `back` or "
                           "`infra`.",
                           "A change that spans layers is always split, "
                           "however small.",
                           "## RULE"):
                self.assertIn(needle, flat, f"{rel}: {needle}")


class TestI1BluntnessDecision(unittest.TestCase):
    """FWD-004: the decision is on record where I1 gets explained."""

    def test_verify_skill_records_the_kept_bluntness(self):
        skill = read("skills/fde-verify/SKILL.md")
        self.assertIn("Known bluntness, kept on purpose", skill)
        self.assertIn("instructions ARE behavior", skill)


class TestExecutionProvenance(unittest.TestCase):
    """FWD-007: the transcript link is asked for wherever findings are made."""

    def test_all_provenance_surfaces_name_agent_transcript(self):
        for rel in ("templates/findings.template.toml",
                    "skills/fde-review/SKILL.md",
                    "agents/fde-adversarial.md",
                    ".claude/agents/fde-adversarial.md"):
            self.assertIn("agent_transcript", read(rel), rel)


class TestRuleLaneIsAParagraphNotATableRow(unittest.TestCase):
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
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            text = read(rel)
            self.assertIn(self.SCORE_SENTENCE, text, rel)
            rule_para = text.index("RULE, checked mechanically")
            sentence_at = text.index(self.SCORE_SENTENCE)
            self.assertLess(rule_para, sentence_at,
                            f"{rel}: RULE paragraph must precede the "
                            f"score-boundary sentence, never follow it")

    def test_rule_paragraph_says_what_r5_requires(self):
        # content only, in each surface on its own; their byte identity is
        # the agents-md pair in tests/mirror.toml (FWD-020)
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            text = read(rel)
            start = text.index("**RULE, checked mechanically")
            para = text[start:text.index(self.SCORE_SENTENCE)]
            for needle in ("Categorically distinct", "data_class",
                           "reversible", "rule_lane_max_loc", "eval_paths",
                           "eval-coverage` gate is completely unchanged",
                           "verified_by` primacy"):
                self.assertIn(needle, para, f"{rel}: {needle}")


class TestBoundedReview(unittest.TestCase):
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
        for needle in ("| XS, S | 1 | full |", "| M, L | 2 | full, delta |",
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
            self.assertIn("five", section(read(rel), "Cap"), rel)

    def test_spec_carries_a_threat_model_within_a_page(self):
        for rel in ("agents/fde-spec.md", "skills/fde-triage/SKILL.md"):
            text = read(rel)
            self.assertIn("## Threat model", text, rel)
            self.assertIn("~800 words", text, rel)
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("## Threat model", read(rel), rel)

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
        agents = " ".join(read("AGENTS.md").split())
        for needle in ("Budgets, not minimums", "never extended",
                       "Timebox: XS 30 min", "instruction first",
                       "never one more round"):
            self.assertIn(needle, agents, needle)

    def test_architecture_revises_only_when_a_decision_changes(self):
        rev = section(read("agents/fde-architecture.md"),
                      "Revisions under review")
        self.assertIn("only when a finding changes a decision", rev)
        self.assertIn("same commit", rev)


class TestDeclaredCycle(unittest.TestCase):
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
        "owns": ("The cycle owns its declared criteria and its blocking "
                 "findings; everything else goes to the backlog."),
        "size": "Size is set on the cycle, never on a demand.",
        "ceiling": ("A demand is at most about 300 production lines and has "
                    "exactly one layer: `front`, `back` or `infra`."),
        "split": ("A change that spans layers is always split, however "
                  "small."),
        "merge": ("Merge happens per demand; promotion and deploy happen per "
                  "cycle."),
        "deploy": ("The deploy plan runs infra-expand → back → front → "
                   "infra-contract, and every step has its own verification "
                   "and rollback."),
        "adr": "An ADR is the only home of a decision.",
        "approval": ("Approval happens once, at plan sign-off, and is "
                     "inherited by everything after it"),
        "reask": "Only a replan asks the owner again.",
        "parallel": ("Demands run in parallel by default, coordinated on "
                     "`cycles/C-<n>/board.md`."),
        "board-record": ("The board is the record (I7), not the "
                         "conversation."),
        "cycle-review": ("The cycle review judges the objective — "
                         "functioning and readiness against `plan.md` — and "
                         "never re-reviews a demand."),
        "rationale": "the rationale is ADR-0019",
    }

    # the layout lives in ## Cycle
    LAYOUT = ("`plan.md`", "`deploy.md`", "`board.md`", "`review.md`",
              "`promotion.md`", "`.fde/templates/cycle/`",
              "`specs/<id>/spec.md` plus `reviews/<id>/findings.toml`",
              "`draft → planned (signed off) → running → closed`")

    def flat(self, rel):
        return " ".join(read(rel).split())

    def cycle(self, rel):
        return " ".join(section(read(rel), "Cycle").split())

    def test_each_rule_is_stated_verbatim(self):
        for rel in self.SURFACES:
            text = self.flat(rel)
            for rid, rule in self.RULES.items():
                self.assertIn(rule, text, f"{rel}: {rid}")

    def test_cycle_section_states_the_layout(self):
        for rel in self.SURFACES:
            text = self.cycle(rel)
            for needle in self.LAYOUT:
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
            self.assertIn("Budget spent with a blocker open → replan "
                          "(`## Cycle`): the user narrows, declares the "
                          "limit, or pauses; never one more round "
                          "(`fde-review`).", flat, rel)
            # FWD-031: sprints are retired, so there is no retro to surface at
            self.assertIn("\"Fix it NOW\" skips the backlog order, never the "
                          "open cycle (`## Cycle`): it becomes the next "
                          "cycle's first demand.", flat, rel)
            self.assertNotIn("surfaces at the retro", flat, rel)
            self.assertNotIn("bypasses the backlog", flat, rel)
        # reviews/FWD-028 F4: the budget's way out is ADR-0019's replan
        for rel in ("skills/fde-review/SKILL.md", ".claude/skills/fde-review/SKILL.md"):
            flat = " ".join(read(rel).split())
            self.assertIn("When the budget is spent with a blocking finding "
                          "open, the cycle replans and the owner picks one "
                          "(AGENTS.md `## Cycle`). `fde-promotion` records "
                          "the choice in `promotion.md`; `plan.md` stays "
                          "frozen.", flat, rel)
            self.assertIn("A non-blocking finding goes to `backlog.md` by "
                          "default.", flat, rel)
            for gone in ("the builder picks one", "nothing is declined "
                         "without the user", "the builder records it",
                         "a dated, named limit in `plan.md`"):
                self.assertNotIn(gone, flat, f"{rel}: {gone}")
        for rel in ("skills/fde-scrum/SKILL.md", ".claude/skills/fde-scrum/SKILL.md"):
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
            self.assertIn("commit `plan.md` (`## Cycle` below), and stop at "
                          "the sign-off.", self.flat(rel), rel)
        self.assertIn("`plan.md` comes first (AGENTS.md `## Cycle`)",
                      " ".join(read("skills/fde-triage/SKILL.md").split()))

    def test_skills_point_to_the_section(self):
        for rel in ("skills/fde-triage/SKILL.md", "skills/fde-scrum/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-scrum/SKILL.md",
                    "skills/fde-status/SKILL.md",
                    ".claude/skills/fde-status/SKILL.md"):
            self.assertIn("AGENTS.md `## Cycle`", read(rel), rel)

    def test_scrum_captures_discoveries_as_found(self):
        for rel in ("skills/fde-scrum/SKILL.md", ".claude/skills/fde-scrum/SKILL.md"):
            text = " ".join(read(rel).split())
            self.assertNotIn("`## Next cycle`", text, rel)
            self.assertIn("enter `backlog.md` as they are found", text, rel)


class TestCycleTemplates(unittest.TestCase):
    """FWD-026, ADR-0019 rules 10-12: one skeleton per cycle file, carrying
    the header lines and sections the ADR names."""

    FILES = {
        "plan.md": ("cycle:", "state: draft", "date:", "size:",
                    "objective:", "signed-off:", "## Threat model",
                    "## Acceptance criteria", "## Failure modes",
                    "## Demands", "| id | layer | depends on | what | meets "
                    "| follows |"),
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


class TestGuardAuditDocs(unittest.TestCase):
    """FWD-006 R3: SETUP names the trail and the opt-in telemetry block."""

    def test_setup_documents_audit_file_and_otel_opt_in(self):
        setup = read("SETUP.md")
        self.assertIn("guard-audit.jsonl", setup)
        self.assertIn("CLAUDE_CODE_ENABLE_TELEMETRY", setup)
        self.assertIn("never enable it unasked", setup)

    def test_kernel_gitignores_its_own_audit_trail(self):
        self.assertIn(".fde/guard-audit.jsonl", read(".gitignore"))


class TestRolesAtTheRightLevel(unittest.TestCase):
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


class TestReconcileText(unittest.TestCase):
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
        for rel in self.SURFACES + ("skills/fde-triage/SKILL.md",):
            self.assertIn("is not re-split at review", self.flat(rel), rel)
            self.assertIn("the cycle replans only if a criterion or an ADR "
                          "changes", self.flat(rel), rel)

    def test_one_round_count_everywhere(self):
        # F2 (and FWD-028 F3): ADR-0019 rule 12
        for rel in self.SURFACES:
            text = self.flat(rel)
            self.assertIn("Size sets only the planner's depth and the cycle "
                          "review rounds: 1 round at XS/S, full + delta at "
                          "M/L.", text, rel)
            self.assertIn("a demand review is 1 round", text, rel)
            for gone in ("3 rounds", "all six roles"):
                self.assertNotIn(gone, text, f"{rel}: {gone}")
        triage = self.flat("skills/fde-triage/SKILL.md")
        self.assertIn("a demand review is 1 round", triage)
        # the old role-list row; "all five roles" at M/L stays (FWD-032 #3/#5)
        for gone in ("1 full + 2 delta", "| L | all five |"):
            self.assertNotIn(gone, triage, gone)

    def test_every_size_has_a_plan_and_a_promotion(self):
        # F3: ADR-0019 rules 3 and 4
        for rel in self.SURFACES:
            text = self.flat(rel)
            self.assertIn("At every size `fde-spec` writes `plan.md` "
                          "(minimal at XS)", text, rel)
            self.assertIn("the cycle closes with a promotion", text, rel)
            self.assertIn("promotion, at every size, is `fde-promotion`'s "
                          "decision", text, rel)
            self.assertNotIn("promotion (M/L)", text, rel)
        self.assertIn("Every size: `fde-spec` writes `plan.md`, a demand "
                      "review is 1 round, and the cycle closes with a "
                      "promotion by `fde-promotion`.",
                      self.flat("skills/fde-triage/SKILL.md"))

    def test_state_has_named_writers(self):
        # F4: who moves state:, and the only edits a frozen plan takes
        rule = ("`fde-spec` writes `state: draft` and `state: planned`; the "
                "orchestrating agent writes `state: running` at sign-off and "
                "`state: closed` or `state: abandoned` at close. These header "
                "lines are the only edits a frozen plan takes.")
        for rel in self.SURFACES:
            self.assertIn(rule, " ".join(section(read(rel), "Cycle").split()),
                          rel)
        plan = self.flat("templates/cycle/plan.md")
        self.assertIn("draft and planned are written by fde-spec; running, "
                      "closed and abandoned by the orchestrating agent", plan)

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


if __name__ == "__main__":
    unittest.main()
