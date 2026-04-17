#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_ADAPTERS = ("claude-code", "copilot-cli")
MANAGED_START = "<!-- agent-governance-standard:start -->"
MANAGED_END = "<!-- agent-governance-standard:end -->"
MANAGED_MANIFEST_VERSION = 1


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

    @property
    def install_state_home(self) -> Path:
        return self.standard_home / "install-state"

    def project_state_dir(self) -> Path:
        if self.project is None:
            raise ValueError("Project state requested without project path.")
        project_key = hashlib.sha256(str(self.project).encode("utf-8")).hexdigest()[:16]
        return self.install_state_home / "projects" / project_key


def default_home() -> Path:
    script_path = Path(__file__).resolve()
    if script_path.parent.name == ".agent-governance-standard":
        return script_path.parent.parent
    return Path.home()


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text() if path.exists() else ""
    updated = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if updated != original:
        path.write_text(updated)


def copy_file_if_changed(src: Path, dst: Path, mode: int | None = None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = src.read_bytes()
    target_bytes = dst.read_bytes() if dst.exists() else None
    if target_bytes != source_bytes:
        backup_if_exists(dst)
        dst.write_bytes(source_bytes)
    if mode is not None:
        dst.chmod(mode)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_to_prefix(rel_path: str, prefixes: tuple[str, ...]) -> bool:
    normalized = tuple(prefix.strip("/").replace("\\", "/") for prefix in prefixes)
    return any(rel_path == prefix or rel_path.startswith(f"{prefix}/") for prefix in normalized)


def remove_empty_dirs(start: Path, stop: Path) -> None:
    current = start
    while current != stop:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


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


def collect_tree_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    files: dict[str, str] = {}
    for item in sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()):
        if item.is_file():
            files[item.relative_to(root).as_posix()] = file_sha256(item)
    return files


def write_manifest(
    manifest_path: Path,
    *,
    source_root: Path | str | None,
    target_root: Path,
    files: dict[str, str],
) -> None:
    write_json(
        manifest_path,
        {
            "version": MANAGED_MANIFEST_VERSION,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceRoot": str(source_root) if source_root is not None else None,
            "targetRoot": str(target_root),
            "files": files,
        },
    )


def record_tree_manifest(manifest_path: Path, *, source_root: Path | str | None, target_root: Path) -> None:
    write_manifest(
        manifest_path,
        source_root=source_root,
        target_root=target_root,
        files=collect_tree_hashes(target_root),
    )


def record_file_manifest(
    manifest_path: Path,
    *,
    target_root: Path,
    files: tuple[Path, ...],
    source_root: Path | str | None = None,
) -> None:
    hashes: dict[str, str] = {}
    for file_path in sorted(files, key=lambda path: path.as_posix()):
        if file_path.exists() and file_path.is_file():
            hashes[file_path.relative_to(target_root).as_posix()] = file_sha256(file_path)
    write_manifest(
        manifest_path,
        source_root=source_root,
        target_root=target_root,
        files=hashes,
    )


def write_wrapper(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text() if path.exists() else None
    if original != content:
        backup_if_exists(path)
        path.write_text(content)
    path.chmod(0o755)
    return path


def sync_tree_with_manifest(
    src: Path,
    dst: Path,
    manifest_path: Path,
    preserve_existing_prefixes: tuple[str, ...] = (),
) -> None:
    previous_manifest = load_json(manifest_path)
    previous_files_raw = previous_manifest.get("files", {})
    previous_files = (
        previous_files_raw
        if isinstance(previous_files_raw, dict) and all(isinstance(key, str) and isinstance(value, str) for key, value in previous_files_raw.items())
        else {}
    )

    current_files: dict[str, str] = {}
    dst.mkdir(parents=True, exist_ok=True)

    for item in sorted(src.rglob("*"), key=lambda path: path.relative_to(src).as_posix()):
        if not item.is_file():
            continue
        rel_path = item.relative_to(src).as_posix()
        target = dst / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)

        if is_relative_to_prefix(rel_path, preserve_existing_prefixes):
            if not target.exists():
                shutil.copy2(item, target)
            continue

        source_hash = file_sha256(item)
        current_files[rel_path] = source_hash
        previous_hash = previous_files.get(rel_path)

        if target.exists():
            if not target.is_file():
                continue
            target_hash = file_sha256(target)
            if target_hash == source_hash:
                continue
            if previous_hash is not None and target_hash != previous_hash:
                continue

        shutil.copy2(item, target)

    for rel_path, previous_hash in previous_files.items():
        if rel_path in current_files:
            continue
        target = dst / rel_path
        if not target.exists() or not target.is_file():
            continue
        if file_sha256(target) != previous_hash:
            continue
        target.unlink()
        remove_empty_dirs(target.parent, dst)

    write_json(
        manifest_path,
        {
            "version": MANAGED_MANIFEST_VERSION,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceRoot": str(src),
            "targetRoot": str(dst),
            "files": current_files,
        },
    )


