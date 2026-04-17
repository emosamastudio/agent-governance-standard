#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _maintenance_common import run_executable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the shared project drift check.")
    parser.add_argument("--project", help="Optional project path. Defaults to cwd.")
    parser.add_argument(
        "--adapter",
        choices=("shared", "claude-code", "copilot-cli"),
        default="shared",
        help="Use the shared drift check, or the Claude wrapper when requested.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = Path(args.project).expanduser().resolve() if args.project else Path.cwd()
    candidates = []
    if args.adapter == "claude-code":
        candidates.append(project / ".claude" / "bin" / "drift-check")
    candidates.append(project / ".agent-governance" / "bin" / "drift-check")

    for path in candidates:
        if path.exists():
            return run_executable(path, [], cwd=project)

    print(f"MISSING_SCRIPT: no drift check found under {project}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
