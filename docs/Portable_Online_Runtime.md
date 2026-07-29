# Portable Online Runtime

Status: local/Pilot demonstration only  
Launcher: `START_STUDIOSAAS_ONLINE.command`

## Contract

The launcher derives `PROJECT_ROOT` from its own location. Every mutable file
needed by the local application and Cloudflare connector is under:

```text
.runtime/
├── online.env
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

Portability covers files and paths. The target Mac still requires the system
programs installed by the launcher and access to the PostgreSQL service named
in `.runtime/online.env`. Moving the folder does not copy a running PostgreSQL
server or change Cloudflare DNS ownership.
