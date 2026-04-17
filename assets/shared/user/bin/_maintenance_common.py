#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ADAPTERS = ("claude-code", "copilot-cli")
ADAPTER_WRAPPERS = {
    "claude-code": (
        "~/.claude/bin/claude-governed",
        "~/.claude/bin/claude-governance-doctor",
        "~/.claude/bin/claude-governance-status",
        "~/.claude/bin/claude-governance-drift",
        "~/.claude/bin/claude-governance-uninstall",
    ),
    "copilot-cli": (
        "~/.copilot/bin/copilot-governed",
        "~/.copilot/bin/copilot-governance-doctor",
        "~/.copilot/bin/copilot-governance-status",
        "~/.copilot/bin/copilot-governance-drift",
        "~/.copilot/bin/copilot-governance-uninstall",
    ),
}


def detect_home(script_path: Path, explicit_home: str | None) -> Path:
    if explicit_home:
        return Path(explicit_home).expanduser().resolve()
    return script_path.resolve().parents[3]


def standard_home(home: Path) -> Path:
    return home / ".agent-governance-standard"


def adapter_script(home: Path, adapter: str, name: str) -> Path:
    return standard_home(home) / adapter / "bin" / name


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def installed_adapters(home: Path) -> list[str]:
    present: list[str] = []
    for adapter in ADAPTERS:
        bin_dir = standard_home(home) / adapter / "bin"
        if bin_dir.exists():
            present.append(adapter)
    return present


def select_adapters(home: Path, requested: list[str] | None) -> list[str]:
    if requested:
        seen: set[str] = set()
        ordered: list[str] = []
        for adapter in requested:
            if adapter not in seen:
                ordered.append(adapter)
                seen.add(adapter)
        return ordered
    detected = installed_adapters(home)
    return detected or list(ADAPTERS)


def run_python_script(path: Path, forwarded_args: list[str]) -> int:
    if not path.exists():
        print(f"MISSING_SCRIPT: {path}")
        return 1
    result = subprocess.run([sys.executable, str(path), *forwarded_args], check=False)
    return result.returncode


def run_executable(path: Path, forwarded_args: list[str], cwd: Path | None = None) -> int:
    if not path.exists():
        print(f"MISSING_SCRIPT: {path}")
        return 1
    result = subprocess.run([str(path), *forwarded_args], cwd=str(cwd) if cwd else None, check=False)
    return result.returncode


def print_section(title: str) -> None:
    print(f"== {title} ==")


def expand_wrapper(home: Path, wrapper: str) -> Path:
    return Path(wrapper.replace("~", str(home), 1)).expanduser()
