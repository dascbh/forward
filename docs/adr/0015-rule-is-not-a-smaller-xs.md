# ADR-0015 — RULE is not a smaller XS

date: 2026-08-25
status: accepted

## Context

`fde-triage`'s table has no floor below XS. The formula
(`score = min(3, surfaces) + (sensitive?2:0) + (irreversible?2:0) +
loc-bucket`) bottoms out at 0, and `score ≤ 1 → XS` already spends a
full isolated adversarial round: a fresh subagent, its own git
worktree, an attack order derived from vector A, a written
`findings.toml`. A one-line label fix pays that entire bill. The skill
promises to "reduce ceremony without relaxing criteria"
(`skills/fde-triage/SKILL.md:3`); the table cannot keep that promise
for the genuinely trivial case, because XS **is** the floor and XS is
already heavy. In the field this cost the project owner real velocity:
they moved a change to another tool rather than pay it.

**The research names this failure precisely.** Kahneman's *Thinking,
Fast and Slow* frames System 2 as a lazy controller — it mostly
rubber-stamps System 1's judgments and fully engages only on a
detected surprise or conflict encountered *during* the work, not on a
one-time classification made before any of it exists. `fde-triage`
today is entirely the second kind: an a-priori estimate that fixes the
ceremony level for a demand's whole life, with no re-check against
what the diff actually turned out to be.

Kahneman, Sibony, and Sunstein's *Noise: A Flaw in Human Judgment*
(2021) is more directly load-bearing. Its rule-vs-standard distinction:
a high-volume, low-stakes, repetitive decision should become a
**rule** — a deterministic checker decides, no judgment applied at
all — while deliberate, multi-perspective judgment is reserved for
what is genuinely risky or novel. This is a difference in *kind*, not
degree. It does not argue for a lighter judgment lane; it argues for
shrinking what enters the judgment lane in the first place, and for
keeping a live, mechanical "surprise/conflict" check on whatever a
rule decided, so a case that turns out to violate the rule's own
premise still surfaces.

**The kernel already declares the internal justification.**
`spec/dimensions/quality-attributes.toml` orders its three
verification pillars by primacy on every quality attribute:
`verified_by = ["empirical", "adversarial", "heuristic"]` —
execution first, demonstrated adversarial failure second, heuristic
judgment against a principle catalog last, reserved for what the
first two cannot reach. When empirical verification — I1's
`eval-coverage` gate — already covers everything there is to verify
for a given change, stacking adversarial and heuristic review on top
adds no information the primacy ordering did not already say was
unnecessary. That is ceremony wearing rigor's clothes, using the
kernel's own stated priorities against it.

`specs/FWD-019-rule-lane/spec.md` and `acceptance.md` (read in full)
work out the mechanical design this ADR records; that spec's
"Boundaries" and "Failure modes" sections are the operative detail
this ADR does not restate wholesale.

## Options considered

**A new tier vs. diluting XS itself.** Diluting XS — fewer adversarial
rounds, a cheaper isolation protocol, judgment applied more loosely —
was considered and rejected. *Noise* is explicit that the correct
lever is shrinking what gets *routed into* the judgment lane, never
weakening the judgment lane itself. XS is where genuinely small but
still-judged demands land; softening it degrades the adversarial
signal for every demand that lands there, including ones that
legitimately need full judgment in reduced form. The fix is a new,
categorically distinct floor beneath XS, not a thinner XS.

**A mechanical rule vs. an agent judgment call ("this looks
trivial").** Making the eligibility check itself a judgment — an
agent eyeballing a diff and deciding it looks safe — was considered
and rejected. That would relocate the exact ceremony/bias problem one
level up: instead of a fixed process being disproportionate to a
trivial change, a fallible, unaudited "looks fine to me" becomes the
gate for skipping process altogether. It defeats the entire
rule-vs-standard point, which depends on the rule containing zero
judgment, checkable by inspection rather than by trusting a claim.
RULE's eligibility function is therefore pure and mechanical: two
already-declared project-level config values, one commit's own
numstat, and `eval_paths` — nothing content-aware, nothing that reads
a diff's meaning, nothing that estimates before the commit exists.

**Skipping I1 for RULE-tier commits.** Considered as a real
temptation — if a change is small enough to skip adversarial and
heuristic review, why not skip the eval-coverage check too? — and
rejected firmly. I1 is a non-negotiable invariant with no configurable
key; nothing in this kernel is permitted to carry a key that turns one
off. More than that: RULE's entire legitimacy rests on I1 remaining
fully, unconditionally intact underneath it. RULE is not "this change
is small enough that nothing needs to verify it" — it is "empirical
verification (I1) already covers everything there is to verify for
this change, so nothing *else* needs to." Weaken I1 for RULE commits
and that sentence becomes false; RULE would stop being a recognition
of I1's sufficiency and become an exemption from it, the one thing
this design cannot become without contradicting its own justification.

**Where the project-level sensitive/irreversible axes get resolved.**
The spec's own investigation (`fde_lib.py` and `erosion.py` read in
full for that work) found no per-file sensitivity signal anywhere in
this codebase — only the two project-level `[triage]` values,
`data_class` and `reversibility`. A per-file heuristic (keyword
matching, path patterns) was available and rejected, for the same
reason as the semantic-detector option below: it substitutes judgment
for a rule. The accepted resolution checks both axes once, at the
project level, using FWD-003/ADR-0009's own established reading —
`data_class` as a ceiling (`public`/`internal` make `sensitive`
unconditionally false), `reversibility` read at its strictest exact
value (`reversible`) rather than attempting the exception clause a
specific diff would need content-level judgment to evaluate. Any
other declared value on either axis makes RULE unavailable for every
commit in that project, not just commits that touch risky-looking
files — where mechanical certainty is unavailable, RULE defaults to
never, the same conservative tiebreak ADR-0009 already established
for `sensitive`/`irreversible` at the demand level, applied here at
the project level instead.

