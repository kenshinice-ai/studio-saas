#!/usr/bin/env bash
# Build and verify both delivery forms from the current clean commit.
#
# This is a packaging gate only; it does not deploy to AWS. The current
# StudioSaaS release remains a local + Cloudflare invitation pilot.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

VERSION="$(tr -d '[:space:]' < VERSION)"
COMMIT="$(git rev-parse HEAD)"
[ -z "$(git status --porcelain)" ] || {
  echo "Release bundle verification requires a clean committed tree." >&2
  exit 1
}

bash deploy/aws/build_aws_bundle.sh "$VERSION" --saas
bash deploy/aws/build_aws_bundle.sh "$VERSION" --edition

verify_bundle() {
  local archive="$1" mode="$2" prefix="$3"
  local checksum="$archive.sha256"
  (
    cd dist
    shasum -a 256 -c "$(basename "$checksum")"
  )

  local build_info
  build_info="$(tar -xOf "$archive" "$prefix/BUILD_INFO")"
  grep -qx "version=$VERSION" <<<"$build_info"
  grep -qx "mode=$mode" <<<"$build_info"
  grep -qx "commit=$COMMIT" <<<"$build_info"

  local inventory
  inventory="$(tar -tzf "$archive")"
  for forbidden in \
    ".pem" \
    "/._" \
    "/.claude/" \
    "/.github/" \
    "/docs/sales/" \
    "/docs/HANDOFF_" \
    "/docs/Project_Audit_" \
    "/docs/UX_Review_" \
    "/docs/Release_Readiness_" \
    "/docs/Project_Review_" \
    "/codingprompt.md" \
    "/docs/Current_Sprint.md" \
    "/docs/design/brand/round2/"; do
    if grep -Fq "$forbidden" <<<"$inventory"; then
      echo "Internal-only path leaked into $(basename "$archive"): $forbidden" >&2
      return 1
    fi
  done

  for required in \
    "$prefix/deploy/aws/docker-compose.lightsail.yml" \
    "$prefix/deploy/aws/lightsail.env.example" \
    "$prefix/deploy/aws/lightsail_ctl.sh"; do
    grep -Fqx "$required" <<<"$inventory" || {
      echo "Lightsail production file missing from $(basename "$archive"): $required" >&2
      return 1
    }
  done

  if [ "$mode" = "standalone" ]; then
    grep -Fqx "$prefix/INSTALL_EDITION_FIRST.md" <<<"$inventory"
    grep -Fqx "$prefix/CUSTOMER_README.md" <<<"$inventory"
    ! grep -Fqx "$prefix/DEPLOY_AWS_FIRST.md" <<<"$inventory"
    ! grep -Fqx "$prefix/RESET_DEMO_TENANT.command" <<<"$inventory"
    ! grep -Fqx "$prefix/backend/scripts/reset_professional_demo.py" <<<"$inventory"
    ! grep -Fq "$prefix/tenants/lets-paint-showcase/" <<<"$inventory"
  else
    grep -Fqx "$prefix/DEPLOY_AWS_FIRST.md" <<<"$inventory"
    ! grep -Fqx "$prefix/INSTALL_EDITION_FIRST.md" <<<"$inventory"
    ! grep -Fqx "$prefix/CUSTOMER_README.md" <<<"$inventory"
    grep -Fqx "$prefix/RESET_DEMO_TENANT.command" <<<"$inventory"
    grep -Fqx "$prefix/backend/scripts/reset_professional_demo.py" <<<"$inventory"
    grep -Fqx "$prefix/product-home.html" <<<"$inventory"
    grep -Fqx "$prefix/customer-resources/PWE_Studio_Data_Import_Template.xlsx" <<<"$inventory"
    grep -Fqx "$prefix/backend/frontend/assets/showcase-botanical.png" <<<"$inventory"
    grep -Fqx "$prefix/backend/frontend/assets/showcase-botanical-home.webp" <<<"$inventory"
    grep -Fqx "$prefix/tenants/lets-paint-showcase/index.html" <<<"$inventory"
  fi
}

SAAS_PREFIX="PWE-StudioSaaS-aws-$VERSION"
EDITION_PREFIX="PWE-Studio-Edition-$VERSION"
verify_bundle "dist/$SAAS_PREFIX.tar.gz" "saas" "$SAAS_PREFIX"
verify_bundle "dist/$EDITION_PREFIX.tar.gz" "standalone" "$EDITION_PREFIX"

echo "Both v$VERSION bundles passed checksum, BUILD_INFO, entrypoint, and exclusion checks."
