# FWD-036 — review by weight

cycle: C-13 · layer: back · meets: A1, A2, A3, A4, A5 · follows: ADR-0021

AGENTS.md step 5 (and the template), fde-review and agents/fde-adversarial.md (and its rendered copy) state one rule: a coding demand inside a signed-off plan gets an isolated code review (diff × demand spec, ADR conformance, tests, the layer's check; `kind = "code"`, ~10 min); a sensitive or irreversible demand, or one whose real diff overruns ~300 production lines, gets adversarial review; an M/L cycle's plan gets an adversarial plan review before sign-off (`kind = "plan"`); the cycle review is unchanged. The findings template carries `kind`. A `kind = "code"` record passes the gate. AGENTS.md ≤ 1,600 words.