**A semantic detector as a second layer of eligibility.** Keyword
matching on "security"/"auth"/"guard", AST inspection, or any other
content-aware heuristic layered onto the four mechanical criteria was
considered and rejected outright. This would smuggle a second,
weaker judgment layer into a lane whose entire premise is having
none — and a semantic detector is exactly the kind of check a small
adversarial diff is best at slipping past, replacing an honestly
named residual risk (below) with a false sense that it had been
closed.

## Decision

A new tier, **RULE**, categorically distinct from XS/S/M/L — never a
score bucket, never "XS with score 0." XS still runs full judgment in
reduced form (implementation, one isolated adversarial round); RULE
runs no judgment at all. It sits in its own paragraph immediately
before the existing score table and score-boundary sentence, in
`skills/fde-triage/SKILL.md`, `AGENTS.md`, and
`templates/AGENTS.md.template` — never as a row inside the table,
never altering a byte of the existing XS/S/M/L text.

**Eligibility is computed, never estimated, and always after the
fact**, against one commit's actual diff:

1. `[triage].data_class` is exactly `public` or `internal`.
2. `[triage].reversibility` is exactly `reversible`.
3. The commit's own `added + deleted` (its numstat) is strictly under
   the declared `[triage].rule_lane_max_loc` (default `10`).
4. No file under `[gate].eval_paths` was deleted or shrunk in that
   commit.

All four are mechanical: no keyword, path-content, or AST inspection
anywhere in the check. A commit self-declares RULE by convention —
first message line matching `FORWARD: RULE — <one-line reason>`, the
same announcement discipline the standard table already uses for its
own sizes. A new gate, `gate_rule_lane`, re-verifies every such claim
against what was **actually committed**, per commit, never against
the aggregate diff of a bundled push and never against the message's
own claim. This is the live surprise/conflict monitor the research
calls for, made deterministic and always-on rather than a fallible
human noticing something felt off: a commit that turns out bigger,
riskier, or different in kind than its self-declaration is caught
mechanically and blocked, with the fallback instruction to run the
demand through the normal table.

**I1 is completely unchanged.** `gate_eval_coverage` gains zero lines
in this demand's diff — enforced by direct inspection and by the
demand's own acceptance criteria. RULE is not an exemption from I1;
it is the recognition that when I1 already covers everything there is
to verify for a change this small and this bounded, adversarial and
heuristic review on top of it verify nothing further. The `verified_by`
primacy ordering this kernel already declares is the reasoning, not a
new one invented for this decision.

## Consequences

**What this closes.** The genuinely trivial case — a label, a typo, a
comment, a version bump, a handful of lines with no sensitive or
irreversible surface — stops paying the price of a full isolated
adversarial round. The cheapest path inside the process becomes
cheaper than leaving the process, closing the exact gap that pushed a
real user elsewhere.

**What this does not touch.** No invariant changes; I1 through I8 all
apply exactly as before. XS/S/M/L, the adversarial protocol, and the
isolation mechanism are byte-identical to what they were — the
rejected alternative (diluting XS) stays rejected, and this ADR is
the record that closes it, not merely a place it was mentioned once. A
project whose `data_class`/`reversibility` do not clear the strict
project-level check gets no RULE lane at all, regardless of how small
any individual commit is — intentional, not a gap to fix later.

