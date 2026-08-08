---
name: fde-init
description: Parameterizes a project under the FDE kernel — detects the stack, interviews only what detection cannot resolve, allocates the weight vector, and compiles the native artifacts for the tool in use. Use whenever the user is starting a new project, adopting the kernel in an existing repository, or mentions "setup", "bootstrap", "parameterize", "adopt the standard", "clone the framework". Also use when the user asks to build something (a platform, service, agent) in a repository that does not yet have fde.config.toml.
---

# fde-init

Parameterizes the project. Runs once; after that use `fde-sync`.

## Mandatory order

1. **Detect, don't ask.** `python bin/detect_stack.py` resolves language, runner, frontend, database, API, CI, IaC, and AI libraries from files in the repository. Asking for what can be inferred produces worse answers than the inference.

2. **Confirm as a block.** Show everything that was detected at once and ask for a single confirmation. Never one question per item.

3. **Interview only the unresolved.** Three things are not inferable from files and change the floor: the most sensitive data class, the reversibility of a production mistake, and whether there is an agent loop. Ask those and nothing else.

4. **Allocate vector A with the user.** Closed budget of 100 points across the eight quality attributes. The `init` default is a starting point, not a neutral recommendation — the user moves it. Explain what weight does: it orders the adversarial attack, sizes the suite, and decides what blocks merge above the floor.

5. **Do not negotiate vector B.** Technical domain depth is derived from the stack + triage. If the user wants to reduce it, explain that override is upward-only: low weight on data modeling in a data-heavy system is not a preference, it is an error.

6. **Compile.** `python bin/compile.py`.

## Command

```bash
python bin/init.py                    # interactive
python bin/init.py --yes \
  --data-class personal \
  --reversibility irreversible        # CI / non-interactive
python bin/compile.py
git config core.hooksPath .githooks
```

## What NOT to do

Do not offer to turn off a gate, relax a floor, or skip a step to "move faster at the start". The scope shrinks; the standard does not. If the user insists, show `fde-triage` — the legitimate path to reduce ceremony is sizing the demand, not relaxing the criteria.
