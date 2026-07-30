#!/usr/bin/env bash
# Operate the live pwestudio.online instance from a development machine.
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
#   drill             Rehearse a restore into a throwaway database. Safe.
#   backups           List what is on disk with sizes and ages.
#   certs             Certificate names, domains, expiry, and the renew timer.
#   deploy <tarball>  Upload a release bundle, switch `current`, rebuild, verify,
#                     and roll back automatically if deep health fails.
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

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

cmd="${1:-}"
[ -n "$cmd" ] || usage 0
shift || true

case "$cmd" in
  status)
    ctl status
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

    say "Backing up before touching anything"
    ctl backup >/dev/null
    previous="$(remote "readlink -f $CURRENT")"
    echo "  current release: $previous"

    say "Uploading $base"
    scp -q "$tarball" "$SSH_HOST:/opt/pwestudio/shared/incoming/$base"

    # docker-compose.yml tags the image `studiosaas:${STUDIOSAAS_VERSION}`, and
    # that variable lives in the shared env file, which deliberately survives a
    # release. Nothing used to update it, so deploying 8.1.0 produced an image
    # tagged `studiosaas:8.0.1` running an app that reports 8.1.0 — `docker
    # images` lies to whoever is diagnosing an incident, and the tag stops being
    # a usable rollback point because every release overwrites the same one.
    version="$(tar xzOf "$tarball" "$name/BUILD_INFO" | sed -n 's/^version=//p')"
    [ -n "$version" ] || die "BUILD_INFO carries no version"
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
    if remote "cd $CURRENT && bash deploy/aws/lightsail_ctl.sh up"; then
      sleep 12
      if remote "curl -fsS 'http://127.0.0.1:8899/v1/health?deep=1'"; then
        echo
        say "Deep health passed — verifying from the public edge"
        curl -fsS --max-time 25 "$PUBLIC_URL/v1/health?deep=1" && echo
        say "Deployed: $name"
        exit 0
      fi
    fi

    say "Deep health FAILED — rolling back to $previous"
    remote "set -e
      ln -sfn '$previous' $CURRENT
      cd $CURRENT && bash deploy/aws/lightsail_ctl.sh up" || true
    sleep 12
    remote "curl -fsS 'http://127.0.0.1:8899/v1/health?deep=1'" \
      && { echo; die "rolled back to $previous, which is healthy. Investigate $name before retrying."; } \
      || die "ROLLBACK ALSO UNHEALTHY. Check: ssh $SSH_HOST 'cd $CURRENT && bash deploy/aws/lightsail_ctl.sh logs'"
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
