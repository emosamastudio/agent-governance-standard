#!/usr/bin/env bash
set -euo pipefail

SOURCE_PATH="${BASH_SOURCE[0]-}"
if [[ -n "$SOURCE_PATH" && "$SOURCE_PATH" != "bash" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$SOURCE_PATH")" && pwd)"
else
  SCRIPT_DIR="$(pwd)"
fi
LOCAL_INSTALLER="$SCRIPT_DIR/tools/install.py"

if [[ -f "$LOCAL_INSTALLER" ]]; then
  AGENT_GOVERNANCE_STANDARD_INSTALL_SOURCE="local" \
    python3 "$LOCAL_INSTALLER" "$@"
  exit 0
fi

REPOSITORY="${AGENT_GOVERNANCE_STANDARD_REPOSITORY:-emosamastudio/agent-governance-standard}"
REF="${AGENT_GOVERNANCE_STANDARD_REF:-main}"
REF_TYPE="${AGENT_GOVERNANCE_STANDARD_REF_TYPE:-auto}"
ARCHIVE_URL_OVERRIDE="${AGENT_GOVERNANCE_STANDARD_ARCHIVE_URL:-}"
API_ROOT="https://api.github.com/repos/${REPOSITORY}"
ARCHIVE_URL=""
RESOLVED_REF_TYPE=""
RESOLVED_COMMIT=""
RESOLVED_COMMIT_VERIFICATION=""
RESOLVED_COMMIT_VERIFICATION_REASON=""
RESOLVED_COMMIT_VERIFIED_AT=""
INSTALL_SOURCE="remote"
INSTALL_REPOSITORY="$REPOSITORY"

fail() {
  echo "$*" >&2
  exit 1
}

json_field() {
  local expression="$1"
  python3 -c "import json, sys; data = json.load(sys.stdin); value = ${expression}; print('' if value is None else value)"
}

github_api_get() {
  local path="$1"
  curl -fsSL -H "Accept: application/vnd.github+json" "${API_ROOT}/${path}"
}

resolve_branch_ref() {
  local ref="$1"
  local branch_json
  branch_json="$(github_api_get "git/ref/heads/${ref}")" || return 1
  RESOLVED_REF_TYPE="branch"
  RESOLVED_COMMIT="$(printf '%s' "$branch_json" | json_field "data.get('object', {}).get('sha')")"
  [[ -n "$RESOLVED_COMMIT" ]] || fail "Failed to resolve branch ref '${ref}'."
  ARCHIVE_URL="https://github.com/${REPOSITORY}/archive/${RESOLVED_COMMIT}.tar.gz"
}

resolve_tag_ref() {
  local ref="$1"
  local tag_json
  local object_type
  local object_sha
  tag_json="$(github_api_get "git/ref/tags/${ref}")" || return 1
  object_type="$(printf '%s' "$tag_json" | json_field "data.get('object', {}).get('type')")"
  object_sha="$(printf '%s' "$tag_json" | json_field "data.get('object', {}).get('sha')")"
  [[ -n "$object_sha" ]] || fail "Failed to resolve tag ref '${ref}'."
  RESOLVED_REF_TYPE="tag"
  if [[ "$object_type" == "tag" ]]; then
    RESOLVED_COMMIT="$(github_api_get "git/tags/${object_sha}" | json_field "data.get('object', {}).get('sha')")"
  else
    RESOLVED_COMMIT="$object_sha"
  fi
  [[ -n "$RESOLVED_COMMIT" ]] || fail "Failed to resolve commit for tag '${ref}'."
  ARCHIVE_URL="https://github.com/${REPOSITORY}/archive/${RESOLVED_COMMIT}.tar.gz"
}

resolve_commit_ref() {
  local ref="$1"
  local commit_json
  [[ "$ref" =~ ^[0-9a-fA-F]{7,40}$ ]] || fail "Commit refs must be 7-40 hexadecimal characters: '${ref}'."
  commit_json="$(github_api_get "commits/${ref}")" || fail "Commit '${ref}' was not found in ${REPOSITORY}."
  RESOLVED_REF_TYPE="commit"
  RESOLVED_COMMIT="$(printf '%s' "$commit_json" | json_field "data.get('sha')")"
  RESOLVED_COMMIT_VERIFICATION="$(printf '%s' "$commit_json" | json_field "'verified' if data.get('commit', {}).get('verification', {}).get('verified') is True else ('unverified' if data.get('commit', {}).get('verification', {}).get('verified') is False else '')")"
  RESOLVED_COMMIT_VERIFICATION_REASON="$(printf '%s' "$commit_json" | json_field "data.get('commit', {}).get('verification', {}).get('reason')")"
  RESOLVED_COMMIT_VERIFIED_AT="$(printf '%s' "$commit_json" | json_field "data.get('commit', {}).get('verification', {}).get('verified_at')")"
  [[ -n "$RESOLVED_COMMIT" ]] || fail "Failed to resolve commit '${ref}'."
  ARCHIVE_URL="https://github.com/${REPOSITORY}/archive/${RESOLVED_COMMIT}.tar.gz"
}

resolve_commit_verification() {
  local commit_json
  [[ -n "$RESOLVED_COMMIT" ]] || return 0
  [[ -n "$RESOLVED_COMMIT_VERIFICATION" ]] && return 0
  commit_json="$(github_api_get "commits/${RESOLVED_COMMIT}")" || return 0
  RESOLVED_COMMIT_VERIFICATION="$(printf '%s' "$commit_json" | json_field "'verified' if data.get('commit', {}).get('verification', {}).get('verified') is True else ('unverified' if data.get('commit', {}).get('verification', {}).get('verified') is False else '')")"
  RESOLVED_COMMIT_VERIFICATION_REASON="$(printf '%s' "$commit_json" | json_field "data.get('commit', {}).get('verification', {}).get('reason')")"
  RESOLVED_COMMIT_VERIFIED_AT="$(printf '%s' "$commit_json" | json_field "data.get('commit', {}).get('verification', {}).get('verified_at')")"
}

resolve_remote_ref() {
  case "$REF_TYPE" in
    branch)
      resolve_branch_ref "$REF" || fail "Branch '${REF}' was not found in ${REPOSITORY}."
      ;;
    tag)
      resolve_tag_ref "$REF" || fail "Tag '${REF}' was not found in ${REPOSITORY}."
      ;;
    commit)
      resolve_commit_ref "$REF"
      ;;
    auto)
      if [[ "$REF" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
        resolve_commit_ref "$REF"
        return
      fi

      local branch_exists=0
      local tag_exists=0
      if github_api_get "git/ref/heads/${REF}" >/dev/null 2>&1; then
        branch_exists=1
      fi
      if github_api_get "git/ref/tags/${REF}" >/dev/null 2>&1; then
        tag_exists=1
      fi

      if [[ "$branch_exists" -eq 1 && "$tag_exists" -eq 1 ]]; then
        fail "Ref '${REF}' is ambiguous in ${REPOSITORY}; set AGENT_GOVERNANCE_STANDARD_REF_TYPE=branch or tag."
      fi
      if [[ "$tag_exists" -eq 1 ]]; then
        resolve_tag_ref "$REF"
        return
      fi
      if [[ "$branch_exists" -eq 1 ]]; then
        resolve_branch_ref "$REF"
        return
      fi

      fail "Ref '${REF}' was not found in ${REPOSITORY}; set AGENT_GOVERNANCE_STANDARD_REF_TYPE explicitly if needed."
      ;;
    *)
      fail "Unsupported AGENT_GOVERNANCE_STANDARD_REF_TYPE='${REF_TYPE}'. Use auto, branch, tag, or commit."
      ;;
  esac
}