def package_fingerprint(package_root: Path) -> str:
    digest = hashlib.sha256()
    roots = (
        package_root / "assets",
        package_root / "install.sh",
        package_root / "tools" / "install.py",
    )
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            digest.update(root.relative_to(package_root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(file_sha256(root).encode("utf-8"))
            digest.update(b"\0")
            continue
        for item in sorted(root.rglob("*"), key=lambda path: path.relative_to(package_root).as_posix()):
            if not item.is_file():
                continue
            digest.update(item.relative_to(package_root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(file_sha256(item).encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def record_install_metadata(ctx: InstallContext) -> dict[str, Any]:
    metadata = {
        "installedAt": datetime.now(timezone.utc).isoformat(),
        "packageRoot": str(ctx.package_root),
        "packageFingerprint": package_fingerprint(ctx.package_root),
        "installerSha256": file_sha256(Path(__file__).resolve()),
        "home": str(ctx.home),
        "project": str(ctx.project) if ctx.project is not None else None,
        "adapters": list(ctx.adapters),
        "source": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_SOURCE", "local"),
        "repository": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_REPOSITORY"),
        "requestedRef": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_REQUESTED_REF"),
        "requestedRefType": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_REQUESTED_REF_TYPE"),
        "resolvedRefType": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_REF_TYPE"),
        "resolvedCommit": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT"),
        "resolvedCommitVerification": {
            "status": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT_VERIFICATION"),
            "reason": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT_VERIFICATION_REASON"),
            "verifiedAt": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT_VERIFIED_AT"),
        },
        "archiveUrl": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_ARCHIVE_URL"),
        "archiveSha256": os.environ.get("AGENT_GOVERNANCE_STANDARD_INSTALL_ARCHIVE_SHA256"),
    }
    write_json(ctx.install_state_home / "last-install.json", metadata)
    return metadata


def install_shared_core(ctx: InstallContext) -> None:
    sync_tree_with_manifest(
        ctx.package_root / "assets" / "shared",
        ctx.standard_home,
        ctx.install_state_home / "shared-home-assets.json",
    )
    copy_file_if_changed(Path(__file__).resolve(), ctx.standard_home / "install.py", mode=0o755)
    record_file_manifest(
        ctx.install_state_home / "shared-support-files.json",
        target_root=ctx.standard_home,
        files=(ctx.standard_home / "install.py",),
        source_root=Path(__file__).resolve().parent,
    )


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

    sync_tree_with_manifest(
        ctx.package_root / "assets" / "claude-code" / "user" / "bin",
        ctx.standard_home / "claude-code" / "bin",
        ctx.install_state_home / "claude-user-assets.json",
    )

    wrapper_dir = ctx.claude_home / "bin"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = write_wrapper(
        wrapper_dir / "claude-governed",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec claude --append-system-prompt-file \"$ROOT/.agent-governance-standard/user/top-level-constraints.md\" \"$@\"\n"
    )

    doctor_wrapper = write_wrapper(
        wrapper_dir / "claude-governance-doctor",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/claude-code/bin/doctor.py\" \"$@\"\n"
    )

    status_wrapper = write_wrapper(
        wrapper_dir / "claude-governance-status",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/claude-code/bin/status.py\" \"$@\"\n"
    )

    drift_wrapper = write_wrapper(
        wrapper_dir / "claude-governance-drift",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/claude-code/bin/drift.py\" \"$@\"\n"
    )

    uninstall_wrapper = write_wrapper(
        wrapper_dir / "claude-governance-uninstall",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/claude-code/bin/uninstall.py\" \"$@\"\n"
    )
    record_file_manifest(
        ctx.install_state_home / "claude-user-wrappers.json",
        target_root=wrapper_dir,
        files=(wrapper_path, doctor_wrapper, status_wrapper, drift_wrapper, uninstall_wrapper),
        source_root="generated",
    )

    (ctx.standard_home / "user" / "top-level-constraints.md").write_text(top_level)


def install_copilot_user(ctx: InstallContext) -> None:
    ctx.copilot_home.mkdir(parents=True, exist_ok=True)
    block = load_text(ctx.package_root / "assets" / "copilot-cli" / "user" / "copilot-global-instructions.md")
    upsert_managed_block(ctx.copilot_home / "copilot-instructions.md", block)
    sync_tree_with_manifest(
        ctx.package_root / "assets" / "copilot-cli" / "user" / "bin",
        ctx.standard_home / "copilot-cli" / "bin",
        ctx.install_state_home / "copilot-user-assets.json",
    )

    wrapper_dir = ctx.copilot_home / "bin"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    governed = write_wrapper(
        wrapper_dir / "copilot-governed",
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

    doctor = write_wrapper(
        wrapper_dir / "copilot-governance-doctor",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/copilot-cli/bin/doctor.py\" \"$@\"\n"
    )

    status = write_wrapper(
        wrapper_dir / "copilot-governance-status",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/copilot-cli/bin/status.py\" \"$@\"\n"
    )

    drift = write_wrapper(
        wrapper_dir / "copilot-governance-drift",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/copilot-cli/bin/drift.py\" \"$@\"\n"
    )

    uninstall = write_wrapper(
        wrapper_dir / "copilot-governance-uninstall",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ROOT=\"$(cd \"$(dirname \"$0\")/../..\" && pwd)\"\n"
        "exec python3 \"$ROOT/.agent-governance-standard/copilot-cli/bin/uninstall.py\" \"$@\"\n"
    )
    record_file_manifest(
        ctx.install_state_home / "copilot-user-wrappers.json",
        target_root=wrapper_dir,
        files=(governed, doctor, status, drift, uninstall),
        source_root="generated",
    )


def install_shared_project(ctx: InstallContext) -> None:
    if ctx.project is None:
        return
    project = ctx.project.resolve()
    sync_tree_with_manifest(
        ctx.package_root / "assets" / "shared" / "project" / ".agent-governance",
        project / ".agent-governance",
        ctx.project_state_dir() / "shared-project-assets.json",
        preserve_existing_prefixes=("state",),
    )


def install_claude_project(ctx: InstallContext) -> None:
    if ctx.project is None:
        return
    project = ctx.project.resolve()
    project_claude_dir = project / ".claude"
    project_claude_dir.mkdir(parents=True, exist_ok=True)

    copytree_replace(ctx.package_root / "assets" / "claude-code" / "project" / ".claude" / "hooks", project_claude_dir / "hooks")
    copytree_replace(ctx.package_root / "assets" / "claude-code" / "project" / ".claude" / "bin", project_claude_dir / "bin")
    record_tree_manifest(
        ctx.project_state_dir() / "claude-project-hooks.json",
        source_root=ctx.package_root / "assets" / "claude-code" / "project" / ".claude" / "hooks",
        target_root=project_claude_dir / "hooks",
    )
    record_tree_manifest(
        ctx.project_state_dir() / "claude-project-bin.json",
        source_root=ctx.package_root / "assets" / "claude-code" / "project" / ".claude" / "bin",
        target_root=project_claude_dir / "bin",
    )
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
    sync_tree_with_manifest(
        ctx.package_root / "assets" / "copilot-cli" / "project" / ".github" / "instructions",
        github_dir / "instructions",
        ctx.project_state_dir() / "copilot-project-instructions.json",
    )


def parse_install_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Agent Governance Standard.")
    parser.add_argument("--project", help="Bootstrap project-level governance into this path.")
    parser.add_argument("--home", help="Override HOME for testing or custom install targets.")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=SUPPORTED_ADAPTERS,
        help="Install only the specified adapter. Repeat for multiple adapters.",
    )
    return parser.parse_args(argv)


def parse_status_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report Agent Governance Standard install status.")
    parser.add_argument("--project", help="Optional project path to validate against recorded manifests.")
    parser.add_argument("--home", help="Override HOME for testing or custom install targets.")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=SUPPORTED_ADAPTERS,
        help="Limit status to one adapter. Repeat for multiple adapters.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def manifest_status(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    target_root_raw = manifest.get("targetRoot")
    target_root = Path(target_root_raw).expanduser() if isinstance(target_root_raw, str) else None
    files_raw = manifest.get("files", {})
    files = files_raw if isinstance(files_raw, dict) else {}
    missing: list[str] = []
    modified: list[str] = []
    checked = 0

    if target_root is None:
        return {
            "manifest": str(manifest_path),
            "targetRoot": None,
            "checkedFiles": checked,
            "missing": ["<manifest targetRoot missing>"],
            "modified": modified,
            "ok": False,
        }

    for rel_path, expected_hash in sorted(files.items()):
        if not isinstance(rel_path, str) or not isinstance(expected_hash, str):
            continue
        checked += 1
        target = target_root / rel_path
        if not target.exists() or not target.is_file():
            missing.append(rel_path)
            continue
        if file_sha256(target) != expected_hash:
            modified.append(rel_path)

    return {
        "manifest": str(manifest_path),
        "targetRoot": str(target_root),
        "checkedFiles": checked,
        "missing": missing,
        "modified": modified,
        "ok": not missing and not modified,
    }


def format_manifest_label(manifest_path: Path, install_state_home: Path) -> str:
    try:
        return manifest_path.relative_to(install_state_home).as_posix()
    except ValueError:
        return str(manifest_path)


def status_main(argv: list[str]) -> int:
    args = parse_status_args(argv)
    home = Path(args.home).expanduser().resolve() if args.home else default_home()
    standard_home = home / ".agent-governance-standard"
    install_state_home = standard_home / "install-state"
    last_install_path = install_state_home / "last-install.json"

    issues: list[str] = []
    reports: list[dict[str, Any]] = []
    last_install = load_json(last_install_path)

    if not last_install:
        issues.append(f"Missing install metadata: {last_install_path}")

    manifest_paths = [
        install_state_home / "shared-home-assets.json",
        install_state_home / "shared-support-files.json",
    ]

    adapters = last_install.get("adapters", []) if isinstance(last_install.get("adapters"), list) else []
    requested_adapters = list(dict.fromkeys(args.adapter or []))
    if requested_adapters:
        adapters = [adapter for adapter in adapters if adapter in requested_adapters]
    if "claude-code" in adapters:
        manifest_paths.extend(
            [
                install_state_home / "claude-user-assets.json",
                install_state_home / "claude-user-wrappers.json",
            ]
        )
    if "copilot-cli" in adapters:
        manifest_paths.extend(
            [
                install_state_home / "copilot-user-assets.json",
                install_state_home / "copilot-user-wrappers.json",
            ]
        )

    if args.project:
        project = Path(args.project).expanduser().resolve()
        project_key = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:16]
        project_state_dir = install_state_home / "projects" / project_key
        manifest_paths.append(project_state_dir / "shared-project-assets.json")
        if "claude-code" in adapters:
            manifest_paths.extend(
                [
                    project_state_dir / "claude-project-hooks.json",
                    project_state_dir / "claude-project-bin.json",
                ]
            )
        if "copilot-cli" in adapters:
            manifest_paths.append(project_state_dir / "copilot-project-instructions.json")

    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            issues.append(f"Missing manifest: {manifest_path}")
            continue
        report = manifest_status(manifest_path)
        reports.append(report)
        if not report["ok"]:
            label = format_manifest_label(manifest_path, install_state_home)
            if report["missing"]:
                issues.append(f"{label}: missing {', '.join(report['missing'])}")
            if report["modified"]:
                issues.append(f"{label}: modified {', '.join(report['modified'])}")

    status_payload = {
        "ok": not issues,
        "home": str(home),
        "standardHome": str(standard_home),
        "installStateHome": str(install_state_home),
        "lastInstall": last_install,
        "reports": reports,
        "issues": issues,
    }

    if args.json_output:
        print(json.dumps(status_payload, indent=2, ensure_ascii=True))
        return 0 if status_payload["ok"] else 1

    print("Agent Governance Standard status")
    print(f"- home: {home}")
    if last_install:
        print(f"- last install: {last_install.get('installedAt', 'unknown')}")
        print(f"- source: {last_install.get('source', 'unknown')}")
        if last_install.get("repository"):
            print(f"- repository: {last_install['repository']}")
        if last_install.get("requestedRef"):
            requested_ref_type = last_install.get("requestedRefType") or "unspecified"
            print(f"- requested ref: {last_install['requestedRef']} ({requested_ref_type})")
        if last_install.get("resolvedCommit"):
            resolved_ref_type = last_install.get("resolvedRefType") or "resolved"
            print(f"- resolved {resolved_ref_type}: {last_install['resolvedCommit']}")
        verification = last_install.get("resolvedCommitVerification", {})
        if isinstance(verification, dict) and verification.get("status"):
            line = f"- commit verification: {verification['status']}"
            if verification.get("reason"):
                line += f" ({verification['reason']})"
            print(line)
        if last_install.get("archiveSha256"):
            print(f"- archive sha256: {last_install['archiveSha256']}")
        if last_install.get("packageFingerprint"):
            print(f"- package fingerprint: {last_install['packageFingerprint']}")
    for report in reports:
        label = format_manifest_label(Path(report["manifest"]), install_state_home)
        status = "OK" if report["ok"] else "DRIFT"
        print(f"- {label}: {status} ({report['checkedFiles']} tracked files)")
    if issues:
        print("STATUS: ATTENTION")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("STATUS: OK")
    return 0


def install_main(argv: list[str]) -> int:
    args = parse_install_args(argv)
    adapters = tuple(args.adapter or SUPPORTED_ADAPTERS)
    package_root = Path(__file__).resolve().parent.parent
    home = Path(args.home).expanduser().resolve() if args.home else default_home()
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

    install_metadata = record_install_metadata(ctx)

    print("Agent Governance Standard installed.")
    print(f"- shared home: {ctx.standard_home}")
    print(f"- install status: python3 {ctx.standard_home / 'install.py'} status --home {ctx.home}")
    print(f"- adapters: {', '.join(adapters)}")
    print(f"- install source: {install_metadata['source']}")
    if install_metadata.get("repository"):
        print(f"- install repository: {install_metadata['repository']}")
    requested_ref = install_metadata.get("requestedRef")
    if requested_ref:
        requested_ref_type = install_metadata.get("requestedRefType") or "unspecified"
        print(f"- requested ref: {requested_ref} ({requested_ref_type})")
    resolved_commit = install_metadata.get("resolvedCommit")
    if resolved_commit:
        resolved_ref_type = install_metadata.get("resolvedRefType") or "resolved"
        print(f"- resolved {resolved_ref_type}: {resolved_commit}")
    verification = install_metadata.get("resolvedCommitVerification", {})
    if isinstance(verification, dict) and verification.get("status"):
        line = f"- commit verification: {verification['status']}"
        if verification.get("reason"):
            line += f" ({verification['reason']})"
        print(line)
    archive_sha256 = install_metadata.get("archiveSha256")
    if archive_sha256:
        print(f"- archive sha256: {archive_sha256}")
    package_fingerprint_value = install_metadata.get("packageFingerprint")
    if package_fingerprint_value:
        print(f"- package fingerprint: {package_fingerprint_value}")
    if "claude-code" in adapters:
        print(f"- claude wrapper: {ctx.claude_home / 'bin' / 'claude-governed'}")
        print(f"- claude status: {ctx.claude_home / 'bin' / 'claude-governance-status'}")
        print(f"- claude drift: {ctx.claude_home / 'bin' / 'claude-governance-drift'}")
    if "copilot-cli" in adapters:
        print(f"- copilot global instructions: {ctx.copilot_home / 'copilot-instructions.md'}")
        print(f"- copilot wrapper: {ctx.copilot_home / 'bin' / 'copilot-governed'}")
        print(f"- copilot status: {ctx.copilot_home / 'bin' / 'copilot-governance-status'}")
        print(f"- copilot drift: {ctx.copilot_home / 'bin' / 'copilot-governance-drift'}")
    if project is not None:
        print(f"- project bootstrapped: {project}")
        print(f"- shared project state: {project / '.agent-governance'}")
        if "claude-code" in adapters:
            print(f"- claude drift check: {project / '.claude' / 'bin' / 'drift-check'}")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "status":
        raise SystemExit(status_main(argv[1:]))
    raise SystemExit(install_main(argv))
