#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

MANAGED_START = "<!-- agent-governance-standard:start -->"
MANAGED_END = "<!-- agent-governance-standard:end -->"

USER_TEMPLATE = {
    "model": "claude-sonnet-4-6",
    "defaultMode": "plan",
    "autoMemoryEnabled": True,
    "disableAllHooks": False,
    "permissions": {
        "deny": [
            "Bash(rm -rf *)",
            "Bash(git reset --hard *)",
            "Bash(git checkout -- *)",
            "Bash(killall *)",
            "Bash(pkill *)",
            "Bash(truncate *)",
        ]
    },
    "env": {"AGENT_GOVERNANCE_STANDARD": "1"},
}


def remove_managed_block(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text()
    if MANAGED_START not in text or MANAGED_END not in text:
        return
    prefix = text.split(MANAGED_START, 1)[0].rstrip()
    suffix = text.split(MANAGED_END, 1)[1].lstrip("\n")
    updated = prefix
    if prefix and suffix:
        updated += "\n\n"
    updated += suffix
    updated = updated.rstrip() + ("\n" if updated.strip() else "")
    path.write_text(updated)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")


def prune_template_values(data: dict, template: dict) -> dict:
    for key, value in template.items():
        if key not in data:
            continue
        if isinstance(value, dict) and isinstance(data[key], dict):
            prune_template_values(data[key], value)
            if not data[key]:
                del data[key]
        elif isinstance(value, list) and isinstance(data[key], list):
            data[key] = [item for item in data[key] if item not in value]
            if not data[key]:
                del data[key]
        elif data[key] == value:
            del data[key]
    return data


def prune_project_hooks(settings: dict) -> dict:
    hook_names = {
        "prompt-submit-gate.py",
        "permission-request-gate.py",
        "config-change-gate.py",
        "compact-gate.py",
        "postcompact-context.py",
        "completion-gate.py",
        "task-created-gate.py",
        "git-governance.py",
        "guard-tool-use.py",
        "log-event.py",
        "session-start.py",
    }
    hooks = settings.get("hooks", {})
    cleaned = {}
    for event, entries in hooks.items():
        kept_entries = []
        for entry in entries:
            kept_hooks = []
            for hook in entry.get("hooks", []):
                command = hook.get("command", "")
                if not any(name in command for name in hook_names):
                    kept_hooks.append(hook)
            if kept_hooks:
                new_entry = dict(entry)
                new_entry["hooks"] = kept_hooks
                kept_entries.append(new_entry)
        if kept_entries:
            cleaned[event] = kept_entries
    settings["hooks"] = cleaned
    return settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Uninstall Claude adapter pieces of Agent Governance Standard.")
    parser.add_argument("--project", help="Optional project path to clean.")
    parser.add_argument("--home", help="Override HOME for testing.")
    parser.add_argument("--remove-shared-home", action="store_true", help="Also remove ~/.agent-governance-standard.")
    return parser.parse_args()


def detect_home() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    args = parse_args()
    home = Path(args.home).expanduser().resolve() if args.home else detect_home()
    claude_home = home / ".claude"
    remove_managed_block(claude_home / "CLAUDE.md")
    settings_path = claude_home / "settings.json"
    settings = load_json(settings_path)
    if settings:
        save_json(settings_path, prune_template_values(settings, USER_TEMPLATE))
    for rel in ("bin/claude-governed", "bin/claude-governance-doctor", "bin/claude-governance-uninstall"):
        path = claude_home / rel
        if path.exists():
            path.unlink()

    standard_home = home / ".agent-governance-standard"
    claude_tools = standard_home / "claude-code"
    if claude_tools.exists():
        shutil.rmtree(claude_tools)
    if args.remove_shared_home and standard_home.exists():
        shutil.rmtree(standard_home)

    if args.project:
        project = Path(args.project).expanduser().resolve()
        remove_managed_block(project / "CLAUDE.md")
        project_settings_path = project / ".claude" / "settings.json"
        project_settings = load_json(project_settings_path)
        if project_settings:
            save_json(project_settings_path, prune_project_hooks(project_settings))
        for path in (
            project / ".claude" / "hooks",
            project / ".claude" / "bin" / "drift-check",
        ):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()

    print("CLAUDE_GOVERNANCE_UNINSTALL_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
