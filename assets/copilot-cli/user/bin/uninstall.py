#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

MANAGED_START = "<!-- agent-governance-standard:start -->"
MANAGED_END = "<!-- agent-governance-standard:end -->"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Uninstall Copilot adapter pieces of Agent Governance Standard.")
    parser.add_argument("--home", help="Override HOME for testing.")
    parser.add_argument("--project", help="Optional project path to clean.")
    parser.add_argument("--remove-shared-home", action="store_true", help="Also remove ~/.agent-governance-standard.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    home = Path(args.home).expanduser().resolve() if args.home else Path.home()
    copilot_home = home / ".copilot"

    remove_managed_block(copilot_home / "copilot-instructions.md")
    for rel in ("bin/copilot-governed", "bin/copilot-governance-doctor", "bin/copilot-governance-uninstall"):
        path = copilot_home / rel
        if path.exists():
            path.unlink()

    adapter_home = home / ".agent-governance-standard" / "copilot-cli"
    if adapter_home.exists():
        shutil.rmtree(adapter_home)
    if args.remove_shared_home:
        shared_home = home / ".agent-governance-standard"
        if shared_home.exists():
            shutil.rmtree(shared_home)

    if args.project:
        project = Path(args.project).expanduser().resolve()
        remove_managed_block(project / ".github" / "copilot-instructions.md")
        instructions_dir = project / ".github" / "instructions"
        for name in (
            "00-governance.instructions.md",
            "10-planning.instructions.md",
            "20-git.instructions.md",
            "30-delegation.instructions.md",
            "40-review.instructions.md",
        ):
            path = instructions_dir / name
            if path.exists():
                path.unlink()

    print("COPILOT_GOVERNANCE_UNINSTALL_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
