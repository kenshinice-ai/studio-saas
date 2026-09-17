#!/usr/bin/env bash
# Operate the pwestudio.online instance from a development machine.
#
# 2026-09-17: production moved to an Oracle ARM box behind Caddy and
# Cloudflare, and the OLD Lightsail instance is still running. The alias below
# still points at the old one. Every command here that only reads is harmless
# against either; `deploy` now proves the target is the machine
# pwestudio.online actually reaches before it uploads anything, and asserts the
# public edge reports the version just built afterwards. Run `verify-target` if
# you want that answer without deploying. The Oracle procedure is in
# ~/Documents/ClaudeCode/oracle-a1-grab/DEPLOY-PWESTUDIO-LETSPAINT.md — it
# builds on the box from a commit, not from a bundle.
#
#   bash deploy/aws/pwestudio_remote.sh <command>
#
# This is the thin half of the pair: it only knows how to reach the host and
# which command to run there. Everything that touches production data lives in
# deploy/aws/lightsail_ctl.sh ON the instance, so the two cannot drift and a
# laptop is never the source of truth for a production procedure.
#
# It holds NO credentials. The SSH identity comes from ~/.ssh/config:
#
#   Host pwestudio
#     HostName 13.237.190.58
#     User ubuntu
#     IdentityFile ~/.ssh/pwestudio-lightsail.pem
#     IdentitiesOnly yes
#     ServerAliveInterval 60
#
# Override the alias with PWESTUDIO_SSH_HOST=<other-alias> for a rehearsal host.
#
# Commands
#   status            Containers plus deep health. Start here.
#   health            Public HTTPS deep health, from your machine, not the box.
#   logs [n]          Last n lines (default 200) of app and database logs.
#   backup            Logical dump + volume tarball, now.
#   prune [--dry-run] Apply event-table retention (audit 730d, analytics 365d).
#   prune-artifacts   Release directories, uploaded bundles, image tags, build cache.
#   disk              Disk headroom; non-zero exit past the warning threshold.
#   drill             Rehearse a restore into a throwaway database. Safe.
#   backups           List what is on disk with sizes and ages.
#   certs             Certificate names, domains, expiry, and the renew timer.
#   deploy <tarball>  Upload a release bundle, switch `current`, rebuild, verify,
#                     and roll back automatically if deep health fails.
#   verify-target     Prove the box this script targets is the one $PUBLIC_URL
#                     reaches. Changes nothing. Run it when in doubt.
#   ssh               Interactive shell on the instance.
#
# Deliberately absent: any command that removes a volume, drops a database, or
# performs a real restore. Those exist on the instance where the operator can
# read the confirmation prompt in context.

set -euo pipefail

SSH_HOST="${PWESTUDIO_SSH_HOST:-pwestudio}"
RELEASES="/opt/pwestudio/releases"
CURRENT="/opt/pwestudio/current"
PUBLIC_URL="${PWESTUDIO_PUBLIC_URL:-https://pwestudio.online}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

remote() { ssh -o ConnectTimeout=15 "$SSH_HOST" "$@"; }
ctl()    { remote "cd $CURRENT && bash deploy/aws/lightsail_ctl.sh $*"; }

wait_internal_health() {
  # Migrations, workspace regeneration and first-time media derivatives can
  # legitimately outlive a fixed sleep. Poll the actual readiness contract for
  # up to 90 seconds; a single connection reset while Waitress is starting is
  # not deployment failure.
  remote "for attempt in \$(seq 1 30); do
    if health=\$(curl -fsS 'http://127.0.0.1:8899/v1/health?deep=1' 2>/dev/null); then
      printf '%s\n' \"\$health\"
      exit 0
    fi
    sleep 3
  done
  echo 'internal deep health did not become ready within 90 seconds' >&2
  exit 1"
}

