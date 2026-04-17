#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def read_section_value(path: Path, header: str) -> str:
    if not path.exists():
        return "missing"
    text = path.read_text()
    marker = f"## {header}"
    if marker not in text:
        return "missing"
    after = text.split(marker, 1)[1].strip()
    if not after:
        return "empty"
    value = after.splitlines()[0].strip()
    return value or "empty"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cwd = Path(payload.get("cwd") or ".").resolve()
    state_dir = cwd / ".agent-governance" / "state"
    print("Governance post-compact context:")
    print(f"- delivery mode: {read_section_value(state_dir / 'delivery-intent.md', 'Mode')}")
    print(f"- mainline objective: {read_section_value(state_dir / 'current-mainline.md', 'Objective')}")
    print(f"- execution frontier: {read_section_value(state_dir / 'current-mainline.md', 'Current Execution Frontier')}")
    print(f"- target branch: {read_section_value(state_dir / 'git-workflow.md', 'Target Integration Branch')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
