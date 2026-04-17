#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_PREFIXES = (
    "plan:",
    "arch:",
    "feat:",
    "fix:",
    "refactor:",
    "test:",
    "review:",
    "docs:",
    "chore:",
    "merge:",
)
PROTECTED_BRANCHES = {"main", "master"}
BRANCH_PATTERN = re.compile(r"^(feat|fix|refactor|chore|research|review|hotfix)/[a-z0-9._-]+$")


def current_branch(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def workflow_incomplete(path: Path) -> bool:
    return not path.exists() or "<fill-me>" in path.read_text()


def block(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command") or ""
    if not isinstance(command, str) or not command.startswith("git "):
        return 0

    cwd = Path(payload.get("cwd") or ".").resolve()
    workflow_path = cwd / ".agent-governance" / "state" / "git-workflow.md"
    branch = current_branch(cwd)

    if command.startswith("git push") or command.startswith("git merge"):
        if workflow_incomplete(workflow_path):
            return block(
                "Git governance blocked: .agent-governance/state/git-workflow.md is incomplete. "
                "Define protected branches, push policy, PR policy, and merge policy before push or merge."
            )

    if command.startswith("git push") and branch in PROTECTED_BRANCHES:
        return block(f"Git governance blocked: direct push from protected branch '{branch}' is not allowed.")

    if command.startswith("git merge") and branch in PROTECTED_BRANCHES:
        return block(f"Git governance blocked: merging while checked out on protected branch '{branch}' is not allowed.")

    if command.startswith("git commit -m"):
        match = re.search(r"git commit -m\s+[\"']([^\"']+)", command)
        if match:
            message = match.group(1).strip()
            if not any(message.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                return block(
                    "Git governance blocked: commit message must start with one of "
                    + ", ".join(ALLOWED_PREFIXES)
                )

    if (command.startswith("git commit") or command.startswith("git push")) and branch and branch not in PROTECTED_BRANCHES:
        if not BRANCH_PATTERN.match(branch):
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Git governance warning only",
                    "additionalContext": (
                        "Git governance warning: current branch does not match the standard branch pattern "
                        "`feat/*`, `fix/*`, `refactor/*`, `chore/*`, `research/*`, `review/*`, or `hotfix/*`."
                    ),
                }
            }
            print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
