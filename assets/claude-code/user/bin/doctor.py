#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

MANAGED_START = "<!-- agent-governance-standard:start -->"
REQUIRED_PROJECT_HOOKS = {
    "UserPromptSubmit": ["prompt-submit-gate.py"],
    "PermissionRequest": ["permission-request-gate.py"],
    "ConfigChange": ["config-change-gate.py"],
    "PreCompact": ["compact-gate.py"],
    "Stop": ["completion-gate.py"],
    "TaskCompleted": ["completion-gate.py"],
    "TaskCreated": ["task-created-gate.py"],
    "SubagentStop": ["completion-gate.py"],
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def commands_for_event(settings: dict, event: str) -> set[str]:
    commands: set[str] = set()
    hooks = settings.get("hooks", {}).get(event, [])
    for entry in hooks:
        for hook in entry.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str):
                commands.add(command)
    return commands


def check_user(home: Path, issues: list[str]) -> None:
    standard_home = home / ".agent-governance-standard"
    claude_home = home / ".claude"
    claude_md = claude_home / "CLAUDE.md"
    settings_path = claude_home / "settings.json"
    wrapper = claude_home / "bin" / "claude-governed"
    doctor = claude_home / "bin" / "claude-governance-doctor"
    uninstall = claude_home / "bin" / "claude-governance-uninstall"

    if not standard_home.exists():
        issues.append(f"Missing shared install home: {standard_home}")
    if not claude_md.exists() or MANAGED_START not in claude_md.read_text():
        issues.append(f"Missing managed Claude block in {claude_md}")
    settings = load_json(settings_path)
    if settings.get("disableAllHooks") is True:
        issues.append(f"disableAllHooks must not be true in {settings_path}")
    if settings.get("defaultMode") != "plan":
        issues.append(f"defaultMode should be 'plan' in {settings_path}")
    if settings.get("env", {}).get("AGENT_GOVERNANCE_STANDARD") != "1":
        issues.append(f"Missing AGENT_GOVERNANCE_STANDARD env in {settings_path}")
    for path in (wrapper, doctor, uninstall):
        if not path.exists() or not os.access(path, os.X_OK):
            issues.append(f"Missing executable: {path}")


def check_project(project: Path, issues: list[str]) -> None:
    claude_md = project / "CLAUDE.md"
    settings_path = project / ".claude" / "settings.json"
    state_dir = project / ".agent-governance" / "state"
    if not claude_md.exists() or MANAGED_START not in claude_md.read_text():
        issues.append(f"Missing managed Claude block in {claude_md}")
    settings = load_json(settings_path)
    if settings.get("disableAllHooks") is True:
        issues.append(f"disableAllHooks must not be true in {settings_path}")
    for event, hook_names in REQUIRED_PROJECT_HOOKS.items():
        commands = commands_for_event(settings, event)
        for hook_name in hook_names:
            if not any(hook_name in command for command in commands):
                issues.append(f"Missing hook {hook_name} under {event} in {settings_path}")
    for rel in (
        "delivery-intent.md",
        "current-mainline.md",
        "git-workflow.md",
    ):
        if not (state_dir / rel).exists():
            issues.append(f"Missing state file: {state_dir / rel}")
    drift = project / ".claude" / "bin" / "drift-check"
    if not drift.exists() or not os.access(drift, os.X_OK):
        issues.append(f"Missing executable: {drift}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Agent Governance Standard Claude install health.")
    parser.add_argument("--project", help="Optional project path to validate.")
    parser.add_argument("--home", help="Override HOME for testing.")
    return parser.parse_args()


def detect_home() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    args = parse_args()
    home = Path(args.home).expanduser().resolve() if args.home else detect_home()
    issues: list[str] = []
    check_user(home, issues)
    if args.project:
        check_project(Path(args.project).expanduser().resolve(), issues)
    if issues:
        print("CLAUDE_GOVERNANCE_DOCTOR_FAILED")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("CLAUDE_GOVERNANCE_DOCTOR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
