#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

MANAGED_START = "<!-- agent-governance-standard:start -->"
REQUIRED_PROJECT_FILES = (
    ".github/copilot-instructions.md",
    ".github/instructions/00-governance.instructions.md",
    ".github/instructions/10-planning.instructions.md",
    ".github/instructions/20-git.instructions.md",
    ".github/instructions/30-delegation.instructions.md",
    ".github/instructions/40-review.instructions.md",
    ".agent-governance/state/delivery-intent.md",
    ".agent-governance/state/current-mainline.md",
    ".agent-governance/state/git-workflow.md",
    ".agent-governance/bin/drift-check",
)
REQUIRED_RULE_FILES = (
    ".agent-governance/rules/00-global-governance.md",
    ".agent-governance/rules/01-planning-and-parallelism.md",
    ".agent-governance/rules/02-mainline-routing.md",
    ".agent-governance/rules/03-lifecycle-observability.md",
    ".agent-governance/rules/04-technology-research.md",
    ".agent-governance/rules/05-acceptance-and-review.md",
    ".agent-governance/rules/06-git-governance.md",
    ".agent-governance/rules/07-hook-hardening.md",
)
WRAPPER_SNIPPETS = {
    "copilot-governed": (
        "exec copilot ",
        "--allow-tool='shell(git status)'",
        "--allow-tool='shell(git diff:*)'",
        "--allow-tool='shell(git log:*)'",
        "--allow-tool='shell(git branch --show-current)'",
        "--deny-tool='shell(git push)'",
        "--deny-tool='shell(git reset:*)'",
        "--deny-tool='shell(git checkout --:*)'",
        "--deny-tool='shell(rm:*)'",
        "--deny-tool='shell(killall:*)'",
        "--deny-tool='shell(pkill:*)'",
    ),
    "copilot-governance-doctor": (
        'exec python3 "$ROOT/.agent-governance-standard/copilot-cli/bin/doctor.py" "$@"',
    ),
    "copilot-governance-uninstall": (
        'exec python3 "$ROOT/.agent-governance-standard/copilot-cli/bin/uninstall.py" "$@"',
    ),
}
PROJECT_SNIPPETS = {
    ".github/copilot-instructions.md": (
        "This repository uses `.agent-governance/` as the shared governance surface.",
        "Use commits as process records",
        "Use `/review` before calling significant work complete",
    ),
    ".github/instructions/00-governance.instructions.md": (
        "Treat `.agent-governance/` as the shared governance surface.",
        "delivery mode in `.agent-governance/state/delivery-intent.md`",
    ),
    ".github/instructions/10-planning.instructions.md": (
        "start with `/plan`",
        "final-system build or a fast MVP",
    ),
    ".github/instructions/20-git.instructions.md": (
        "Use commits as process records",
        "Keep `.agent-governance/state/git-workflow.md` current",
    ),
    ".github/instructions/30-delegation.instructions.md": (
        "Use `/fleet` only",
        "Use `/delegate`",
    ),
    ".github/instructions/40-review.instructions.md": (
        "Use `/review`",
        "delivery intent, mainline, git workflow",
    ),
}


def read_text(path: Path, issues: list[str]) -> str:
    try:
        return path.read_text()
    except OSError as exc:
        issues.append(f"Unable to read {path}: {exc}")
        return ""


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


def run_drift_check(path: Path, project: Path, issues: list[str]) -> None:
    try:
        result = subprocess.run(
            [str(path)],
            cwd=str(project),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        issues.append(f"Unable to run drift check {path}: {exc}")
        return
    if result.returncode != 0:
        combined = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        issues.append(f"Project drift check failed via {path}: {summarize_output(combined)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Agent Governance Standard Copilot install health.")
    parser.add_argument("--home", help="Override HOME for testing.")
    parser.add_argument("--project", help="Optional project path to validate.")
    return parser.parse_args()


def detect_home() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    args = parse_args()
    home = Path(args.home).expanduser().resolve() if args.home else detect_home()
    issues: list[str] = []

    standard_home = home / ".agent-governance-standard"
    adapter_home = standard_home / "copilot-cli" / "bin"
    global_file = home / ".copilot" / "copilot-instructions.md"

    if not standard_home.exists():
        issues.append(f"Missing shared install home: {standard_home}")
    for rel in ("doctor.py", "uninstall.py"):
        target = adapter_home / rel
        if not target.exists():
            issues.append(f"Missing adapter file: {target}")

    global_text = read_text(global_file, issues) if global_file.exists() else ""
    if not global_file.exists() or MANAGED_START not in global_text:
        issues.append(f"Missing managed Copilot block in {global_file}")
    else:
        for snippet in (
            "When a repository contains `.agent-governance/`, use it as the shared governance surface.",
            "Prefer launching Copilot through `~/.copilot/bin/copilot-governed`",
        ):
            if snippet not in global_text:
                issues.append(f"Managed Copilot guidance drift in {global_file}: missing snippet {snippet}")

    for name, snippets in WRAPPER_SNIPPETS.items():
        check_wrapper(home / ".copilot" / "bin" / name, snippets, issues)

    if args.project:
        project = Path(args.project).expanduser().resolve()
        for rel in (*REQUIRED_PROJECT_FILES, *REQUIRED_RULE_FILES):
            path = project / rel
            if not path.exists():
                issues.append(f"Missing project file: {path}")

        repo_file = project / ".github" / "copilot-instructions.md"
        repo_text = read_text(repo_file, issues) if repo_file.exists() else ""
        if repo_file.exists() and MANAGED_START not in repo_text:
            issues.append(f"Missing managed Copilot block in {repo_file}")

        for rel, snippets in PROJECT_SNIPPETS.items():
            path = project / rel
            if not path.exists():
                continue
            text = read_text(path, issues)
            for snippet in snippets:
                if snippet not in text:
                    issues.append(f"Project guidance drift in {path}: missing snippet {snippet}")

        drift = project / ".agent-governance" / "bin" / "drift-check"
        if not drift.exists() or not os.access(drift, os.X_OK):
            issues.append(f"Missing executable: {drift}")
        else:
            run_drift_check(drift, project, issues)

    if issues:
        print("COPILOT_GOVERNANCE_DOCTOR_FAILED")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("COPILOT_GOVERNANCE_DOCTOR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