**The honest, named risk.** RULE's real danger is a false positive: a
diff that mechanically looks small and safe — few lines, no
sensitive/irreversible path, no shrunk eval coverage — while hiding a
disproportionate semantic change. A one-character flip in a security
comparison, a sign flip in a financial calculation, a widened default:
none of these announce themselves in a numstat. No threshold value
closes this gap, including one far below the chosen default — a
flipped comparison operator is two lines of churn, so `rule_lane_max_
loc = 1` would not stop the paradigm case either. The live
re-verification gate mitigates this by checking the actual commit
rather than trusting the claim, and I1 independently still requires
an eval entry for anything under `behavior_paths` regardless of the
RULE tag — but a mechanical loc/path check cannot see semantic risk,
full stop. This is stated the way ADR-0013 named "no real UI to test
against here" and ADR-0011 named "a partial datapoint, not proof": an
honest, permanent limit of the mechanism, not a problem this design
claims to have solved. It is the isolated adversarial round's specific
probe for this demand, not a question this ADR answers for itself.

**The asymmetry that makes the default conservative safe.** A false
negative — something genuinely trivial fails to qualify and runs
through the full XS/S/M/L table by mistake — costs time, nothing else.
It is why every project-level check defaults to "unavailable" rather
than "probably fine" whenever mechanical certainty is not available,
and why the chosen `rule_lane_max_loc = 10` errs toward a smaller
number than a larger one: there is no safety argument for raising it
past the motivating case's actual needs, only a usability cost to
setting it too low. The design accepts real, ongoing cost on the safe
side of the asymmetry in exchange for closing the unsafe side as far
as a mechanical check can close it.

## Amendment — 2026-08-25 (FWD-019 F13)

The isolated adversarial round's fifth pass (`reviews/FWD-019/findings.toml`,
round 5, F13, `functional_correctness`, non-blocking) found that R6 — this
ADR's own "I1 is completely unchanged" clause, carried into
`specs/FWD-019-rule-lane/spec.md` as two MUST-level clauses — no longer
holds in full. Clause (a), "`gate_eval_coverage` MUST be unmodified...
zero lines added, removed, or reordered inside its body," still holds
exactly as written: round 4's F10 confirmed it byte-identical against
both round 2's own checkpoint and the demand's true pre-FWD-019 origin
point, and F13's own round-5 probe re-confirmed it independently. That
clause was, and remains, the load-bearing guardrail this ADR needed: the
one mechanical, inspection-verifiable line standing between this demand
and the temptation to casually touch FWD-017's already-hardened
`gate_eval_coverage` logic while building an unrelated tier underneath
it. Nothing here weakens or reopens that guarantee.

Clause (b), "nothing about `--gate eval`/`--gate eval-coverage`'s
behavior, output, or code path changes as a side effect of this demand,"
was a stronger claim than this demand could actually keep, and F13
demonstrated why directly, not by argument: the shared `_git`/
`_resolve_range` helper `gate_eval_coverage` reaches through `changed()`
became strict by default as round 3's own F9 fix — a genuine safety
correction, not scope creep, made independently of R6 and for reasons
that had nothing to do with it (a git spawn or invocation fault that used
to read as "nothing changed" and pass now correctly blocks). `gate_eval_
coverage`'s own body never moved a line to make that happen; it inherited
the safer behavior for free, precisely because clause (a) held. Reproduced
against the identical fault on both sides of the change: the pre-round-3
binary passes silently under a genuine `git diff` failure, the current one
blocks it. R6(b), read literally, was false the moment F9 landed in round
3 and has stayed false through every round since, including this one's
own HEAD — a fact no amount of code motion confined to "outside the
function's body" could have undone, since the violation lives in the
shared helper's behavior, not in `gate_eval_coverage` itself.

This is named here as what it is: the safety fix was correct, and the
prohibition, as originally written, was overbroad — not a violation this
amendment apologizes for, but a boundary that needed narrowing to match
what was actually true and desirable once F9's fix existed. A demand that
had kept clause (b) literal would have had to either revert F9's
hardening (reintroducing a real, already-demonstrated gap under FWD-017's
own logic) or fork the shared helper into a second, duplicate
implementation just to keep its old, less-safe behavior pinned in place
for `gate_eval_coverage` alone — both strictly worse than the outcome
that actually shipped.

**The corrected boundary, going forward.** `gate_eval_coverage`'s CODE —
its body, and its behavior on every path where the git operations it
depends on succeed — is unchanged and stays the guardrail clause (a)
always was. Its behavior specifically under a previously-unsafe
git-failure condition (a `changed()`-reachable git invocation failing
outright, as opposed to succeeding and returning a real diff) is now
correctly stricter than it was before FWD-019 existed — a feature of F9's
fix, inherited through the shared helper, not a scope violation of this
demand and not a thing future work needs to re-flag against R6.
`specs/FWD-019-rule-lane/spec.md`'s R6 and its "Boundaries → Never"
section are corrected in place, in the same change that adds this
amendment, to say this plainly and to agree with each other — that
correction is not append-only doctrine the way this ADR's own Decision
and Consequences sections above are, and is made directly in that file
rather than layered here.
