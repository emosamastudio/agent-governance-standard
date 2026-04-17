#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_ADAPTERS = ("claude-code", "copilot-cli")
MANAGED_START = "<!-- agent-governance-standard:start -->"
MANAGED_END = "<!-- agent-governance-standard:end -->"


@dataclass
class InstallContext:
    package_root: Path
    home: Path
    project: Path | None
    adapters: tuple[str, ...]

    @property
    def standard_home(self) -> Path:
        return self.home / ".agent-governance-standard"

    @property
    def claude_home(self) -> Path:
        return self.home / ".claude"

    @property
    def copilot_home(self) -> Path:
        return self.home / ".copilot"


def backup_if_exists(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copy2(path, backup)


def managed_block(content: str) -> str:
    return f"{MANAGED_START}\n{content.strip()}\n{MANAGED_END}\n"


def upsert_managed_block(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text() if path.exists() else ""
    block = managed_block(content)
    if MANAGED_START in original and MANAGED_END in original:
        prefix = original.split(MANAGED_START, 1)[0].rstrip()
        suffix = original.split(MANAGED_END, 1)[1].lstrip("\n")
        updated = f"{prefix}\n\n{block}"
        if suffix:
            updated += f"\n{suffix}"
    else:
        updated = original.rstrip()
        if updated:
            updated += "\n\n"
        updated += block
    if updated != original:
        backup_if_exists(path)
        path.write_text(updated)


def load_text(path: Path) -> str:
    return path.read_text().strip() + "\n"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def list_merge(left: list[Any], right: list[Any]) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for item in [*left, *right]:
        key = json.dumps(item, sort_keys=True, ensure_ascii=True)
        if key not in seen:
            merged.append(item)
            seen.add(key)
    return merged


def hook_signature(entry: dict[str, Any]) -> tuple[Any, ...]:
    hooks = entry.get("hooks", [])
    hook_sigs = []
    for hook in hooks:
        hook_sigs.append(
            (
                hook.get("type"),
                hook.get("command"),
                hook.get("matcher"),
                hook.get("if"),
                hook.get("async"),
                hook.get("asyncRewake"),
                hook.get("timeout"),
            )
        )
    return (entry.get("matcher"), tuple(hook_sigs))


def merge_json(target_path: Path, template_path: Path) -> None:
    target = load_json(target_path)
    template = load_json(template_path)

    def merge_dict(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
        if "$schema" in src and "$schema" not in dst:
            dst["$schema"] = src["$schema"]

        for key, value in src.items():
            if key == "hooks":
                target_hooks = dst.setdefault("hooks", {})
                for event, entries in value.items():
                    existing = target_hooks.setdefault(event, [])
                    seen = {hook_signature(entry) for entry in existing}
                    for entry in entries:
                        sig = hook_signature(entry)
                        if sig not in seen:
                            existing.append(entry)
                            seen.add(sig)
            elif key not in dst:
                dst[key] = value
            elif isinstance(dst[key], dict) and isinstance(value, dict):
                dst[key] = merge_dict(dst[key], value)
            elif isinstance(dst[key], list) and isinstance(value, list):
                dst[key] = list_merge(dst[key], value)
        return dst

    target = merge_dict(target, template)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    original = target_path.read_text() if target_path.exists() else ""
    updated = json.dumps(target, indent=2, ensure_ascii=True) + "\n"
    if updated != original:
        backup_if_exists(target_path)
        target_path.write_text(updated)


def enforce_json_baseline(target_path: Path, updates: dict[str, Any]) -> None:
    target = load_json(target_path)

    def apply(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
        for key, value in src.items():
            if isinstance(value, dict):
                child = dst.get(key)
                if not isinstance(child, dict):
                    child = {}
                dst[key] = apply(child, value)
            elif isinstance(value, list):
                current = dst.get(key)
                if not isinstance(current, list):
                    current = []
                dst[key] = list_merge(current, value)
            else:
                dst[key] = value
        return dst

    updated_data = apply(target, updates)
    original = target_path.read_text() if target_path.exists() else ""
    updated = json.dumps(updated_data, indent=2, ensure_ascii=True) + "\n"
    if updated != original:
        backup_if_exists(target_path)
        target_path.write_text(updated)


def copytree_replace(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def sync_tree(src: Path, dst: Path, preserve_existing: bool = False) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            sync_tree(item, target, preserve_existing=preserve_existing)
            continue
        if preserve_existing and target.exists():
            continue
        shutil.copy2(item, target)


def install_shared_core(ctx: InstallContext) -> None:
    sync_tree(ctx.package_root / "assets" / "shared", ctx.standard_home, preserve_existing=False)


def install_claude_user(ctx: InstallContext) -> None:
    ctx.claude_home.mkdir(parents=True, exist_ok=True)
    top_level = load_text(ctx.package_root / "assets" / "shared" / "user" / "top-level-constraints.md")
    operating_model = load_text(ctx.package_root / "assets" / "claude-code" / "user" / "claude-user.md")
    upsert_managed_block(ctx.claude_home / "CLAUDE.md", operating_model)
    merge_json(
        ctx.claude_home / "settings.json",
        ctx.package_root / "assets" / "claude-code" / "user" / "settings.template.json",
    )
    enforce_json_baseline(
        ctx.claude_home / "settings.json",
        {
            "defaultMode": "plan",
            "disableAllHooks": False,
            "env": {"AGENT_GOVERNANCE_STANDARD": "1"},
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
        },
    )

    sync_tree(
        ctx.package_root / "assets" / "claude-code" / "user" / "bin",
        ctx.standard_home / "claude-code" / "bin",
        preserve_existing=False,
    )

    wrapper_dir = ctx.claude_home / "bin"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = wrapper_dir / "claude-governed"
    wrapper_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec claude --append-system-prompt-file \"$ROOT/.agent-governance-standard/user/top-level-constraints.md\" \"$@\"\n"
    )
    wrapper_path.chmod(0o755)

    doctor_wrapper = wrapper_dir / "claude-governance-doctor"
    doctor_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/claude-code/bin/doctor.py\" \"$@\"\n"
    )
    doctor_wrapper.chmod(0o755)

    uninstall_wrapper = wrapper_dir / "claude-governance-uninstall"
    uninstall_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/claude-code/bin/uninstall.py\" \"$@\"\n"
    )
    uninstall_wrapper.chmod(0o755)

    (ctx.standard_home / "user" / "top-level-constraints.md").write_text(top_level)


def install_copilot_user(ctx: InstallContext) -> None:
    ctx.copilot_home.mkdir(parents=True, exist_ok=True)
    block = load_text(ctx.package_root / "assets" / "copilot-cli" / "user" / "copilot-global-instructions.md")
    upsert_managed_block(ctx.copilot_home / "copilot-instructions.md", block)
    sync_tree(
        ctx.package_root / "assets" / "copilot-cli" / "user" / "bin",
        ctx.standard_home / "copilot-cli" / "bin",
        preserve_existing=False,
    )

    wrapper_dir = ctx.copilot_home / "bin"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    governed = wrapper_dir / "copilot-governed"
    governed.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "exec copilot "
        "--allow-tool='shell(git status)' "
        "--allow-tool='shell(git diff:*)' "
        "--allow-tool='shell(git log:*)' "
        "--allow-tool='shell(git branch --show-current)' "
        "--deny-tool='shell(git push)' "
        "--deny-tool='shell(git reset:*)' "
        "--deny-tool='shell(git checkout --:*)' "
        "--deny-tool='shell(rm:*)' "
        "--deny-tool='shell(killall:*)' "
        "--deny-tool='shell(pkill:*)' "
        "\"$@\"\n"
    )
    governed.chmod(0o755)

    doctor = wrapper_dir / "copilot-governance-doctor"
    doctor.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/copilot-cli/bin/doctor.py\" \"$@\"\n"
    )
    doctor.chmod(0o755)

    uninstall = wrapper_dir / "copilot-governance-uninstall"
    uninstall.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/copilot-cli/bin/uninstall.py\" \"$@\"\n"
    )
    uninstall.chmod(0o755)


