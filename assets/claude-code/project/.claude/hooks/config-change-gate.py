#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_EVENT_HOOKS = {
    "UserPromptSubmit": ("prompt-submit-gate.py",),
    "PermissionRequest": ("permission-request-gate.py",),
    "ConfigChange": ("config-change-gate.py",),
    "PreCompact": ("compact-gate.py",),
    "Stop": ("completion-gate.py",),
    "TaskCompleted": ("completion-gate.py",),
    "TaskCreated": ("task-created-gate.py",),
    "SubagentStop": ("completion-gate.py",),
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def commands_for_event(settings: dict, event: str) -> set[str]:
    commands: set[str] = set()
    for entry in settings.get("hooks", {}).get(event, []):
        for hook in entry.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str):
                commands.add(command)
    return commands


def block(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cwd = Path(payload.get("cwd") or ".").resolve()
    settings_path = cwd / ".claude" / "settings.json"
    settings = load_json(settings_path)
    if settings.get("disableAllHooks") is True:
        return block("Config change blocked: .claude/settings.json must not set disableAllHooks=true.")
    for event, required in REQUIRED_EVENT_HOOKS.items():
        commands = commands_for_event(settings, event)
        for hook_name in required:
            if not any(hook_name in command for command in commands):
                return block(f"Config change blocked: missing required hook {hook_name} under event {event}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
