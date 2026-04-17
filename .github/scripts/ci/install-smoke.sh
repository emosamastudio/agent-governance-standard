#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MANAGED_MARKER="<!-- agent-governance-standard:start -->"

TRANSPORT="${1:?usage: install-smoke.sh <local|remote> <claude-only|copilot-only|both> [default|explicit] [archive-override|tag-lightweight-auto|tag-annotated-explicit]}"
PROFILE="${2:?usage: install-smoke.sh <local|remote> <claude-only|copilot-only|both> [default|explicit] [archive-override|tag-lightweight-auto|tag-annotated-explicit]}"
ADAPTER_MODE="${3:-explicit}"
REMOTE_SCENARIO="${4:-archive-override}"
REMOTE_EXPECT_METADATA=0
REMOTE_REPOSITORY=""
REMOTE_REF=""
REMOTE_REF_TYPE=""
REMOTE_EXPECTED_ARCHIVE_URL=""
REMOTE_RESOLVED_COMMIT=""

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

assert_json_field() {
  local path="$1"
  local key="$2"
  local expected="$3"
  python3 - "$path" "$key" "$expected" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
expected = sys.argv[3]
data = json.loads(path.read_text())
actual = data.get(key)
if actual is None:
    actual = ""
if str(actual) != expected:
    raise SystemExit(f"expected {key}={expected!r} in {path}, got {actual!r}")
PY
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

configure_remote_scenario() {
  REMOTE_EXPECT_METADATA=0
  REMOTE_REPOSITORY="ci/mock-agent-governance-standard"
  REMOTE_REF="main"
  REMOTE_REF_TYPE="auto"
  REMOTE_BRANCH_EXISTS=0
  REMOTE_TAG_OBJECT_TYPE=""
  REMOTE_TAG_OBJECT_SHA=""
  REMOTE_RESOLVED_COMMIT=""

  case "$REMOTE_SCENARIO" in
    archive-override)
      ;;
    tag-lightweight-auto)
      REMOTE_EXPECT_METADATA=1
      REMOTE_REF="v0.0.0-ci-lightweight"
      REMOTE_REF_TYPE="auto"
      REMOTE_TAG_OBJECT_TYPE="commit"
      REMOTE_RESOLVED_COMMIT="1111111111111111111111111111111111111111"
      REMOTE_TAG_OBJECT_SHA="$REMOTE_RESOLVED_COMMIT"
      ;;
    tag-annotated-explicit)
      REMOTE_EXPECT_METADATA=1
      REMOTE_REF="v0.0.0-ci-annotated"
      REMOTE_REF_TYPE="tag"
      REMOTE_TAG_OBJECT_TYPE="tag"
      REMOTE_TAG_OBJECT_SHA="2222222222222222222222222222222222222222"
      REMOTE_RESOLVED_COMMIT="3333333333333333333333333333333333333333"
      ;;
    *)
      fail "unsupported remote scenario: $REMOTE_SCENARIO"
      ;;
  esac

  REMOTE_EXPECTED_ARCHIVE_URL="https://github.com/${REMOTE_REPOSITORY}/archive/${REMOTE_RESOLVED_COMMIT}.tar.gz"
}

prepare_mock_github() {
  mkdir -p "$MOCK_BIN_DIR"
  cat > "$MOCK_BIN_DIR/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")
url=""
outfile=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output)
      outfile="${2:-}"
      shift 2
      ;;
    -H|--header|--retry|--retry-delay)
      shift 2
      ;;
    --*)
      shift
      ;;
    -*)
      shift
      ;;
    http://*|https://*|file://*)
      url="$1"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

api_root="https://api.github.com/repos/${MOCK_GITHUB_REPOSITORY}"
branch_ref_url="${api_root}/git/ref/heads/${MOCK_GITHUB_REF}"
tag_ref_url="${api_root}/git/ref/tags/${MOCK_GITHUB_REF}"
tag_object_url="${api_root}/git/tags/${MOCK_GITHUB_TAG_OBJECT_SHA}"
archive_url="https://github.com/${MOCK_GITHUB_REPOSITORY}/archive/${MOCK_GITHUB_RESOLVED_COMMIT}.tar.gz"

write_output() {
  if [[ -n "$outfile" ]]; then
    cat > "$outfile"
  else
    cat
  fi
}

if [[ "$url" == "$branch_ref_url" ]]; then
  if [[ "${MOCK_GITHUB_BRANCH_EXISTS}" == "1" ]]; then
    printf '{"object":{"type":"commit","sha":"%s"}}\n' "${MOCK_GITHUB_BRANCH_SHA}" | write_output
    exit 0
  fi
  exit 22
fi

if [[ "$url" == "$tag_ref_url" ]]; then
  printf '{"object":{"type":"%s","sha":"%s"}}\n' "${MOCK_GITHUB_TAG_OBJECT_TYPE}" "${MOCK_GITHUB_TAG_OBJECT_SHA}" | write_output
  exit 0
