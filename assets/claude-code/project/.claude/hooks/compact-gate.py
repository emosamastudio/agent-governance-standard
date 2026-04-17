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
    if state_incomplete(state_dir / "delivery-intent.md") or state_incomplete(state_dir / "current-mainline.md"):
        print(
            "Compaction blocked: delivery intent and current mainline must be explicit before context compaction.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
