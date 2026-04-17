#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MANAGED_MARKER="<!-- agent-governance-standard:start -->"

TRANSPORT="${1:?usage: install-smoke.sh <local|remote> <claude-only|copilot-only|both> [default|explicit]}"
PROFILE="${2:?usage: install-smoke.sh <local|remote> <claude-only|copilot-only|both> [default|explicit]}"
ADAPTER_MODE="${3:-explicit}"

log() {
  printf '==> %s\n' "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

assert_exists() {
  [[ -e "$1" ]] || fail "expected path to exist: $1"
}

assert_not_exists() {
  [[ ! -e "$1" ]] || fail "expected path to be absent: $1"
}

assert_executable() {
  [[ -x "$1" ]] || fail "expected executable: $1"
}

assert_contains() {
  local path="$1"
  local needle="$2"
  grep -Fq -- "$needle" "$path" || fail "expected '$needle' in $path"
}

assert_not_contains() {
  local path="$1"
  local needle="$2"
  if [[ -e "$path" ]] && grep -Fq -- "$needle" "$path"; then
    fail "did not expect '$needle' in $path"
  fi
}

create_remote_archive() {
  local archive_path="$1"
  python3 - "$REPO_ROOT" "$archive_path" <<'PY'
import sys
import tarfile
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
archive_path = Path(sys.argv[2]).resolve()
root_name = "agent-governance-standard-ci"

with tarfile.open(archive_path, "w:gz") as tar:
    tar.add(repo_root, arcname=root_name, recursive=False)
    for path in sorted(repo_root.rglob("*")):
        rel = path.relative_to(repo_root)
        if ".git" in rel.parts:
            continue
        tar.add(path, arcname=str(Path(root_name) / rel), recursive=False)
PY
}

build_install_args() {
  INSTALL_ARGS=(--home "$HOME_DIR" --project "$PROJECT_DIR")
  case "$PROFILE" in
    claude-only)
      EXPECT_CLAUDE=1
      EXPECT_COPILOT=0
      INSTALL_ARGS+=(--adapter claude-code)
      ;;
    copilot-only)
      EXPECT_CLAUDE=0
      EXPECT_COPILOT=1
      INSTALL_ARGS+=(--adapter copilot-cli)
      ;;
    both)
      EXPECT_CLAUDE=1
      EXPECT_COPILOT=1
      if [[ "$ADAPTER_MODE" == "explicit" ]]; then
        INSTALL_ARGS+=(--adapter claude-code --adapter copilot-cli)
      elif [[ "$ADAPTER_MODE" != "default" ]]; then
        fail "unsupported adapter mode for profile 'both': $ADAPTER_MODE"
      fi
      ;;
    *)
      fail "unsupported profile: $PROFILE"
      ;;
  esac
}

run_install() {
  if [[ "$TRANSPORT" == "local" ]]; then
    log "running local install.sh"
    (
      cd "$REPO_ROOT"
      ./install.sh "${INSTALL_ARGS[@]}"
    )
    return
  fi

  if [[ "$TRANSPORT" != "remote" ]]; then
    fail "unsupported transport: $TRANSPORT"
  fi

  log "building local archive for remote bootstrap simulation"
  create_remote_archive "$ARCHIVE_PATH"
  mkdir -p "$REMOTE_RUNNER_DIR"
  log "running remote bootstrap via bash stdin + file:// archive"
  (
    cd "$REMOTE_RUNNER_DIR"
    AGENT_GOVERNANCE_STANDARD_ARCHIVE_URL="file://$ARCHIVE_PATH" \
      bash -s -- "${INSTALL_ARGS[@]}" < "$REPO_ROOT/install.sh"
  )
}

run_doctors() {
  if [[ "$EXPECT_CLAUDE" -eq 1 ]]; then
    "$HOME_DIR/.claude/bin/claude-governance-doctor" --home "$HOME_DIR"
  fi
  if [[ "$EXPECT_COPILOT" -eq 1 ]]; then
    "$HOME_DIR/.copilot/bin/copilot-governance-doctor" --home "$HOME_DIR"
  fi
}

