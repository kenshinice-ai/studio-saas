#!/usr/bin/env bash
# Operate the pwestudio.online instance on the Oracle ARM host.
#
# Production moved here from AWS Lightsail on 2026-09-17. The shape of a deploy
# changed with it: the old host unpacked a release tarball and moved a symlink,
# this one checks out a commit and builds the image on the box. There is no
# bundle in the path at all — `deploy/aws/build_aws_bundle.sh` still produces
# the Edition deliverable and the archival SaaS artefact, but nothing here
# consumes them.
#
# Until this script existed the procedure was prose in docs/Release_Runbook.md,
# which meant the two guards written for the AWS path did not apply to the host
# that actually serves traffic. They do now, and they are the same two:
#
#   before anything moves — prove this box is the one pwestudio.online reaches
#   after it comes up    — prove the public edge reports the commit we deployed
#
# Commands:
#   status            Containers, image tags, the pinned version. Read-only.
#   verify-target     Prove this box is the one $PUBLIC_URL reaches. Changes
#                     nothing. Run it whenever the answer is in doubt.
#   health            Public deep health, redirect and transport.
#   logs [n]          Application logs.
#   deploy <commit>   Check out <commit>, rebuild, restart, verify, roll back
#                     automatically if verification fails.
#   ssh               Interactive shell.
#
# The SSH identity comes from ~/.ssh/config:
#
#   Host pwe-arm
#     HostName 130.162.197.219
#
# Override with PWESTUDIO_ARM_SSH_HOST=<alias> for a rehearsal host.

set -euo pipefail

SSH_HOST="${PWESTUDIO_ARM_SSH_HOST:-pwe-arm}"
ROOT="/srv/pwestudio"
APP="$ROOT/app"
ENV_FILE="$ROOT/shared/production.env"
COMPOSE_DIR="$APP/deploy/aws"
PROJECT="pwestudio"
PUBLIC_URL="${PWESTUDIO_PUBLIC_URL:-https://pwestudio.online}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

remote() { ssh -o ConnectTimeout=15 "$SSH_HOST" "$@"; }

# `--profile local-db` is not optional here. The database is a service of this
# same project (`profiles: ["local-db"]` in docker-compose.yml), and without the
# flag compose refuses the whole project with
# `service "app" depends on undefined service "db"` — it does not start the app
# without the database, it declines to parse. Both compose files document the
# flag in their header comments; the first version of this script did not carry
# it and failed on the first real deploy.
compose() {
  remote "cd $COMPOSE_DIR && sudo docker compose -p $PROJECT --env-file $ENV_FILE \
    -f docker-compose.yml -f docker-compose.lightsail.yml --profile local-db $*"
}

pinned_version() { remote "sudo sed -n 's/^STUDIOSAAS_VERSION=//p' $ENV_FILE | tail -1"; }
app_commit()     { remote "sudo git -C $APP rev-parse HEAD"; }

