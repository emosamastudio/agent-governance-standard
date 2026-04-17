#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _maintenance_common import detect_home, standard_home


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show Agent Governance maintenance status.")
    parser.add_argument("--home", help="Override HOME for testing.")
    parser.add_argument("--project", help="Optional project path to inspect.")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=("claude-code", "copilot-cli"),
        help="Limit status to one adapter. Repeat for multiple adapters.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    home = detect_home(Path(__file__), args.home)
    installer = standard_home(home) / "install.py"
    forwarded = ["status", "--home", str(home)]
    if args.project:
        forwarded.extend(["--project", str(Path(args.project).expanduser().resolve())])
    for adapter in args.adapter or []:
        forwarded.extend(["--adapter", adapter])
    if args.json_output:
        forwarded.append("--json")
    result = subprocess.run([sys.executable, str(installer), *forwarded], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
