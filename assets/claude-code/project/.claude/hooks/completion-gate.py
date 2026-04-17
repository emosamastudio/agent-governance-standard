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
    state_dir = cwd / ".agent-governance" / "state"
    required = {
        "delivery intent": state_dir / "delivery-intent.md",
        "mainline": state_dir / "current-mainline.md",
        "git workflow": state_dir / "git-workflow.md",
    }
    missing = [name for name, path in required.items() if state_incomplete(path)]
    if missing:
        print(
            "Completion blocked: governance state is incomplete for " + ", ".join(missing) + ". "
            "Refresh the shared state and pass .claude/bin/drift-check before claiming completion.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