# ── is this box the one $PUBLIC_URL reaches? ─────────────────────────────────
#
# The same question deploy/aws/pwestudio_remote.sh asks, for the same reason:
# the machine that used to serve this domain is still running, and a deploy to
# it succeeds while changing nothing anybody sees. Two boxes on the same
# release are identical in everything the application says about itself, so
# only machine state can separate them — disk is the one machine fact the deep
# health payload always carries.
#
# Heuristic on purpose, and deliberately before anything moves. The proof is
# the post-deploy assertion further down.
assert_box_serves_public_url() {
  local box public
  box="$(remote "curl -fsS --max-time 10 'http://127.0.0.1:8899/v1/health?deep=1'" 2>/dev/null || true)"
  public="$(curl -fsS --max-time 20 "$PUBLIC_URL/v1/health?deep=1" 2>/dev/null || true)"
  [ -n "$box" ]    || die "$SSH_HOST does not answer its own health on 127.0.0.1:8899 — cannot prove it serves $PUBLIC_URL"
  [ -n "$public" ] || die "$PUBLIC_URL does not answer deep health — refusing to deploy blind"

  BOX_HEALTH="$box" PUBLIC_HEALTH="$public" PUBLIC_URL="$PUBLIC_URL" SSH_HOST="$SSH_HOST" \
  python3 - <<'PYEOF' || die "the deploy target is not the machine serving $PUBLIC_URL"
import json, os, sys

box = json.loads(os.environ["BOX_HEALTH"])
public = json.loads(os.environ["PUBLIC_HEALTH"])
host, url = os.environ["SSH_HOST"], os.environ["PUBLIC_URL"]

def disk(payload):
    return (payload.get("disk") or {}).get("percentUsed")

box_disk, public_disk = disk(box), disk(public)
if box_disk is None or public_disk is None:
    print("  deep health carries no disk reading — cannot compare machines", file=sys.stderr)
    sys.exit(1)

print(f"  {host:<22} disk {box_disk}%  v{box.get('appVersion')}")
print(f"  {url:<22} disk {public_disk}%  v{public.get('appVersion')}")

if abs(float(box_disk) - float(public_disk)) > 1.0:
    print(
        f"\n  {host} reports {box_disk}% disk used; {url} reports {public_disk}%.\n"
        f"  These are different machines. Deploying here would succeed and change\n"
        f"  nothing that anybody visits.",
        file=sys.stderr,
    )
    sys.exit(1)
PYEOF
}

wait_internal_health() {
  remote "for attempt in \$(seq 1 40); do
    if health=\$(curl -fsS 'http://127.0.0.1:8899/v1/health?deep=1' 2>/dev/null); then
      printf '%s\n' \"\$health\"
      exit 0
    fi
    sleep 3
  done
  echo 'internal deep health did not become ready within 120 seconds' >&2
  exit 1"
}

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

cmd="${1:-}"
[ -n "$cmd" ] || usage 0
shift || true