def install_shared_project(ctx: InstallContext) -> None:
    if ctx.project is None:
        return
    project = ctx.project.resolve()
    sync_tree(
        ctx.package_root / "assets" / "shared" / "project" / ".agent-governance",
        project / ".agent-governance",
        preserve_existing=True,
    )


def install_claude_project(ctx: InstallContext) -> None:
    if ctx.project is None:
        return
    project = ctx.project.resolve()
    project_claude_dir = project / ".claude"
    project_claude_dir.mkdir(parents=True, exist_ok=True)

    copytree_replace(ctx.package_root / "assets" / "claude-code" / "project" / ".claude" / "hooks", project_claude_dir / "hooks")
    copytree_replace(ctx.package_root / "assets" / "claude-code" / "project" / ".claude" / "bin", project_claude_dir / "bin")
    merge_json(project_claude_dir / "settings.json", ctx.package_root / "assets" / "claude-code" / "project" / "settings.template.json")
    enforce_json_baseline(
        project_claude_dir / "settings.json",
        {
            "disableAllHooks": False,
        },
    )

    claude_project_block = load_text(ctx.package_root / "assets" / "claude-code" / "project" / "claude-project.md")
    upsert_managed_block(project / "CLAUDE.md", claude_project_block)
    (project_claude_dir / "bin" / "drift-check").chmod(0o755)