# ── does this box actually serve $PUBLIC_URL? ────────────────────────────────
#
# 2026-09-17: production moved from AWS Lightsail to an Oracle ARM box behind
# Cloudflare and Caddy, and the OLD machine is still running. `~/.ssh/config`
# still resolves the alias this script defaults to (`pwestudio`) to the old
# one. Nothing in this script noticed: it would deploy, the box would come up
# healthy, the public-edge check below would `curl $PUBLIC_URL` and get a 200
# from the OTHER machine, and the release would report success with production
# untouched. The three-way commit guard cannot catch it either — it compares
# commits, not machines.
#
# Two boxes running the same release are identical in everything the app says
# about itself, so content cannot tell them apart. Only machine state can, and
# disk usage is the one machine fact the deep health payload always carries.
#
# This is an EARLY WARNING, deliberately cheap and deliberately before the
# upload. The PROOF is the post-deploy assertion that the public edge reports
# the version we just shipped: at that moment the version is new and exists
# nowhere else, so a mismatch there is unambiguous. Both are needed — this one
# so the failure arrives before anything has moved, that one so no future
# migration can slip through a heuristic.
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
    print(f"  deep health carries no disk reading — cannot compare machines", file=sys.stderr)
    sys.exit(1)

print(f"  {host:<22} disk {box_disk}%  v{box.get('appVersion')}")
print(f"  {url:<22} disk {public_disk}%  v{public.get('appVersion')}")

# A percentage point of drift between two reads seconds apart is generous; two
# different machines are not within one point of each other by accident.
if abs(float(box_disk) - float(public_disk)) > 1.0:
    print(
        f"\n  {host} reports {box_disk}% disk used; {url} reports {public_disk}%.\n"
        f"  These are different machines. Deploying here would succeed and change\n"
        f"  nothing that anybody visits.\n\n"
        f"  If production has moved, this script is not the way to deploy to it —\n"
        f"  see docs/Release_Runbook.md, step 8.",
        file=sys.stderr,
    )
    sys.exit(1)
PYEOF
}

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

cmd="${1:-}"
[ -n "$cmd" ] || usage 0
shift || true

