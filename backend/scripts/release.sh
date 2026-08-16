#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  StudioSaaS — Release orchestrator (REL-01)
#
#      bash backend/scripts/release.sh <version> [--until <step>] [--from <step>]
#
#  A shell around docs/Release_Runbook.md's nine steps — it changes WHO types
#  the commands, never what the commands are. Every step calls the existing
#  script for that step and stops on the first failure, in that step's own
#  vocabulary. The discipline is unchanged; the transcription errors are gone.
#
#  Steps, in order (also the values --until/--from accept):
#
#    bump            rewrite the version ledger in one shot (see below)
#    preflight       backend/scripts/release_preflight.sh          (runbook 1)
#    verify          STUDIOSAAS_REQUIRE_POSTGRES=1 verify_local.sh (runbook 4)
#    commit          STOPS if the tree is dirty — committing is a human
#                    decision and this script never commits         (runbook 5)
#    build           deploy/aws/build_aws_bundle.sh, SaaS + Edition (runbook 6)
#    verify-bundles  deploy/aws/verify_release_bundles.sh           (runbook 7)
#    guard           three-way commit identity: bundle BUILD_INFO ==
#                    local HEAD == origin/main (fetched first). This is
#                    runbook's "nothing may be added after step 6" as a
#                    machine check instead of a rule people remember.
#    deploy          pwestudio_remote.sh deploy <SaaS bundle>       (runbook 8)
#    health          public deep health summary                     (runbook 8)
#
#  Two interactive confirmations: before build and before deploy. Runbook
#  steps 2 and 3 stay human: bump edits the ledger, but the handoff section
#  (step 3) must be WRITTEN by the releasing human — preflight fails until it
#  names the new version, and that failing is the step working.
#
#  bump: every ledger position that carries the version label, asserted
#  before and after each edit (a replacement that silently misses is worse
#  than none — scripted-edit discipline). Release-notes files get a skeleton
#  section only; content stays human. It never touches docs/HANDOFF_LATEST.md.
#
#  Typical first run:  release.sh 10.8.0 --until verify
#     … write handoff, review diff, commit …
#  Then:               release.sh 10.8.0 --from build
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

BOLD='\033[1m'; CYAN='\033[1;36m'; RED='\033[1;31m'; NC='\033[0m'
say() { printf '\n%b══ release: %s ══%b\n' "$CYAN" "$*" "$NC"; }
die() { printf '%bERROR: %s%b\n' "$RED" "$*" "$NC" >&2; exit 1; }

confirm() {
  # Confirmation points are the human's three decisions; a pipe cannot decide.
  [ -t 0 ] || die "interactive confirmation required for: $1 (run from a terminal)"
  printf '%b%s [y/N] %b' "$BOLD" "$1" "$NC"
  local answer; read -r answer
  case "$answer" in y|Y|yes|YES) return 0 ;; *) die "not confirmed — stopping" ;; esac
}

STEPS=(bump preflight verify commit build verify-bundles guard deploy health)
step_index() {
  local i
  for i in "${!STEPS[@]}"; do [ "${STEPS[$i]}" = "$1" ] && { echo "$i"; return 0; }; done
  die "unknown step: $1 (steps: ${STEPS[*]})"
}

NEW=""; UNTIL="health"; FROM="bump"
while [ $# -gt 0 ]; do
  case "$1" in
    --until) UNTIL="${2:?--until needs a step}"; shift 2 ;;
    --from)  FROM="${2:?--from needs a step}";  shift 2 ;;
    -h|--help) sed -n '2,42p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) die "unknown option: $1 (see --help)" ;;
    *)  [ -z "$NEW" ] || die "one version only (got '$NEW' and '$1')"; NEW="$1"; shift ;;
  esac