assert_common_install() {
  assert_exists "$HOME_DIR/.agent-governance-standard"
  assert_exists "$PROJECT_DIR/.agent-governance/rules/00-global-governance.md"
  assert_exists "$PROJECT_DIR/.agent-governance/state/delivery-intent.md"
  assert_exists "$PROJECT_DIR/.agent-governance/state/current-mainline.md"
  assert_exists "$PROJECT_DIR/.agent-governance/state/git-workflow.md"
}

assert_claude_install() {
  assert_contains "$HOME_DIR/.claude/CLAUDE.md" "$MANAGED_MARKER"
  assert_executable "$HOME_DIR/.claude/bin/claude-governed"
  assert_executable "$HOME_DIR/.claude/bin/claude-governance-doctor"
  assert_executable "$HOME_DIR/.claude/bin/claude-governance-uninstall"
  assert_exists "$HOME_DIR/.agent-governance-standard/claude-code/bin/doctor.py"
  assert_contains "$PROJECT_DIR/CLAUDE.md" "$MANAGED_MARKER"
  assert_exists "$PROJECT_DIR/.claude/hooks"
  assert_executable "$PROJECT_DIR/.claude/bin/drift-check"
}

assert_copilot_install() {
  assert_contains "$HOME_DIR/.copilot/copilot-instructions.md" "$MANAGED_MARKER"
  assert_executable "$HOME_DIR/.copilot/bin/copilot-governed"
  assert_executable "$HOME_DIR/.copilot/bin/copilot-governance-doctor"
  assert_executable "$HOME_DIR/.copilot/bin/copilot-governance-uninstall"
  assert_exists "$HOME_DIR/.agent-governance-standard/copilot-cli/bin/doctor.py"
  assert_contains "$PROJECT_DIR/.github/copilot-instructions.md" "$MANAGED_MARKER"
  assert_exists "$PROJECT_DIR/.github/instructions/00-governance.instructions.md"
  assert_exists "$PROJECT_DIR/.github/instructions/10-planning.instructions.md"
  assert_exists "$PROJECT_DIR/.github/instructions/20-git.instructions.md"
  assert_exists "$PROJECT_DIR/.github/instructions/30-delegation.instructions.md"
  assert_exists "$PROJECT_DIR/.github/instructions/40-review.instructions.md"
}

assert_install_state() {
  assert_common_install
  if [[ "$EXPECT_CLAUDE" -eq 1 ]]; then
    assert_claude_install
  else
    assert_not_exists "$HOME_DIR/.claude"
    assert_not_exists "$PROJECT_DIR/.claude"
    assert_not_exists "$PROJECT_DIR/CLAUDE.md"
  fi

  if [[ "$EXPECT_COPILOT" -eq 1 ]]; then
    assert_copilot_install
  else
    assert_not_exists "$HOME_DIR/.copilot"
    assert_not_exists "$PROJECT_DIR/.github/copilot-instructions.md"
    assert_not_exists "$PROJECT_DIR/.github/instructions"
  fi
}

assert_claude_uninstall_state() {
  assert_not_exists "$HOME_DIR/.claude/bin/claude-governed"
  assert_not_exists "$HOME_DIR/.claude/bin/claude-governance-doctor"
  assert_not_exists "$HOME_DIR/.claude/bin/claude-governance-uninstall"
  assert_not_exists "$HOME_DIR/.agent-governance-standard/claude-code"
  assert_not_contains "$HOME_DIR/.claude/CLAUDE.md" "$MANAGED_MARKER"
  assert_not_contains "$PROJECT_DIR/CLAUDE.md" "$MANAGED_MARKER"
  assert_not_exists "$PROJECT_DIR/.claude/hooks"
  assert_not_exists "$PROJECT_DIR/.claude/bin/drift-check"
  assert_not_contains "$PROJECT_DIR/.claude/settings.json" "prompt-submit-gate.py"
}

