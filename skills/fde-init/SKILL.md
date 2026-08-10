---
name: fde-init
description: Sets a project up under the FDE kernel — you, the agent, are the installer; detect the stack, interview only what files cannot tell, write fde.config.toml, install the gate runtime, and emit the native layer for your own tool. Use whenever the user asks to adopt, install, set up, or configure the kernel (or "forward") in a repository, or asks to build something in a repo that has no fde.config.toml yet.
---

# fde-init

The installer is `SETUP.md` at the kernel root, and its runtime is you.

1. **Locate the kernel — do not clone it into the project.**
   - Running as an installed plugin: the kernel IS the plugin, at
     `${CLAUDE_PLUGIN_ROOT}`. Use it. Nothing to download, and
     `/plugin update forward@forward` is what keeps it current.
   - Otherwise: clone it **outside the project directory**
     (`git clone https://github.com/dascbh/forward.git ../forward`, or
     anywhere that is not the project tree). A kernel cloned *inside* the
     project poisons step 1 of SETUP — stack detection would read the
     kernel's own files and describe the wrong repository.
   - Either way, note the absolute path once; every "copy from the kernel"
     instruction in SETUP means that path.
2. Open the kernel's `SETUP.md` and execute it top to bottom. Do not
   reorder or skip steps — detection before interview, config before
   structure, runtime before native layer, verification last.
3. Your work is audited by `python3 bin/fde/verify.py --all` (step 9). The
   gate validates the config you wrote (budget = 100, floors, escalated
   security floor) and the structure you created. On a fresh install,
   I2/I4/I5 red is designed — do not fabricate artifacts to silence them.

Runs once per project; afterwards use `fde-sync` to regenerate.

## What NOT to do

Do not offer to turn off a gate, relax a floor, or skip a step to "move
faster at the start". The scope shrinks; the standard does not. If the user
finds the process heavy, show `fde-triage` — the legitimate path to reduce
ceremony is sizing the demand, not relaxing the criteria.
