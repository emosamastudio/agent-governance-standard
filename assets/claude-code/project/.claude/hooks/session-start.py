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


def count_open_items(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip().startswith("- [ ]"))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cwd = Path(payload.get("cwd") or ".").resolve()
    state_dir = cwd / ".agent-governance" / "state"
    delivery_path = state_dir / "delivery-intent.md"
    mainline_path = state_dir / "current-mainline.md"
    sidelines_path = state_dir / "sidelines.md"
    workflow_path = state_dir / "git-workflow.md"

    delivery_mode = read_section_value(delivery_path, "Mode")
    objective = read_section_value(mainline_path, "Objective")
    phase = read_section_value(mainline_path, "Current Phase")
    active_branch = read_section_value(workflow_path, "Active Branch")
    target_branch = read_section_value(workflow_path, "Target Integration Branch")
    open_sidelines = count_open_items(sidelines_path)

    print("Governance startup context:")
    print(f"- delivery mode: {delivery_mode}")
    print(f"- mainline objective: {objective}")
    print(f"- current phase: {phase}")
    print(f"- active branch: {active_branch}")
    print(f"- target integration branch: {target_branch}")
    print(f"- open sideline items: {open_sidelines}")
    print("- reminders: confirm delivery intent early, protect the mainline, plan before parallel execution, and keep git workflow governed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
