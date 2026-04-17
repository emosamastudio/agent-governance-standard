#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+checkout\s+--\b",
    r"\btruncate\b",
    r"\bDROP\s+TABLE\b",
    r"\bkillall\b",
    r"\bpkill\b",
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    command = ""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or ""

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, flags=re.IGNORECASE):
            print(f"Blocked dangerous command: {command}", file=sys.stderr)
            return 2

    cwd = Path(payload.get("cwd") or ".").resolve()
    mainline_path = cwd / ".agent-governance" / "state" / "current-mainline.md"
    additional_context = None
    if mainline_path.exists() and "<fill-me>" in mainline_path.read_text():
        additional_context = (
            "Governance reminder: .agent-governance/state/current-mainline.md still contains placeholders. "
            "Before going deeper, clarify the active mainline, execution frontier, and acceptance criteria."
        )

    if additional_context:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "permissionDecisionReason": "Passed safety checks",
                        "additionalContext": additional_context,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
