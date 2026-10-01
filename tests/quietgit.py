"""Git's background maintenance off for every repository the suite creates.

Git 2.47+ runs `git maintenance run --auto --detach` after a commit. On a
loaded machine that detached process still writes .git/objects when a test
removes its temporary repository, and the cleanup fails with "Directory not
empty" — a different test each run. Setting the keys through GIT_CONFIG_*
applies them to every git the suite spawns and to nothing else: the
owner's own git configuration is untouched. Imported for its side effect.
"""
from __future__ import annotations

import os

QUIET = {"maintenance.auto": "false", "gc.auto": "0"}


def apply(env=os.environ) -> None:
    count = int(env.get("GIT_CONFIG_COUNT", "0") or 0)
    have = {env.get(f"GIT_CONFIG_KEY_{i}") for i in range(count)}
    for key, value in QUIET.items():
        if key in have:
            continue
        env[f"GIT_CONFIG_KEY_{count}"] = key
        env[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)


apply()
