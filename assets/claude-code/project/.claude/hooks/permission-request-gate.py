#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+checkout\s+--\b",
    r"\bkillall\b",
    r"\bpkill\b",
    r"\btruncate\b",
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input")
    command = ""
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or ""

    if tool_name == "Bash" and any(re.search(pattern, command, flags=re.IGNORECASE) for pattern in DANGEROUS_PATTERNS):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PermissionRequest",
                        "decision": {"behavior": "deny"},
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
