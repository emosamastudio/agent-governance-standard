#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def state_incomplete(path: Path) -> bool:
    return not path.exists() or "<fill-me>" in path.read_text()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cwd = Path(payload.get("cwd") or ".").resolve()
    delivery_path = cwd / ".agent-governance" / "state" / "delivery-intent.md"
    mainline_path = cwd / ".agent-governance" / "state" / "current-mainline.md"
    workflow_path = cwd / ".agent-governance" / "state" / "git-workflow.md"

    if state_incomplete(delivery_path):
        print(
            "Delegation blocked: .agent-governance/state/delivery-intent.md is incomplete. "
            "Confirm with the user whether this work targets a final-system build or a fast MVP before planning or delegation.",
            file=sys.stderr,
        )
        return 2

    if state_incomplete(mainline_path):
        print(
            "Delegation blocked: .agent-governance/state/current-mainline.md is incomplete. "
            "Finish the mainline definition before creating tasks or subagent work.",
            file=sys.stderr,
        )
        return 2

    if state_incomplete(workflow_path):
        print(
            "Delegation blocked: .agent-governance/state/git-workflow.md is incomplete. "
            "Define the branch, push, PR, and merge workflow before parallel delegation.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
