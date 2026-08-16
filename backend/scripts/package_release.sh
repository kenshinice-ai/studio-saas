#!/usr/bin/env bash
# ============================================================================
# 已弃用 / DEPRECATED — 请用 deploy/aws/build_aws_bundle.sh
#
# 这个脚本产出的包没有 BUILD_INFO（version/mode/commit 戳），部署护栏
# （pwestudio_remote.sh 的 mode=saas 检查、verify_release_bundles.sh 的
# BUILD_INFO 门禁）都无法验证它，所以它打出的东西不可部署。
# 现行打包流程见 docs/Release_Runbook.md 第 6 步：
#
#     bash deploy/aws/build_aws_bundle.sh <version>            # SaaS
#     bash deploy/aws/build_aws_bundle.sh <version> --edition  # Edition
#
# 原脚本正文保留在下方仅作 git 史留档，永不再执行。
# ============================================================================
echo "已弃用：请用 deploy/aws/build_aws_bundle.sh（见 docs/Release_Runbook.md 第 6 步）。" >&2
echo "DEPRECATED: use deploy/aws/build_aws_bundle.sh — its bundles carry BUILD_INFO," >&2
echo "which every deploy guard checks; this script's output is undeployable." >&2
exit 1

# ── 以下为历史留档，不再执行 ────────────────────────────────────────────────
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
