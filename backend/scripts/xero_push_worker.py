#!/usr/bin/env python3
"""Consume the Xero push queue for every tenant whose gate is open.

Runs from a systemd timer (deploy/aws/xero-push.timer) inside the app
container — the single-instance answer to "who delivers the queue" that the
audit plan chose over Redis/Celery. Also safe to run by hand; every line it
prints is the observability.

    docker compose exec -T app python backend/scripts/xero_push_worker.py

Per tenant: bind the RLS session, check the gate (push enabled, transport
present, connected), drain due jobs with the same classification the
in-request button uses. A tenant whose gate is closed is skipped silently —
that is the gate working, not an error. Exit code 0 unless the run itself
could not happen (no database, bad credentials): per-job failures are data,
recorded on their rows and surfaced in the studio's own error queue.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studiosaas.db import connect, fetch_all  # noqa: E402
from studiosaas.services import xero as xero_gate  # noqa: E402
from studiosaas.services import xero_transport as transport  # noqa: E402
from studiosaas.tenant_context import bind_tenant_session  # noqa: E402


def main() -> int:
    drained = skipped = failed_tenants = 0
    with connect() as conn:
        tenants = fetch_all(conn, "SELECT id, slug FROM tenants ORDER BY slug", ())
        for tenant in tenants:
            tenant_id = str(tenant["id"])
            bind_tenant_session(conn, tenant_id)
            status = xero_gate.gate_status(conn, tenant_id)
            if not (status.push_enabled and status.transport_available and status.connected):
                skipped += 1
                continue
            try:
                result = transport.drain(conn, tenant_id, limit=50)
                conn.commit()
            except transport.TransportError as exc:
                # Connection-level failure (org gone, token dead). The card
                # in the studio's own UI already explains it; log and move on.
                conn.rollback()
                failed_tenants += 1
                print(f"[{tenant['slug']}] drain refused: {exc}")
                continue
            if result["processed"]:
                drained += result["processed"]
                print(
                    f"[{tenant['slug']}] processed={result['processed']} "
                    f"sent={result['sent']} failed={result['failed']} "
                    f"deferred={result['deferred']}"
                )
    print(f"xero-push: tenants={len(tenants)} gate-closed={skipped} "
          f"jobs={drained} tenant-errors={failed_tenants}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