if [[ -n "$ARCHIVE_URL_OVERRIDE" ]]; then
  ARCHIVE_URL="$ARCHIVE_URL_OVERRIDE"
  INSTALL_SOURCE="remote-override"
  INSTALL_REPOSITORY=""
  RESOLVED_REF_TYPE=""
  RESOLVED_COMMIT=""
else
  resolve_remote_ref
  resolve_commit_verification
fi

echo "Agent Governance Standard remote bootstrap" >&2
echo "- repository: ${REPOSITORY}" >&2
echo "- requested ref: ${REF} (${REF_TYPE})" >&2
if [[ -n "$RESOLVED_REF_TYPE" ]]; then
  echo "- resolved ref: ${RESOLVED_REF_TYPE}" >&2
fi
if [[ -n "$RESOLVED_COMMIT" ]]; then
  echo "- resolved commit: ${RESOLVED_COMMIT}" >&2
fi
if [[ -n "$RESOLVED_COMMIT_VERIFICATION" ]]; then
  echo "- commit verification: ${RESOLVED_COMMIT_VERIFICATION}" >&2
  if [[ -n "$RESOLVED_COMMIT_VERIFICATION_REASON" ]]; then
    echo "- verification reason: ${RESOLVED_COMMIT_VERIFICATION_REASON}" >&2
  fi
  if [[ -n "$RESOLVED_COMMIT_VERIFIED_AT" ]]; then
    echo "- verified at: ${RESOLVED_COMMIT_VERIFIED_AT}" >&2
  fi
fi
echo "- archive: ${ARCHIVE_URL}" >&2

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

ARCHIVE_PATH="$TMP_DIR/agent-governance-standard.tar.gz"
curl -fsSL --retry 3 --retry-delay 1 "$ARCHIVE_URL" -o "$ARCHIVE_PATH"
ARCHIVE_SHA256="$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}')"
echo "- archive sha256: ${ARCHIVE_SHA256}" >&2
tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"

EXTRACTED_ROOT="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d -name 'agent-governance-standard-*' | head -n 1)"
if [[ -z "$EXTRACTED_ROOT" ]]; then
  echo "Failed to locate extracted agent-governance-standard package." >&2
  exit 1
fi

AGENT_GOVERNANCE_STANDARD_INSTALL_SOURCE="$INSTALL_SOURCE" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_REPOSITORY="$INSTALL_REPOSITORY" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_REQUESTED_REF="$REF" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_REQUESTED_REF_TYPE="$REF_TYPE" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_REF_TYPE="$RESOLVED_REF_TYPE" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT="$RESOLVED_COMMIT" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT_VERIFICATION="$RESOLVED_COMMIT_VERIFICATION" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT_VERIFICATION_REASON="$RESOLVED_COMMIT_VERIFICATION_REASON" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_RESOLVED_COMMIT_VERIFIED_AT="$RESOLVED_COMMIT_VERIFIED_AT" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_ARCHIVE_URL="$ARCHIVE_URL" \
  AGENT_GOVERNANCE_STANDARD_INSTALL_ARCHIVE_SHA256="$ARCHIVE_SHA256" \
  python3 "$EXTRACTED_ROOT/tools/install.py" "$@"
