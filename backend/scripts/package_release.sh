#!/usr/bin/env bash
# Build a reproducible source release from the current Git commit.
# Local databases, media, credentials, virtual environments and logs are excluded.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

SHA="$(git rev-parse --short=12 HEAD)"
MODE="commit"
if [ "${1:-}" = "--working-tree" ]; then
  MODE="working-tree"
  shift
fi
if [ "$MODE" = "commit" ] && [ -n "$(git status --porcelain)" ]; then
  echo "Working tree must be clean before commit packaging. Use --working-tree only for a reviewed candidate." >&2
  exit 1
fi

VERSION="${1:-$(date +%Y%m%d)-$SHA}"
OUT_DIR="$ROOT/dist"
ARCHIVE="$OUT_DIR/PWE-StudioSaaS-$VERSION.tar.gz"

mkdir -p "$OUT_DIR"
if [ "$MODE" = "working-tree" ]; then
  STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/studiosaas-release.XXXXXX")"
  trap 'rm -rf "$STAGE_ROOT"' EXIT
  STAGE_DIR="$STAGE_ROOT/PWE-StudioSaaS-$VERSION"
  mkdir -p "$STAGE_DIR"
  git ls-files -co --exclude-standard -z \
    | tar --null -T - -cf - \
    | tar -xf - -C "$STAGE_DIR"
  tar -C "$STAGE_ROOT" -czf "$ARCHIVE" "PWE-StudioSaaS-$VERSION"
else
  git archive --format=tar --prefix="PWE-StudioSaaS-$VERSION/" HEAD | gzip -9 > "$ARCHIVE"
fi
shasum -a 256 "$ARCHIVE" > "$ARCHIVE.sha256"

echo "$ARCHIVE"
echo "$ARCHIVE.sha256"
