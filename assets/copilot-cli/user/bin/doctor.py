#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

MANAGED_START = "<!-- agent-governance-standard:start -->"
REQUIRED_PROJECT_FILES = (
    ".github/copilot-instructions.md",
    ".github/instructions/00-governance.instructions.md",
    ".github/instructions/10-planning.instructions.md",
    ".github/instructions/20-git.instructions.md",
    ".github/instructions/30-delegation.instructions.md",
    ".github/instructions/40-review.instructions.md",
    ".agent-governance/state/delivery-intent.md",
    ".agent-governance/state/current-mainline.md",
    ".agent-governance/state/git-workflow.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Agent Governance Standard Copilot install health.")
    parser.add_argument("--home", help="Override HOME for testing.")
    parser.add_argument("--project", help="Optional project path to validate.")
    return parser.parse_args()


def detect_home() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    args = parse_args()
    home = Path(args.home).expanduser().resolve() if args.home else detect_home()
    issues: list[str] = []

    global_file = home / ".copilot" / "copilot-instructions.md"
    if not global_file.exists() or MANAGED_START not in global_file.read_text():
        issues.append(f"Missing managed Copilot block in {global_file}")

    for rel in ("bin/copilot-governed", "bin/copilot-governance-doctor", "bin/copilot-governance-uninstall"):
        path = home / ".copilot" / rel
        if not path.exists() or not os.access(path, os.X_OK):
            issues.append(f"Missing executable: {path}")

    if args.project:
        project = Path(args.project).expanduser().resolve()
        for rel in REQUIRED_PROJECT_FILES:
            path = project / rel
            if not path.exists():
                issues.append(f"Missing project file: {path}")
        repo_file = project / ".github" / "copilot-instructions.md"
        if repo_file.exists() and MANAGED_START not in repo_file.read_text():
            issues.append(f"Missing managed Copilot block in {repo_file}")

    if issues:
        print("COPILOT_GOVERNANCE_DOCTOR_FAILED")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("COPILOT_GOVERNANCE_DOCTOR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
