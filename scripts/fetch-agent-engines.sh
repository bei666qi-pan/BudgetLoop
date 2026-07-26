#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/vendor/agent-engines"
mkdir -p "$DEST"

fetch_engine() {
  local id="$1"
  local repo="$2"
  local revision="$3"
  local exclude_enterprise="${4:-false}"
  local target="$DEST/$id"

  if [[ -e "$target" && ! -d "$target/.git" ]]; then
    echo "Refusing to replace non-git path: $target" >&2
    return 1
  fi
  if [[ ! -d "$target/.git" ]]; then
    git clone --filter=blob:none --no-checkout --depth 1 "https://github.com/$repo.git" "$target"
  fi

  git -C "$target" fetch --depth 1 origin "$revision"
  if [[ "$exclude_enterprise" == "true" ]]; then
    git -C "$target" sparse-checkout init --no-cone
    printf '/*\n!/enterprise/\n' > "$target/.git/info/sparse-checkout"
  else
    git -C "$target" sparse-checkout disable 2>/dev/null || true
  fi
  git -C "$target" checkout --detach --force "$revision"
  echo "$id $(git -C "$target" rev-parse HEAD)"
}

fetch_engine openhands OpenHands/OpenHands 652503005093d18d1b2f48816c91d62e93f45970 true
fetch_engine codex openai/codex 4c43465133428898aa84f0bfc02c306ed65fb66a
fetch_engine gemini-cli google-gemini/gemini-cli 3818efbbfbf8ef029ef53a6ab1093db39971ce83
fetch_engine opencode anomalyco/opencode 7534d23551f665e65080809975b4ca5c7d63807b