case "$cmd" in
  status)
    say "Containers"
    remote "sudo docker ps --format '  {{.Names}}  {{.Image}}  {{.Status}}'"
    say "Pinned version and checked-out commit"
    echo "  STUDIOSAAS_VERSION=$(pinned_version)"
    echo "  app commit        =$(app_commit)"
    remote "sudo git -C $APP log --oneline -1 | sed 's/^/  /'"
    ;;

  verify-target)
    say "Is $SSH_HOST the machine behind $PUBLIC_URL?"
    assert_box_serves_public_url
    say "Yes — same machine"
    ;;

  health)
    say "Public deep health ($PUBLIC_URL)"
    curl -fsS --max-time 20 "$PUBLIC_URL/v1/health?deep=1" || die "public health failed"
    echo
    say "Redirect and transport"
    curl -sS -o /dev/null -w '  http  -> %{http_code} %{redirect_url}\n' --max-time 20 "${PUBLIC_URL/https:/http:}/"
    curl -sS -o /dev/null -w '  https -> %{http_code}  tls=%{ssl_verify_result} (0=ok)  proto=%{http_version}\n' --max-time 20 "$PUBLIC_URL/"
    ;;

  logs)
    compose "logs --tail ${1:-200} app"
    ;;

  ssh)
    exec ssh "$SSH_HOST"
    ;;

  deploy)
    commit="${1:-}"
    [ -n "$commit" ] || die "usage: $0 deploy <commit>"

    say "Checking this box is the one $PUBLIC_URL reaches"
    assert_box_serves_public_url

    # The commit has to be on origin before the box can check it out, and it
    # has to be the commit that was gated. Both are checked here rather than
    # discovered on the box, where the failure costs a half-finished deploy.
    git rev-parse --verify --quiet "$commit^{commit}" >/dev/null \
      || die "$commit is not a commit in this repository"
    full="$(git rev-parse "$commit^{commit}")"
    git fetch -q origin
    git merge-base --is-ancestor "$full" origin/main \
      || die "$full is not on origin/main — the box pulls from origin, so it could not check this out"

    version="$(git show "$full:VERSION" | tr -d '[:space:]')"
    [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)*$ ]] \
      || die "VERSION at $full is not a safe release identifier: $version"

    previous_commit="$(app_commit)"
    previous_version="$(pinned_version)"
    [ -n "$previous_version" ] || die "$ENV_FILE carries no STUDIOSAAS_VERSION — refusing an unrollbackable deploy"
    echo "  deploying   : ${full:0:12}  v$version"
    echo "  rolling back to: ${previous_commit:0:12}  v$previous_version"

    say "Fetching and checking out ${full:0:12}"
    remote "set -e
      sudo git -C $APP fetch --quiet origin
      sudo git -C $APP checkout --quiet --detach $full
      sudo git -C $APP rev-parse HEAD"
    landed="$(app_commit)"
    [ "$landed" = "$full" ] || die "the box is on $landed, not $full"

    say "Pinning STUDIOSAAS_VERSION=$version"
    remote "set -e
      sudo sed -i 's/^STUDIOSAAS_VERSION=.*/STUDIOSAAS_VERSION=$version/' $ENV_FILE
      sudo grep -q '^STUDIOSAAS_VERSION=$version\$' $ENV_FILE \
        || echo 'STUDIOSAAS_VERSION=$version' | sudo tee -a $ENV_FILE >/dev/null
      sudo sed -n 's/^STUDIOSAAS_VERSION=/  now: /p' $ENV_FILE"

    say "Building studiosaas:$version on the box (aarch64)"
    remote "cd $ROOT && sudo docker build -f app/deploy/aws/Dockerfile -t studiosaas:$version app/" \
      || die "image build failed — nothing was restarted, production is untouched"

    say "Starting"
    deployed=false
    started=false
    if compose "up -d"; then
      started=true
      say "Waiting for internal deep health (up to 120 seconds)"
      if wait_internal_health; then
        echo
        say "Verifying from the public edge"
        if edge=$(curl -fsS --max-time 25 "$PUBLIC_URL/v1/health?deep=1"); then
          echo "$edge"
          edge_version="$(sed -n 's/.*"appVersion"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' <<<"$edge")"
          if [ "$edge_version" != "$version" ]; then
            say "WRONG TARGET: deployed $version, but $PUBLIC_URL still reports ${edge_version:-nothing}"
            echo "  The deploy succeeded on $SSH_HOST and did not reach anybody." >&2
          elif grep -Eq '"unreadable"[[:space:]]*:[[:space:]]*0[^0-9]' <<<"$edge"; then
            deployed=true
          else
            say "THEME DRIFT: this release cannot read every live tenant's stored theme"
          fi
        fi
      fi
    fi

    if $deployed; then
      say "Deployed: ${full:0:12} as v$version"
      exit 0
    fi

    # Two different situations, and calling both "ROLLBACK FAILED" is how an
    # operator gets paged for a deploy that never touched anything. The first
    # run of this script hit the second one and said the box needed hands; the
    # box was serving normally throughout, because compose had declined to
    # parse the project and therefore stopped nothing.
    say "Restoring the checkout to ${previous_commit:0:12} (v$previous_version)"
    remote "set -e
      sudo git -C $APP checkout --quiet --detach $previous_commit
      sudo sed -i 's/^STUDIOSAAS_VERSION=.*/STUDIOSAAS_VERSION=$previous_version/' $ENV_FILE"

    if ! $started; then
      # compose never ran, so the container that was serving before is still
      # serving — untouched, not restarted, not rebuilt.
      say "Nothing was restarted: production is still on v$previous_version and was never interrupted"
      curl -sS -o /dev/null -w '  %{http_code} from %{url_effective}\n' --max-time 20 "$PUBLIC_URL/v1/health" || true
      exit 1
    fi

    say "The new release was started and failed verification — rolling it back"
    compose "up -d" || die "ROLLBACK FAILED — the box needs hands"
    if wait_internal_health >/dev/null; then
      say "Rolled back to v$previous_version"
    else
      die "ROLLBACK did not come up healthy — the box needs hands"
    fi
    exit 1
    ;;

  *)
    die "unknown command: $cmd (run with no arguments for usage)"
    ;;
esac