case "$cmd" in
  status)
    ctl status
    ;;

  verify-target)
    # Answers one question without changing anything: is the box this script is
    # pointed at the box $PUBLIC_URL actually reaches? Run it any time the
    # answer is in doubt — after a migration, after an ssh config edit, or
    # before trusting a deploy that "succeeded".
    say "Is $SSH_HOST the machine behind $PUBLIC_URL?"
    assert_box_serves_public_url
    say "Yes — same machine"
    ;;

  health)
    # From here, not from the box: this is the only check that also proves DNS,
    # the certificate and nginx, which a curl on localhost cannot.
    say "Public deep health ($PUBLIC_URL)"
    curl -fsS --max-time 20 "$PUBLIC_URL/v1/health?deep=1" || die "public health failed"
    echo
    say "Redirect and transport"
    curl -sS -o /dev/null -w '  http  -> %{http_code} %{redirect_url}\n' --max-time 20 "${PUBLIC_URL/https:/http:}/"
    curl -sS -o /dev/null -w '  https -> %{http_code}  tls=%{ssl_verify_result} (0=ok)  proto=%{http_version}\n' --max-time 20 "$PUBLIC_URL/"
    ;;

  logs)
    ctl "logs" | tail -n "${1:-200}"
    ;;

  backup)
    ctl backup
    ;;

  prune)
    ctl "prune ${*:-}"
    ;;

  prune-artifacts)
    ctl "prune-artifacts ${*:-}"
    ;;

  disk)
    ctl disk
    ;;

  drill)
    ctl "restore-dry-run ${*:-}"
    ;;

  backups)
    say "Logical dumps"
    remote "ls -lht /opt/pwestudio/backups/postgres/ | head -12"
    say "Volume archives"
    remote "sudo ls -lht /opt/pwestudio/backups/volumes/ | head -6"
    say "Last cron run"
    remote "sudo tail -5 /var/log/pwestudio-backup.log 2>/dev/null || echo '(no cron output yet)'"
    ;;

  certs)
    remote "sudo certbot certificates 2>/dev/null | grep -E 'Certificate Name|Domains|Expiry'"
    remote "systemctl list-timers certbot.timer --all | head -3"
    ;;

  deploy)
    tarball="${1:-}"
    [ -n "$tarball" ] || die "usage: $0 deploy <PWE-StudioSaaS-aws-<ver>.tar.gz>"
    [ -f "$tarball" ] || die "not found: $tarball"
    base="$(basename "$tarball")"
    name="${base%.tar.gz}"

    say "Verifying the bundle is a SaaS build before it leaves this machine"
    # A mode=standalone tarball on the SaaS host would refuse to boot after the
    # symlink already moved. Check on the laptop, where it costs nothing.
    if ! tar xzOf "$tarball" "$name/BUILD_INFO" 2>/dev/null | grep -qx 'mode=saas'; then
      die "$base is not mode=saas — refusing to deploy it to the SaaS host"
    fi
    tar xzOf "$tarball" "$name/BUILD_INFO" | sed 's/^/  /'

    say "Checking this box is the one $PUBLIC_URL reaches"
    assert_box_serves_public_url

    previous="$(remote "readlink -f $CURRENT")"
    previous_version="$(remote "sudo sed -n 's/^STUDIOSAAS_VERSION=//p' /opt/pwestudio/shared/production.env | tail -1")"
    [ -n "$previous_version" ] || die "production.env carries no current STUDIOSAAS_VERSION — refusing an unrollbackable deploy"
    [[ "$previous_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)*$ ]] \
      || die "production.env carries an unsafe STUDIOSAAS_VERSION: $previous_version"
    echo "  current release: $previous"
    echo "  current version: $previous_version"

    say "Uploading $base"
    scp -q "$tarball" "$SSH_HOST:/opt/pwestudio/shared/incoming/$base"

    # The currently running release may not know how to back up a newly added
    # FORCE-RLS table. Stage the candidate first, but do not move `current`; run
    # its controller against the unchanged Compose project so the pre-switch
    # backup uses the candidate's owner-role backup fix. If staging or backup
    # fails, production is still on the previous symlink and version.
    say "Staging candidate backup controller"
    remote "set -e
      cd $RELEASES
      rm -rf '$name'
      tar xzf /opt/pwestudio/shared/incoming/$base --exclude='._*'
      cd $RELEASES/$name
      bash deploy/aws/lightsail_ctl.sh backup >/dev/null"

    # docker-compose.yml tags the image `studiosaas:${STUDIOSAAS_VERSION}`, and
    # that variable lives in the shared env file, which deliberately survives a
    # release. Nothing used to update it, so deploying 8.1.0 produced an image
    # tagged `studiosaas:8.0.1` running an app that reports 8.1.0 — `docker
    # images` lies to whoever is diagnosing an incident, and the tag stops being
    # a usable rollback point because every release overwrites the same one.
    version="$(tar xzOf "$tarball" "$name/BUILD_INFO" | sed -n 's/^version=//p')"
    [ -n "$version" ] || die "BUILD_INFO carries no version"
    [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)*$ ]] \
      || die "BUILD_INFO version is not a safe release identifier: $version"
    say "Pinning STUDIOSAAS_VERSION=$version in the shared environment"
    remote "set -e
      sudo sed -i 's/^STUDIOSAAS_VERSION=.*/STUDIOSAAS_VERSION=$version/' /opt/pwestudio/shared/production.env
      grep -q '^STUDIOSAAS_VERSION=$version\$' /opt/pwestudio/shared/production.env \
        || echo 'STUDIOSAAS_VERSION=$version' | sudo tee -a /opt/pwestudio/shared/production.env >/dev/null
      sudo sed -n 's/^STUDIOSAAS_VERSION=/  now: /p' /opt/pwestudio/shared/production.env"

    say "Unpacking and switching the current symlink"
    remote "set -e
      cd $RELEASES
      rm -rf '$name'
      # COPYFILE_DISABLE at build time keeps AppleDouble out, but a bundle built
      # elsewhere may still carry ._* entries that break the migration runner.
      tar xzf /opt/pwestudio/shared/incoming/$base --exclude='._*'
      ln -sfn $RELEASES/$name $CURRENT
      readlink -f $CURRENT"

    say "Rebuilding and starting"
    deployed=false
    if remote "cd $CURRENT && bash deploy/aws/lightsail_ctl.sh up"; then
      say "Waiting for internal deep health (up to 90 seconds)"
      if wait_internal_health; then
        echo
        say "Deep health passed — verifying from the public edge"
        if edge=$(curl -fsS --max-time 25 "$PUBLIC_URL/v1/health?deep=1"); then
          echo "$edge"
          # The exact one. `$version` was just built and exists nowhere else,
          # so if the public edge does not report it, whatever we deployed to
          # is not what the public URL reaches. This check used to be absent:
          # the edge only had to return 200, which it does from any healthy
          # machine serving that domain — including one we did not touch.
          edge_version="$(sed -n 's/.*"appVersion"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' <<<"$edge")"
          if [ "$edge_version" != "$version" ]; then
            say "WRONG TARGET: deployed $version, but $PUBLIC_URL still reports ${edge_version:-nothing}"
            echo "  The deploy succeeded on $SSH_HOST and did not reach anybody." >&2
            echo "  See docs/Release_Runbook.md, step 8." >&2
            deployed=false
            edge=""
          fi
        fi
        if [ -n "$edge" ]; then
          # A green health check is not the same as a rendered tenant.
          #
          # v8.5.2 retired one visual style id. Every check above passed, the
          # rollback window closed, and five of six live portals were serving
          # 500 for their whole content payload the entire time. So the gate
          # now asks the release a question about the DATA it inherited: can
          # you still read every live tenant's stored theme?
          #
          # `unreadable` counts the ones this release would reject. Non-zero
          # means a contract changed under live rows — roll back, add the
          # alias (presets.RETIRED_STYLE_ALIASES), redeploy.
          # Whitespace-tolerant: Flask's JSON separators are not a contract.
          if grep -Eq '"unreadable"[[:space:]]*:[[:space:]]*0[^0-9]' <<<"$edge"; then
            deployed=true
          else
            say "THEME DRIFT: this release cannot read every live tenant's stored theme"
          fi
        fi
      fi
    fi
    if $deployed; then
      # Only after the new release is confirmed healthy, so a rollback never
      # races the cleanup for the directory it needs.
      say "Pruning superseded release artefacts"
      remote "cd $CURRENT && bash deploy/aws/lightsail_ctl.sh prune-artifacts" || \
        echo "  (prune failed; deployment itself is fine — run prune-artifacts by hand)"
      say "Deployed: $name"
      exit 0
    fi

    say "Deployment verification FAILED — rolling back to $previous (version $previous_version)"
    if ! remote "set -e
      ln -sfn '$previous' $CURRENT
      if grep -q '^STUDIOSAAS_VERSION=' /opt/pwestudio/shared/production.env; then
        sudo sed -i 's/^STUDIOSAAS_VERSION=.*/STUDIOSAAS_VERSION=$previous_version/' /opt/pwestudio/shared/production.env
      else
        echo 'STUDIOSAAS_VERSION=$previous_version' | sudo tee -a /opt/pwestudio/shared/production.env >/dev/null
      fi
      grep -q '^STUDIOSAAS_VERSION=$previous_version\$' /opt/pwestudio/shared/production.env
      cd $CURRENT && bash deploy/aws/lightsail_ctl.sh up"
    then
      die "ROLLBACK START FAILED. Check: ssh $SSH_HOST 'cd $CURRENT && bash deploy/aws/lightsail_ctl.sh logs'"
    fi
    if ! wait_internal_health; then
      die "ROLLBACK INTERNAL HEALTH FAILED. Check: ssh $SSH_HOST 'cd $CURRENT && bash deploy/aws/lightsail_ctl.sh logs'"
    fi
    echo
    if ! curl -fsS --max-time 25 "$PUBLIC_URL/v1/health?deep=1"; then
      die "ROLLBACK PUBLIC EDGE HEALTH FAILED. Internal health passed; check nginx, DNS and TLS immediately."
    fi
    echo
    die "rolled back to $previous (version $previous_version), healthy internally and publicly. Investigate $name before retrying."
    ;;

  ssh)
    exec ssh "$SSH_HOST"
    ;;

  -h|--help)
    usage 0
    ;;

  *)
    die "unknown command: $cmd (see --help)"
    ;;
esac