assert_copilot_uninstall_state() {
  assert_not_exists "$HOME_DIR/.copilot/bin/copilot-governed"
  assert_not_exists "$HOME_DIR/.copilot/bin/copilot-governance-doctor"
  assert_not_exists "$HOME_DIR/.copilot/bin/copilot-governance-uninstall"
  assert_not_exists "$HOME_DIR/.agent-governance-standard/copilot-cli"
  assert_not_contains "$HOME_DIR/.copilot/copilot-instructions.md" "$MANAGED_MARKER"
  assert_not_contains "$PROJECT_DIR/.github/copilot-instructions.md" "$MANAGED_MARKER"
  assert_not_exists "$PROJECT_DIR/.github/instructions/00-governance.instructions.md"
  assert_not_exists "$PROJECT_DIR/.github/instructions/10-planning.instructions.md"
  assert_not_exists "$PROJECT_DIR/.github/instructions/20-git.instructions.md"
  assert_not_exists "$PROJECT_DIR/.github/instructions/30-delegation.instructions.md"
  assert_not_exists "$PROJECT_DIR/.github/instructions/40-review.instructions.md"
}

run_uninstall() {
  if [[ "$EXPECT_CLAUDE" -eq 1 ]]; then
    log "uninstalling claude adapter"
    "$HOME_DIR/.claude/bin/claude-governance-uninstall" --home "$HOME_DIR" --project "$PROJECT_DIR"
    assert_claude_uninstall_state
    if [[ "$EXPECT_COPILOT" -eq 1 ]]; then
      assert_exists "$HOME_DIR/.agent-governance-standard"
      "$HOME_DIR/.copilot/bin/copilot-governance-doctor" --home "$HOME_DIR"
    fi
  fi

  if [[ "$EXPECT_COPILOT" -eq 1 ]]; then
    log "uninstalling copilot adapter"
    "$HOME_DIR/.copilot/bin/copilot-governance-uninstall" --home "$HOME_DIR" --project "$PROJECT_DIR" --remove-shared-home
    assert_copilot_uninstall_state
    assert_not_exists "$HOME_DIR/.agent-governance-standard"
    return
  fi

  log "removing shared home with claude uninstall"
  "$CLAUDE_UNINSTALL_WITH_SHARED" --home "$HOME_DIR" --project "$PROJECT_DIR" --remove-shared-home
}

BASE_ROOT="${RUNNER_TEMP:-$REPO_ROOT/.ci-smoke}/install-smoke-${TRANSPORT}-${PROFILE}-${ADAPTER_MODE}"
HOME_DIR="$BASE_ROOT/home"
PROJECT_DIR="$BASE_ROOT/project"
ARCHIVE_PATH="$BASE_ROOT/agent-governance-standard.tar.gz"
REMOTE_RUNNER_DIR="$BASE_ROOT/remote-runner"
CLAUDE_UNINSTALL_WITH_SHARED="$HOME_DIR/.claude/bin/claude-governance-uninstall"

rm -rf "$BASE_ROOT"
mkdir -p "$HOME_DIR" "$PROJECT_DIR"

build_install_args

log "install smoke test: transport=$TRANSPORT profile=$PROFILE adapter_mode=$ADAPTER_MODE"
run_install
assert_install_state
run_doctors

log "re-running install to verify idempotent upgrade path"
run_install
assert_install_state
run_doctors

if [[ "$EXPECT_CLAUDE" -eq 1 && "$EXPECT_COPILOT" -eq 0 ]]; then
  log "uninstalling claude adapter"
  "$CLAUDE_UNINSTALL_WITH_SHARED" --home "$HOME_DIR" --project "$PROJECT_DIR" --remove-shared-home
  assert_claude_uninstall_state
  assert_not_exists "$HOME_DIR/.agent-governance-standard"
else
  run_uninstall
fi

log "install smoke test passed"
