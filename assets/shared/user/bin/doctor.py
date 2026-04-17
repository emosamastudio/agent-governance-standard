#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _maintenance_common import adapter_script, detect_home, print_section, run_python_script, select_adapters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run adapter governance doctors through one shared command.")
    parser.add_argument("--home", help="Override HOME for testing.")
    parser.add_argument("--project", help="Optional project path to validate.")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=("claude-code", "copilot-cli"),
        help="Limit doctor to one adapter. Repeat for multiple adapters.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    home = detect_home(Path(__file__), args.home)
    adapters = select_adapters(home, args.adapter)
    forwarded: list[str] = []
    if args.home:
        forwarded.extend(["--home", str(home)])
    if args.project:
        forwarded.extend(["--project", str(Path(args.project).expanduser().resolve())])

    overall = 0
    for index, adapter in enumerate(adapters):
        if index:
            print()
        print_section(f"{adapter} doctor")
        overall = max(overall, run_python_script(adapter_script(home, adapter, "doctor.py"), forwarded))
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
