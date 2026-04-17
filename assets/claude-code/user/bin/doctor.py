#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
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
REQUIRED_PROJECT_HOOK_FILES = {
    "compact-gate.py",
    "completion-gate.py",
    "config-change-gate.py",
    "git-governance.py",
    "guard-tool-use.py",
    "log-event.py",
    "permission-request-gate.py",
    "postcompact-context.py",
    "prompt-submit-gate.py",
    "session-start.py",
    "task-created-gate.py",
}
REQUIRED_PERMISSION_DENIES = (
    "Bash(rm -rf *)",
    "Bash(git reset --hard *)",
    "Bash(git checkout -- *)",
    "Bash(killall *)",
    "Bash(pkill *)",
    "Bash(truncate *)",
)
WRAPPER_SNIPPETS = {
    "claude-governed": (
        'exec claude --append-system-prompt-file "$ROOT/.agent-governance-standard/user/top-level-constraints.md" "$@"',
    ),
    "claude-governance-doctor": (
        'exec python3 "$ROOT/.agent-governance-standard/claude-code/bin/doctor.py" "$@"',
    ),
    "claude-governance-uninstall": (
        'exec python3 "$ROOT/.agent-governance-standard/claude-code/bin/uninstall.py" "$@"',
    ),
}


def read_text(path: Path, issues: list[str]) -> str:
    try:
        return path.read_text()
    except OSError as exc:
        issues.append(f"Unable to read {path}: {exc}")
        return ""


def load_json(path: Path, issues: list[str]) -> dict:
    if not path.exists():
        issues.append(f"Missing JSON file: {path}")
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        issues.append(f"Invalid JSON in {path}: {exc}")
        return {}


def commands_for_event(settings: dict, event: str) -> set[str]:
    commands: set[str] = set()
    hooks = settings.get("hooks", {}).get(event, [])
    for entry in hooks:
        for hook in entry.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str):
                commands.add(command)
    return commands


def hook_files_from_settings(settings: dict) -> set[str]:
    files: set[str] = set()
    for entries in settings.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = hook.get("command")
                if not isinstance(command, str) or ".claude/hooks/" not in command:
                    continue
                suffix = command.split(".claude/hooks/", 1)[1].strip()
                name = suffix.split()[0].strip("\"'")
                if name:
                    files.add(name)
    return files


def check_wrapper(path: Path, snippets: tuple[str, ...], issues: list[str]) -> None:
    if not path.exists() or not os.access(path, os.X_OK):
        issues.append(f"Missing executable: {path}")
        return
    text = read_text(path, issues)
    for snippet in snippets:
        if snippet not in text:
            issues.append(f"Wrapper drift in {path}: missing snippet {snippet}")


def summarize_output(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return "; ".join(lines[:8]) if lines else "no output"


def run_drift_check(script: Path, project: Path, issues: list[str]) -> None:
    try:
        result = subprocess.run(
            [str(script)],
            cwd=str(project),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        issues.append(f"Unable to run drift check {script}: {exc}")
        return
    if result.returncode != 0:
        combined = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        issues.append(f"Project drift check failed via {script}: {summarize_output(combined)}")


def check_user(home: Path, issues: list[str]) -> None:
    standard_home = home / ".agent-governance-standard"
    claude_home = home / ".claude"
    claude_md = claude_home / "CLAUDE.md"
    settings_path = claude_home / "settings.json"
    adapter_home = standard_home / "claude-code" / "bin"

    if not standard_home.exists():
        issues.append(f"Missing shared install home: {standard_home}")
    top_level = standard_home / "user" / "top-level-constraints.md"
    if not top_level.exists():
        issues.append(f"Missing shared constraint file: {top_level}")
    for rel in ("doctor.py", "uninstall.py"):
        target = adapter_home / rel
        if not target.exists():
            issues.append(f"Missing adapter file: {target}")

    claude_text = read_text(claude_md, issues) if claude_md.exists() else ""
    if not claude_md.exists() or MANAGED_START not in claude_text:
        issues.append(f"Missing managed Claude block in {claude_md}")
    else:
        for snippet in (
            "Prefer the `claude-governed` wrapper",
            "treat it as the shared governance surface",
        ):
            if snippet not in claude_text:
                issues.append(f"Managed Claude guidance drift in {claude_md}: missing snippet {snippet}")

    settings = load_json(settings_path, issues)
    if settings.get("disableAllHooks") is True:
        issues.append(f"disableAllHooks must not be true in {settings_path}")
    if settings.get("defaultMode") != "plan":
        issues.append(f"defaultMode should be 'plan' in {settings_path}")
    if settings.get("env", {}).get("AGENT_GOVERNANCE_STANDARD") != "1":
        issues.append(f"Missing AGENT_GOVERNANCE_STANDARD env in {settings_path}")

    denies = settings.get("permissions", {}).get("deny", [])
    for rule in REQUIRED_PERMISSION_DENIES:
        if rule not in denies:
            issues.append(f"Missing deny permission {rule} in {settings_path}")

    wrapper_dir = claude_home / "bin"
    for name, snippets in WRAPPER_SNIPPETS.items():
        check_wrapper(wrapper_dir / name, snippets, issues)


def check_project(project: Path, issues: list[str]) -> None:
    claude_md = project / "CLAUDE.md"
    settings_path = project / ".claude" / "settings.json"
    state_dir = project / ".agent-governance" / "state"
    hook_dir = project / ".claude" / "hooks"
    local_drift = project / ".claude" / "bin" / "drift-check"
    shared_drift = project / ".agent-governance" / "bin" / "drift-check"

    claude_text = read_text(claude_md, issues) if claude_md.exists() else ""
    if not claude_md.exists() or MANAGED_START not in claude_text:
        issues.append(f"Missing managed Claude block in {claude_md}")

    settings = load_json(settings_path, issues)
    if settings.get("disableAllHooks") is True:
        issues.append(f"disableAllHooks must not be true in {settings_path}")

    for hook_name in REQUIRED_PROJECT_HOOK_FILES | hook_files_from_settings(settings):
        if not (hook_dir / hook_name).exists():
            issues.append(f"Missing hook file: {hook_dir / hook_name}")

    for event, hook_names in REQUIRED_PROJECT_HOOKS.items():
        commands = commands_for_event(settings, event)
        for hook_name in hook_names:
            if not any(hook_name in command for command in commands):
                issues.append(f"Missing hook {hook_name} under {event} in {settings_path}")

    for rel in ("delivery-intent.md", "current-mainline.md", "git-workflow.md"):
        if not (state_dir / rel).exists():
            issues.append(f"Missing state file: {state_dir / rel}")

    if not shared_drift.exists() or not os.access(shared_drift, os.X_OK):
        issues.append(f"Missing executable: {shared_drift}")
    if not local_drift.exists() or not os.access(local_drift, os.X_OK):
        issues.append(f"Missing executable: {local_drift}")
    else:
        drift_text = read_text(local_drift, issues)
        if 'project / ".agent-governance" / "bin" / "drift-check"' not in drift_text:
            issues.append(f"Claude drift wrapper does not delegate to shared drift check: {local_drift}")

    if shared_drift.exists() and os.access(shared_drift, os.X_OK):
        run_drift_check(shared_drift, project, issues)
    elif local_drift.exists() and os.access(local_drift, os.X_OK):
        run_drift_check(local_drift, project, issues)


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