fi

if [[ "$url" == "$tag_object_url" ]]; then
  if [[ "${MOCK_GITHUB_TAG_OBJECT_TYPE}" != "tag" ]]; then
    exit 22
  fi
  printf '{"object":{"type":"commit","sha":"%s"}}\n' "${MOCK_GITHUB_RESOLVED_COMMIT}" | write_output
  exit 0
fi

if [[ "$url" == "$archive_url" ]]; then
  if [[ -n "$outfile" ]]; then
    cp "${MOCK_GITHUB_ARCHIVE_PATH}" "$outfile"
  else
    cat "${MOCK_GITHUB_ARCHIVE_PATH}"
  fi
  exit 0
fi

exec "${REAL_CURL}" "${original_args[@]}"
EOF
  chmod +x "$MOCK_BIN_DIR/curl"
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

  configure_remote_scenario
  log "building local archive for remote bootstrap simulation"
  create_remote_archive "$ARCHIVE_PATH"
  mkdir -p "$REMOTE_RUNNER_DIR"
  if [[ "$REMOTE_SCENARIO" == "archive-override" ]]; then
    log "running remote bootstrap via bash stdin + file:// archive"
    (
      cd "$REMOTE_RUNNER_DIR"
      AGENT_GOVERNANCE_STANDARD_ARCHIVE_URL="file://$ARCHIVE_PATH" \
        bash -s -- "${INSTALL_ARGS[@]}" < "$REPO_ROOT/install.sh"
    )
    return
  fi

  prepare_mock_github
  log "running remote bootstrap via mocked GitHub tag resolution (${REMOTE_SCENARIO})"
  (
    cd "$REMOTE_RUNNER_DIR"
    PATH="$MOCK_BIN_DIR:$PATH" \
      REAL_CURL="$REAL_CURL" \
      MOCK_GITHUB_REPOSITORY="$REMOTE_REPOSITORY" \
      MOCK_GITHUB_REF="$REMOTE_REF" \
      MOCK_GITHUB_BRANCH_EXISTS="$REMOTE_BRANCH_EXISTS" \
      MOCK_GITHUB_BRANCH_SHA="$REMOTE_BRANCH_SHA" \
      MOCK_GITHUB_TAG_OBJECT_TYPE="$REMOTE_TAG_OBJECT_TYPE" \
      MOCK_GITHUB_TAG_OBJECT_SHA="$REMOTE_TAG_OBJECT_SHA" \
      MOCK_GITHUB_RESOLVED_COMMIT="$REMOTE_RESOLVED_COMMIT" \
      MOCK_GITHUB_ARCHIVE_PATH="$ARCHIVE_PATH" \
      AGENT_GOVERNANCE_STANDARD_REPOSITORY="$REMOTE_REPOSITORY" \
      AGENT_GOVERNANCE_STANDARD_REF="$REMOTE_REF" \
      AGENT_GOVERNANCE_STANDARD_REF_TYPE="$REMOTE_REF_TYPE" \
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

  if [[ "$TRANSPORT" == "remote" && "$REMOTE_EXPECT_METADATA" -eq 1 ]]; then
    assert_remote_install_metadata
  fi
}

assert_remote_install_metadata() {
  local metadata_path="$HOME_DIR/.agent-governance-standard/install-state/last-install.json"
  assert_exists "$metadata_path"
  assert_json_field "$metadata_path" "source" "remote"
  assert_json_field "$metadata_path" "repository" "$REMOTE_REPOSITORY"
  assert_json_field "$metadata_path" "requestedRef" "$REMOTE_REF"
  assert_json_field "$metadata_path" "requestedRefType" "$REMOTE_REF_TYPE"
  assert_json_field "$metadata_path" "resolvedRefType" "tag"
  assert_json_field "$metadata_path" "resolvedCommit" "$REMOTE_RESOLVED_COMMIT"
  assert_json_field "$metadata_path" "archiveUrl" "$REMOTE_EXPECTED_ARCHIVE_URL"
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

BASE_ROOT="${RUNNER_TEMP:-$REPO_ROOT/.ci-smoke}/install-smoke-${TRANSPORT}-${PROFILE}-${ADAPTER_MODE}-${REMOTE_SCENARIO}"
HOME_DIR="$BASE_ROOT/home"
PROJECT_DIR="$BASE_ROOT/project"
ARCHIVE_PATH="$BASE_ROOT/agent-governance-standard.tar.gz"
REMOTE_RUNNER_DIR="$BASE_ROOT/remote-runner"
MOCK_BIN_DIR="$BASE_ROOT/mock-bin"
CLAUDE_UNINSTALL_WITH_SHARED="$HOME_DIR/.claude/bin/claude-governance-uninstall"
REAL_CURL="$(command -v curl)"
REMOTE_BRANCH_SHA="4444444444444444444444444444444444444444"

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
