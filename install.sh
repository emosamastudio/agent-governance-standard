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
  python3 "$LOCAL_INSTALLER" "$@"
  exit 0
fi

REF="${AGENT_GOVERNANCE_STANDARD_REF:-main}"
ARCHIVE_URL="${AGENT_GOVERNANCE_STANDARD_ARCHIVE_URL:-https://github.com/emosamastudio/agent-governance-standard/archive/refs/heads/${REF}.tar.gz}"
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

ARCHIVE_PATH="$TMP_DIR/agent-governance-standard.tar.gz"
curl -fsSL "$ARCHIVE_URL" -o "$ARCHIVE_PATH"
tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"

EXTRACTED_ROOT="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d -name 'agent-governance-standard-*' | head -n 1)"
if [[ -z "$EXTRACTED_ROOT" ]]; then
  echo "Failed to locate extracted agent-governance-standard package." >&2
  exit 1
fi

python3 "$EXTRACTED_ROOT/tools/install.py" "$@"