done
[ -n "$NEW" ] || { sed -n '2,42p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must be MAJOR.MINOR.PATCH, got: $NEW"
FROM_I="$(step_index "$FROM")"; UNTIL_I="$(step_index "$UNTIL")"
[ "$FROM_I" -le "$UNTIL_I" ] || die "--from $FROM is after --until $UNTIL"

runs() { # runs <step>: is this step inside the requested window?
  local i; i="$(step_index "$1")"
  [ "$i" -ge "$FROM_I" ] && [ "$i" -le "$UNTIL_I" ]
}
finish_if_done() {
  if [ "$(step_index "$1")" -eq "$UNTIL_I" ]; then
    say "stopped after '$1' as requested (--until $UNTIL)"
    exit 0
  fi
}

# ── bump primitives: assert old exists, replace, assert new landed ─────────
replace_all() { # file old new  — literal, whole-file, both sides asserted
  local file="$1" old="$2" new="$3" content before after
  [ -f "$file" ] || die "bump: no such file: $file"
  grep -qF -- "$old" "$file" || die "bump: '$old' not found in $file — the ledger moved; fix release.sh"
  before="$(grep -oF -- "$old" "$file" | wc -l | tr -d ' ')"
  content="$(cat "$file"; printf x)"; content="${content%x}"
  # Replacement side deliberately UNQUOTED: macOS bash 3.2 copies quote
  # characters from a quoted replacement into the output ("v10.8.0" instead
  # of v10.8.0). No word splitting happens inside ${...//}, so this is safe.
  content="${content//"$old"/$new}"
  printf '%s' "$content" > "$file"
  grep -qF -- "$old" "$file" && die "bump: '$old' still present in $file after replacement"
  after="$(grep -oF -- "$new" "$file" | wc -l | tr -d ' ')"
  [ "$after" -ge "$before" ] || die "bump: $file has $after copies of '$new' after replacing $before copies of '$old' — replacement corrupted"
  echo "  ledger: $file  ('$old' -> '$new', ${before}x)"
}

insert_after_line() { # file exact-marker-line text  — first occurrence only
  local file="$1" marker="$2" text="$3" tmp inserted=""
  [ -f "$file" ] || die "bump: no such file: $file"
  tmp="$(mktemp "${TMPDIR:-/tmp}/release-bump.XXXXXX")"
  while IFS= read -r line; do
    printf '%s\n' "$line" >> "$tmp"
    if [ -z "$inserted" ] && [ "$line" = "$marker" ]; then
      printf '%s\n' "$text" >> "$tmp"
      inserted=1
    fi
  done < "$file"
  [ -n "$inserted" ] || { rm -f "$tmp"; die "bump: marker line not found in $file: $marker"; }
  mv "$tmp" "$file"
  echo "  ledger: $file  (skeleton section inserted)"
}

bump() {
  local OLD; OLD="$(tr -d '[:space:]' < VERSION)"
  if [ "$OLD" = "$NEW" ]; then
    say "bump — VERSION already reads $NEW, ledger edits skipped"
    return 0
  fi
  [[ "$OLD" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "VERSION file carries an unsafe label: $OLD"
  say "bump $OLD -> $NEW"

  # 1. VERSION — the source of truth everything else must agree with.
  printf '%s\n' "$NEW" > VERSION
  grep -qx "$NEW" VERSION || die "bump: VERSION write failed"
  echo "  ledger: VERSION"

  # 2. backend/server.py — APP_VERSION and today's RELEASE_DATE.
  replace_all backend/server.py "APP_VERSION   = '$OLD'" "APP_VERSION   = '$NEW'"
  local old_date today
  old_date="$(sed -n "s/^RELEASE_DATE  = '\([0-9-]*\)'.*/\1/p" backend/server.py)"
  [ -n "$old_date" ] || die "bump: RELEASE_DATE not found in backend/server.py"
  today="$(date +%Y-%m-%d)"
  if [ "$old_date" != "$today" ]; then
    replace_all backend/server.py "RELEASE_DATE  = '$old_date'" "RELEASE_DATE  = '$today'"
  fi

  # 3. Role guides — the version each guide declares in its header.
  local f
  for f in docs/guides/*.md; do
    replace_all "$f" "v$OLD" "v$NEW"
  done

  # 4. README release rows.
  replace_all README.md "$OLD" "$NEW"

  # 5. Edition delivery documents — package names and candidate labels.
  for f in standalone-edition/*.md; do
    if grep -qF -- "$OLD" "$f"; then
      replace_all "$f" "$OLD" "$NEW"
    fi
  done

  # 6. Customer release notes — SKELETON ONLY, the content is a human's.
  insert_after_line customer-resources/Release_Notes.html \
'  <div class="grid">' \
"    <article class=\"card\">
      <strong data-lang=\"en\">v$NEW — (skeleton: write this entry before release)</strong><strong data-lang=\"zh\">v$NEW ——（骨架：发布前补写）</strong>
      <p data-lang=\"en\">Placeholder created by release.sh bump. Replace with what v$NEW actually changes; delivery evidence, not roadmap promises.</p>
      <p data-lang=\"zh\">release.sh bump 生成的占位条目。发布前替换为 v$NEW 的实际变更；写交付依据，不写路线图承诺。</p>
    </article>"
  insert_after_line docs/customer/Release_Notes.md \
"# PWE Studio — Release Notes and Acceptance Evidence" \
"
## v$NEW — （骨架：发布前补写标题与内容）

Placeholder created by release.sh bump — describe what v$NEW changes, its
deployment state, and where the acceptance evidence lives, before releasing."

  echo
  echo "  changed files:"
  git diff --stat -- VERSION backend/server.py docs/guides README.md \
    standalone-edition customer-resources/Release_Notes.html \
    docs/customer/Release_Notes.md | sed 's/^/  /'
  echo
  printf '%b' "$BOLD"
  cat <<EOF
  bump done — two things remain HUMAN before this can pass preflight:
    1. write the v$NEW section at the TOP of docs/HANDOFF_LATEST.md (runbook step 3);
    2. fill in both release-notes skeletons (they currently say so themselves).
EOF
  printf '%b' "$NC"
}

SAAS_BUNDLE="dist/PWE-StudioSaaS-aws-$NEW.tar.gz"
EDITION_BUNDLE="dist/PWE-Studio-Edition-$NEW.tar.gz"

bundle_commit() { # tarball prefix
  tar xzOf "$1" "$2/BUILD_INFO" 2>/dev/null | sed -n 's/^commit=//p'
}

# ── the sequence ───────────────────────────────────────────────────────────
if runs bump; then bump; fi
finish_if_done bump

if runs preflight; then
  say "preflight (runbook step 1)"
  bash backend/scripts/release_preflight.sh || die "preflight failed — if the ledger check is red, the handoff/'skeleton' reminders above are why. Fix, then resume: release.sh $NEW --from preflight"
fi
finish_if_done preflight

if runs verify; then
  say "gate: verify_local with mandatory PostgreSQL (runbook step 4)"
  STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh \
    || die "gate failed — diagnose it or stop the release; never waive it by skipping PostgreSQL"
fi
finish_if_done verify

if runs commit; then
  say "commit check (runbook step 5 — yours, not mine)"
  if [ -n "$(git status --porcelain)" ]; then
    git status --short
    printf '%b' "$BOLD"
    cat <<EOF

  The tree has uncommitted work and this script NEVER commits for you.
  Commit everything (including docs — the bundle is 'git archive HEAD'), then:

      bash backend/scripts/release.sh $NEW --from build
EOF
    printf '%b' "$NC"
    exit 0
  fi
  echo "  tree is clean — HEAD is what will ship"
fi
finish_if_done commit

if runs build; then
  say "build both delivery forms (runbook step 6)"
  confirm "Confirmation 1/2 — build v$NEW bundles from HEAD $(git rev-parse --short=12 HEAD)?"
  bash deploy/aws/build_aws_bundle.sh "$NEW"
  bash deploy/aws/build_aws_bundle.sh "$NEW" --edition
fi
finish_if_done build

if runs verify-bundles; then
  say "verify bundles (runbook step 7)"
  bash deploy/aws/verify_release_bundles.sh
fi
finish_if_done verify-bundles

if runs guard; then
  say "three-way commit guard (nothing added after the build — runbook's hard rule)"
  [ -f "$SAAS_BUNDLE" ] || die "missing $SAAS_BUNDLE — run the build step"
  git fetch origin || die "cannot fetch origin — the guard needs origin/main's real position"
  LOCAL_HEAD="$(git rev-parse HEAD)"
  ORIGIN_MAIN="$(git rev-parse origin/main)"
  BUNDLE_COMMIT="$(bundle_commit "$SAAS_BUNDLE" "PWE-StudioSaaS-aws-$NEW")"
  [ -n "$BUNDLE_COMMIT" ] || die "$SAAS_BUNDLE carries no BUILD_INFO commit"
  echo "  bundle BUILD_INFO : $BUNDLE_COMMIT"
  echo "  local HEAD        : $LOCAL_HEAD"
  echo "  origin/main       : $ORIGIN_MAIN"
  [ "$BUNDLE_COMMIT" = "$LOCAL_HEAD" ] || die "the bundle was built from a different commit than HEAD — rebuild (runbook: go back to step 6)"
  if [ -f "$EDITION_BUNDLE" ]; then
    EDITION_COMMIT="$(bundle_commit "$EDITION_BUNDLE" "PWE-Studio-Edition-$NEW")"
    [ "$EDITION_COMMIT" = "$LOCAL_HEAD" ] || die "the Edition bundle was built from $EDITION_COMMIT, not HEAD — rebuild both forms"
  fi
  [ "$LOCAL_HEAD" = "$ORIGIN_MAIN" ] || die "HEAD is not origin/main. Publish the release commit first:
    git push origin HEAD
    git merge-base --is-ancestor origin/main HEAD   # prove fast-forward
    git push origin HEAD:main
  then resume: release.sh $NEW --from guard
  (Deploying a commit main does not have is how a hotfix gets lost.)"
  echo "  identical — what was gated is what was built is what main records"
fi
finish_if_done guard

if runs deploy; then
  say "deploy to production (runbook step 8)"
  confirm "Confirmation 2/2 — deploy v$NEW to pwestudio.online now?"
  bash deploy/aws/pwestudio_remote.sh deploy "$SAAS_BUNDLE"
fi
finish_if_done deploy

if runs health; then
  say "deep health summary"
  bash deploy/aws/pwestudio_remote.sh health
  echo
  say "done — what remains is runbook step 9 (close)"
  cat <<EOF
  Record in README's three rows and the handoff: git revision, bundle hashes,
  backup dump + manifest names, health payloads, operator and time.
  main was already synced before the deploy (the guard requires it).
EOF
fi
