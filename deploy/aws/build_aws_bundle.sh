#!/usr/bin/env bash
# Build a deployment bundle: a reproducible source tarball that unpacks
# ready-to-deploy on EC2 (Docker path or bare systemd path).
#
#   bash deploy/aws/build_aws_bundle.sh                    # SaaS, version = VERSION + git sha
#   bash deploy/aws/build_aws_bundle.sh 7.4.0              # SaaS, explicit version
#   bash deploy/aws/build_aws_bundle.sh 7.7.7 --edition     # PWE Studio Edition
#
# Output:
#   dist/PWE-StudioSaaS-aws-<version>.tar.gz{,.sha256}      # SaaS
#   dist/PWE-Studio-Edition-<version>.tar.gz{,.sha256}      # --edition
#
# The bundle contains the clean committed tree (git archive) — including
# deploy/aws/ (Dockerfile, compose, nginx, systemd, README_AWS.md) — so the
# entire deployment procedure ships with the code it deploys.
#
# --edition builds the single-studio delivery of the SAME tree (one code base,
# two forms — standalone-edition/README.md §3 route A). It differs only in what
# the operator is pointed at first and in the mode recorded in BUILD_INFO:
#
#   * entry point is standalone-edition/RUNBOOK.md, not README_AWS.md
#   * BUILD_INFO carries mode=standalone, which the implementation engineer
#     checks before install (RUNBOOK §0) so a SaaS tarball cannot be delivered
#     to a customer by accident
#   * a CUSTOMER_README.md points the studio owner at OPERATIONS.md
#
# It deliberately does NOT strip the platform-plane source. STUDIOSAAS_MODE
# closes that plane at runtime and 15 isolation checks hold it shut; deleting
# files here would fork the tree into something the test suite never ran
# against, which is the failure mode route B was rejected for.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

EDITION=0
VERSION_ARG=""
for arg in "$@"; do
  case "$arg" in
    --edition) EDITION=1 ;;
    --saas)    EDITION=0 ;;
    -h|--help) sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)        echo "Unknown option: $arg (see --help)" >&2; exit 2 ;;
    *)         VERSION_ARG="$arg" ;;
  esac
done

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree must be clean before building a bundle (commit or stash first)." >&2
  exit 1
fi

SHA="$(git rev-parse --short=12 HEAD)"
FILE_VERSION="$(tr -d '[:space:]' < VERSION 2>/dev/null || true)"
VERSION="${VERSION_ARG:-${FILE_VERSION:-0.0.0}-$SHA}"

if [ "$EDITION" = "1" ]; then
  PREFIX="PWE-Studio-Edition-$VERSION"
  MODE="standalone"
else
  PREFIX="PWE-StudioSaaS-aws-$VERSION"
  MODE="saas"
fi

OUT_DIR="$ROOT/dist"
ARCHIVE="$OUT_DIR/$PREFIX.tar.gz"

mkdir -p "$OUT_DIR"

STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/studiosaas-bundle.XXXXXX")"
trap 'rm -rf "$STAGE_ROOT"' EXIT
STAGE_DIR="$STAGE_ROOT/$PREFIX"
mkdir -p "$STAGE_DIR"

git archive --format=tar HEAD | tar -xf - -C "$STAGE_DIR"

# Stamp the build so a running instance can report exactly what it is, and so
# the implementation engineer can prove which form they are holding.
cat > "$STAGE_DIR/BUILD_INFO" <<EOF
version=$VERSION
mode=$MODE
commit=$(git rev-parse HEAD)
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

if [ "$EDITION" = "1" ]; then
  # Entry point is the implementation runbook, not the SaaS AWS guide.
  cp "$STAGE_DIR/standalone-edition/RUNBOOK.md" "$STAGE_DIR/INSTALL_EDITION_FIRST.md"
  cat > "$STAGE_DIR/CUSTOMER_README.md" <<EOF
# PWE Studio Edition $VERSION

这台服务器上运行的是属于你一家工作室的独立版本。

- **日常运维看** [standalone-edition/OPERATIONS.md](standalone-edition/OPERATIONS.md)
  （备份怎么确认、怎么重启、出什么问题找谁）
- 安装与交付流程（实施工程师用）见
  [standalone-edition/RUNBOOK.md](standalone-edition/RUNBOOK.md)
- 商务条款（维护档位、更新次数、回迁通道）见
  [standalone-edition/COMMERCIAL.md](standalone-edition/COMMERCIAL.md)

本版本 = $VERSION，构建于 $(date -u +%Y-%m-%d)。
升级时请核对 \`BUILD_INFO\` 里的 version 与 mode（应为 \`standalone\`）。

---

*A PARADISE PRODUCTION · 天域文创出品*
EOF
else
  cp "$STAGE_DIR/deploy/aws/README_AWS.md" "$STAGE_DIR/DEPLOY_AWS_FIRST.md"
fi

tar -C "$STAGE_ROOT" -czf "$ARCHIVE" "$PREFIX"
(cd "$OUT_DIR" && shasum -a 256 "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256")

echo "$ARCHIVE"
echo "$ARCHIVE.sha256"
echo "mode=$MODE version=$VERSION"