def install_copilot_project(ctx: InstallContext) -> None:
    if ctx.project is None:
        return
    project = ctx.project.resolve()
    github_dir = project / ".github"
    github_dir.mkdir(parents=True, exist_ok=True)
    block = load_text(ctx.package_root / "assets" / "copilot-cli" / "project" / "copilot-project-instructions.md")
    upsert_managed_block(github_dir / "copilot-instructions.md", block)
    sync_tree(
        ctx.package_root / "assets" / "copilot-cli" / "project" / ".github" / "instructions",
        github_dir / "instructions",
        preserve_existing=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Agent Governance Standard.")
    parser.add_argument("--project", help="Bootstrap project-level governance into this path.")
    parser.add_argument("--home", help="Override HOME for testing or custom install targets.")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=SUPPORTED_ADAPTERS,
        help="Install only the specified adapter. Repeat for multiple adapters.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    adapters = tuple(args.adapter or SUPPORTED_ADAPTERS)
    package_root = Path(__file__).resolve().parent.parent
    home = Path(args.home).expanduser().resolve() if args.home else Path.home()
    project = Path(args.project).expanduser().resolve() if args.project else None
    ctx = InstallContext(package_root=package_root, home=home, project=project, adapters=adapters)

    install_shared_core(ctx)
    install_shared_project(ctx)

    if "claude-code" in adapters:
        install_claude_user(ctx)
        install_claude_project(ctx)

    if "copilot-cli" in adapters:
        install_copilot_user(ctx)
        install_copilot_project(ctx)

    print("Agent Governance Standard installed.")
    print(f"- shared home: {ctx.standard_home}")
    print(f"- adapters: {', '.join(adapters)}")
    if "claude-code" in adapters:
        print(f"- claude wrapper: {ctx.claude_home / 'bin' / 'claude-governed'}")
    if "copilot-cli" in adapters:
        print(f"- copilot global instructions: {ctx.copilot_home / 'copilot-instructions.md'}")
        print(f"- copilot wrapper: {ctx.copilot_home / 'bin' / 'copilot-governed'}")
    if project is not None:
        print(f"- project bootstrapped: {project}")
        print(f"- shared project state: {project / '.agent-governance'}")
        if "claude-code" in adapters:
            print(f"- claude drift check: {project / '.claude' / 'bin' / 'drift-check'}")


if __name__ == "__main__":
    main()
