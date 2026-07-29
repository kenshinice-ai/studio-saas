# Portable Online Runtime

Status: local/Pilot demonstration only  
Launcher: `START_STUDIOSAAS_ONLINE.command`

## Contract

The launcher derives `PROJECT_ROOT` from its own location. Every mutable file
needed by the local application and Cloudflare connector is under:

```text
.runtime/
├── online.env
├── database/
│   ├── studiosaas-portable.snapshot
│   └── active-session.json
├── cloudflare/
│   └── tunnel-credentials.json
├── cms-data/
├── credentials/
└── logs/
```

The directory is ignored by Git because it contains secrets and local runtime
state. Moving or copying the complete project folder in Finder preserves this
hidden directory. Do not copy only the visible source files.

The launcher fails explicitly when `online.env`, the Tunnel name or the
project-local Tunnel credential JSON is missing. It does not search the user
home directory and does not select an arbitrary credential file.

## Single-writer database handoff

For two Macs that run the pilot one at a time, set this in `online.env`:

```text
STUDIOSAAS_DATABASE_MODE=portable
```

Remove `STUDIOSAAS_DATABASE_URL` in portable mode. Each Mac uses its own
Homebrew PostgreSQL service and current macOS username. The launcher restores
the last verified snapshot before migrations and acquires
`database/active-session.json`. On shutdown it writes one atomic snapshot
archive containing a custom-format dump and a manifest with SHA-256, migration
inventory and critical table counts. The complete archive replaces the prior
snapshot only after validation, so a mid-export interruption leaves the prior
good snapshot intact. The lease is released only after the replacement passes
verification.

The project `.venv` may also arrive through iCloud. If that Python environment
cannot run on the current Mac because its Homebrew path or CPU architecture is
different, startup explicitly rebuilds it with the current Mac's `python3`
before installing requirements.

The operating sequence is strict:

1. Start on Mac A and make changes.
2. Use `STOP_STUDIOSAAS_ONLINE.command` or close the launcher window.
3. Wait for `portable database handoff completed`, then wait for iCloud to
   finish syncing the project folder.
4. Start on Mac B.

Never start both Macs together. Never copy or sync a live PostgreSQL data
directory. If a Mac crashed and left a stale lease, first prove StudioSaaS is
stopped on that Mac, then run:

```bash
cd "/path/to/studiosaas"
.venv/bin/python backend/scripts/portable_database_handoff.py recover \
  --lease .runtime/database/active-session.json \
  --confirm OTHER-DEVICE-IS-STOPPED
```

Recovery removes only the stale lease; it does not modify the last verified
snapshot. A failed shutdown export deliberately keeps the lease so another Mac
cannot silently restore stale data.

## Start and stop

Double-click:

- `START_STUDIOSAAS_ONLINE.command`
- `STOP_STUDIOSAAS_ONLINE.command`

Or run them from Terminal. The current working directory does not matter.

Startup performs migrations, verifies the existing platform administrator
without resetting its password, starts the application and Tunnel, then
requires local/public version, mode and database parity.

## Password lifecycle

Service startup never changes application passwords. The controlled local
demonstration currently uses one operator-selected shared password. A password
change is an explicit maintenance action through
`backend/scripts/set_local_demo_passwords.py`, not an automatic restart step.

This policy must not be carried into AWS production. Production requires unique
privileged credentials, MFA, managed secrets and an audited rotation process.

## External service boundary

Portability covers files, paths and verified single-writer database snapshots.
The target Mac still requires the system programs installed by the launcher.
Moving the folder does not copy a running PostgreSQL server or change
Cloudflare DNS ownership.
