#!/usr/bin/env bash
# Build the AWS deployment bundle: a reproducible source tarball that unpacks
# ready-to-deploy on EC2 (Docker path or bare systemd path).
#
#   bash deploy/aws/build_aws_bundle.sh                # version = VERSION file + git sha
#   bash deploy/aws/build_aws_bundle.sh 7.4.0          # explicit version
#
# Output:
#   dist/PWE-StudioSaaS-aws-<version>.tar.gz
#   dist/PWE-StudioSaaS-aws-<version>.tar.gz.sha256
#
# The bundle contains the clean committed tree (git archive) — including
# deploy/aws/ (Dockerfile, compose, nginx, systemd, README_AWS.md) — so the
# entire deployment procedure ships with the code it deploys.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree must be clean before building an AWS bundle (commit or stash first)." >&2
  exit 1
fi

SHA="$(git rev-parse --short=12 HEAD)"
FILE_VERSION="$(tr -d '[:space:]' < VERSION 2>/dev/null || true)"
VERSION="${1:-${FILE_VERSION:-0.0.0}-$SHA}"
PREFIX="PWE-StudioSaaS-aws-$VERSION"
OUT_DIR="$ROOT/dist"
ARCHIVE="$OUT_DIR/$PREFIX.tar.gz"

mkdir -p "$OUT_DIR"

STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/studiosaas-aws.XXXXXX")"
trap 'rm -rf "$STAGE_ROOT"' EXIT
STAGE_DIR="$STAGE_ROOT/$PREFIX"
mkdir -p "$STAGE_DIR"

git archive --format=tar HEAD | tar -xf - -C "$STAGE_DIR"

# Stamp the build so a running instance can report exactly what it is.
cat > "$STAGE_DIR/BUILD_INFO" <<EOF
version=$VERSION
commit=$(git rev-parse HEAD)
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

# Entry point of the bundle for the operator.
cp "$STAGE_DIR/deploy/aws/README_AWS.md" "$STAGE_DIR/DEPLOY_AWS_FIRST.md"

tar -C "$STAGE_ROOT" -czf "$ARCHIVE" "$PREFIX"
(cd "$OUT_DIR" && shasum -a 256 "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256")

echo "$ARCHIVE"
echo "$ARCHIVE.sha256"
