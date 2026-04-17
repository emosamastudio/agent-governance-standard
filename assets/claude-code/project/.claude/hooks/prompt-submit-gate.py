#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PLANNING_TERMS = (
    "plan",
    "planning",
    "architecture",
    "tech stack",
    "technical selection",
    "mvp",
    "final system",
    "develop",
    "implementation",
    "implement",
    "delegate",
    "subagent",
    "parallel",
    "规划",
    "架构",
    "技术选型",
    "mvp",
    "最终",
    "开发",
    "实现",
    "并行",
    "派发",
)


def state_incomplete(path: Path) -> bool:
    return not path.exists() or "<fill-me>" in path.read_text()


def extract_text(obj: object) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return " ".join(extract_text(item) for item in obj)
    if isinstance(obj, dict):
        parts = []
        for key in ("text", "content", "message", "value"):
            if key in obj:
                parts.append(extract_text(obj[key]))
        return " ".join(part for part in parts if part)
    return ""


def latest_user_prompt(transcript_path: Path) -> str:
    if not transcript_path.exists():
        return ""
    latest = ""
    for raw in transcript_path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except Exception:
            continue
        role = record.get("role") or record.get("speaker") or record.get("type")
        if role not in {"user", "human"}:
            message = record.get("message")
            if isinstance(message, dict):
                role = message.get("role", role)
        if role in {"user", "human"}:
            latest = extract_text(record)
    return latest.strip()


def block(reason: str) -> int:
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": reason,
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit"},
            }
        )
    )
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cwd = Path(payload.get("cwd") or ".").resolve()
    transcript_path = Path(payload.get("transcript_path") or "")
    latest = latest_user_prompt(transcript_path).lower()
    if not latest:
        return 0

    state_dir = cwd / ".agent-governance" / "state"
    delivery_path = state_dir / "delivery-intent.md"
    workflow_path = state_dir / "git-workflow.md"

    if any(term in latest for term in PLANNING_TERMS) and state_incomplete(delivery_path):
        return block(
            "Governance gate: before planning or technology selection, confirm whether the user wants a final-system build or a fast MVP, then record it in .agent-governance/state/delivery-intent.md."
        )

    if any(term in latest for term in ("push", "merge", "branch", "pr", "commit")) and state_incomplete(workflow_path):
        return block(
            "Governance gate: before deep git workflow work, define .agent-governance/state/git-workflow.md so branch, push, PR, and merge rules are explicit."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
