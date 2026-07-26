#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/vendor/ai-gateways"
TARGET="$DEST/new-api"
REPOSITORY="QuantumNous/new-api"
REVISION="bde9b2f44887d34ec54799ae191d50f97914359e"

mkdir -p "$DEST"
if [[ -e "$TARGET" && ! -d "$TARGET/.git" ]]; then
  echo "Refusing to replace non-git path: $TARGET" >&2
  exit 1
fi
if [[ ! -d "$TARGET/.git" ]]; then
  git clone --filter=blob:none --no-checkout --depth 1 "https://github.com/$REPOSITORY.git" "$TARGET"
fi

git -C "$TARGET" fetch --depth 1 origin "$REVISION"
git -C "$TARGET" checkout --detach --force "$REVISION"

actual="$(git -C "$TARGET" rev-parse HEAD)"
if [[ "$actual" != "$REVISION" ]]; then
  echo "New API revision mismatch: expected $REVISION, got $actual" >&2
  exit 1
fi
test -f "$TARGET/LICENSE"
echo "new-api $actual"
