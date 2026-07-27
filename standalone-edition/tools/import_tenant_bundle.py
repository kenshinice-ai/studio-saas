#!/usr/bin/env python3
"""Import a PWE Studio Edition delivery bundle into a FRESH standalone database.

Edition-side half of the SaaS → Edition migration path (DATABASE.md §2 路径 1).
Consumes the tar.gz produced by ``export_tenant_bundle.py``. The target
database must already have every migration from the bundle applied and must
contain ZERO tenants and ZERO users (a fresh install) — anything else is
refused, because the Edition invariant is "exactly one tenant, created at
install time".

Original UUIDs are preserved (identical schema → direct INSERT). Platform
membership rows (tenant_id IS NULL) are stripped if a bundle ever carries
them. References to platform users that are not part of the bundle (e.g. a
support-mode super admin in audit rows) are nulled out and counted. Imported
users get fresh random unusable passwords — the delivery engineer issues real
credentials during handover.

Usage:
    python standalone-edition/tools/import_tenant_bundle.py bundle.tar.gz            # preview
    python standalone-edition/tools/import_tenant_bundle.py bundle.tar.gz \
        --confirm-fresh-db [--media-dir PATH]                                        # apply

Requires STUDIOSAAS_DATABASE_URL (see studiosaas.db).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import sys
import tarfile
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.auth import hash_password  # noqa: E402
from studiosaas.db import connect, fetch_all, fetch_one  # noqa: E402
# Single source of truth for the table inventory — do NOT copy the list here.
from studiosaas.services.tenant_archive import SNAPSHOT_TABLES  # noqa: E402

# FK-safe load order, derived from backend/db/schema_v1.sql:
#   tenants ← everything; users ← memberships/tokens/actor columns;
#   courses ← packages/class_schedules/credit_accounts/attendance;
#   students ← accounts/attendance/roster/consent/portfolio/media owner;
#   registrations ← student_publication_consent_events.source_registration_id;
#   media_assets ← portfolio_items/media_variants and the deferred
#   students.student_photo_asset_id back-reference (circular with
#   media_assets.owner_student_id — resolved by a post-insert patch);
#   credit_transactions ← attendance_sessions.credit_transaction_id;
#   portfolio_items ← share_tokens.
# Self-references (registrations.duplicate_of_registration_id,
# tenant_brand_versions.source_version_id) are also deferred and patched.
IMPORT_ORDER: tuple[str, ...] = (
    "tenant.json",
    "users.json",
    "memberships.json",
    "password_setup_tokens.json",
    "courses.json",
    "packages.json",
    "class_schedules.json",
    "students.json",
    "registrations.json",
    "media_assets.json",
    "credit_accounts.json",
    "credit_transactions.json",
    "attendance_sessions.json",
    "class_schedule_students.json",
    "portfolio_items.json",
    "share_tokens.json",
    "media_variants.json",
    "daily_roster_entries.json",
    "student_access_sessions.json",
    "student_access_attempts.json",
    "student_publication_consent_events.json",
    "email_templates.json",
    "notification_logs.json",
    "audit_logs.json",
    "subscriptions.json",
    "tenant_usage.json",
    "tenant_brand_drafts.json",
    "tenant_brand_versions.json",
    "tenant_archives.json",
    "public_analytics_events.json",
)

# Columns whose FK targets are inserted later (or reference the row's own
# table): stripped at INSERT time, restored by UPDATE patches afterwards.
DEFERRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "students": ("student_photo_asset_id",),
    "registrations": ("duplicate_of_registration_id",),
    "tenant_brand_versions": ("source_version_id",),
}


class ImportError_(RuntimeError):
    """Raised when the bundle cannot be imported safely."""


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(bundle: Path, target: Path) -> Path:
    """Extract the tarball defensively and return the bundle root directory."""

    with tarfile.open(bundle, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ImportError_(f"Unsafe path in bundle: {member.name}")
            if member.issym() or member.islnk():
                raise ImportError_(f"Links are not allowed in bundles: {member.name}")
        try:
            tar.extractall(target, filter="data")
        except TypeError:  # Python < 3.11.4 without extraction filters
            tar.extractall(target)

    manifests = sorted(target.glob("*/manifest.json")) or sorted(target.glob("manifest.json"))
    if not manifests:
        raise ImportError_("Bundle has no manifest.json.")
    return manifests[0].parent


def _load_manifest(root: Path) -> dict[str, Any]:
    """Load and structurally validate the bundle manifest."""

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "pwe-studio-edition-bundle":
        raise ImportError_(f"Unsupported bundle format: {manifest.get('format')!r}")
    for key in ("tenant", "tables", "ledger", "schema_migrations", "files"):
        if key not in manifest:
            raise ImportError_(f"Manifest is missing required key: {key}")
    return manifest


def _verify_file_hashes(root: Path, manifest: dict[str, Any]) -> None:
    """Verify the sha256 of every snapshot file against the manifest."""

    for rel_path, expected in sorted(manifest["files"].items()):
        actual = _sha256_file(root / rel_path)
        if actual != expected:
            raise ImportError_(f"Checksum mismatch for {rel_path}: {actual} != {expected}")


def _check_preconditions(conn: Any, manifest: dict[str, Any]) -> list[str]:
    """Enforce the fresh-database contract; return non-fatal warnings."""

    warnings: list[str] = []
    try:
        applied = {
            row["version"]
            for row in fetch_all(conn, "SELECT version FROM schema_migrations", ())
        }
    except Exception as exc:  # table missing → migrations never ran
        raise ImportError_(
            "Target database has no schema_migrations table. "
            "Run backend/scripts/run_migrations.py first."
        ) from exc

    missing = [v for v in manifest["schema_migrations"] if v not in applied]
    if missing:
        raise ImportError_(
            "Target database is missing migrations required by the bundle: "
            + ", ".join(missing)
        )
    extra = sorted(applied - set(manifest["schema_migrations"]))
    if extra:
        warnings.append(
            "Target schema is NEWER than the bundle (extra migrations: "
            + ", ".join(extra)
            + "). Direct insert still works while migrations stay additive."
        )

    tenants = fetch_one(conn, "SELECT count(*) AS n FROM tenants", ())
    if int(tenants["n"]) != 0:
        raise ImportError_(
            f"Target database already has {tenants['n']} tenant(s). "
            "Edition import requires a FRESH database (exactly zero tenants)."
        )
    users = fetch_one(conn, "SELECT count(*) AS n FROM users", ())
    if int(users["n"]) != 0:
        raise ImportError_(
            f"Target database already has {users['n']} user(s). "
            "Edition import requires a fresh database with no accounts."
        )
    return warnings


def _column_types(conn: Any, table: str) -> dict[str, str]:
    """Return column → cast expression for one table (explicit, no guessing)."""

    rows = fetch_all(
        conn,
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    if not rows:
        raise ImportError_(f"Table does not exist in target database: {table}")
    casts: dict[str, str] = {}
    for row in rows:
        if row["data_type"] == "ARRAY":
            casts[row["column_name"]] = row["udt_name"].lstrip("_") + "[]"
        else:
            casts[row["column_name"]] = row["udt_name"]
    return casts


def _user_fk_columns(conn: Any) -> dict[str, list[tuple[str, bool]]]:
    """Map table → [(column, is_nullable)] for every FK that targets users(id)."""

    rows = fetch_all(
        conn,
        """
        SELECT c.conrelid::regclass::text AS table_name,
               a.attname AS column_name,
               NOT a.attnotnull AS is_nullable
        FROM pg_constraint c
        JOIN LATERAL unnest(c.conkey) AS k(attnum) ON true
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
        WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass
        """,
        (),
    )
    mapping: dict[str, list[tuple[str, bool]]] = {}
    for row in rows:
        mapping.setdefault(row["table_name"], []).append(
            (row["column_name"], bool(row["is_nullable"]))
        )
    return mapping


def _adapt_value(value: Any, cast: str) -> Any:
    """Prepare one JSON-decoded value for a typed INSERT parameter."""

    if value is None:
        return None
    if cast in ("json", "jsonb"):
        from psycopg.types.json import Json

        return Json(value)
    return value


def _insert_rows(
    cur: Any,
    table: str,
    rows: list[dict[str, Any]],
    casts: dict[str, str],
    deferred: tuple[str, ...] = (),
) -> list[tuple[str, str, Any]]:
    """Insert snapshot rows with explicit casts; return deferred patches."""

    patches: list[tuple[str, str, Any]] = []
    for raw in rows:
        row = dict(raw)
        for column in deferred:
            value = row.get(column)
            if value is not None:
                patches.append((str(row["id"]), column, value))
            row[column] = None
        columns = [c for c in row.keys() if c in casts]
        unknown = sorted(set(row) - set(columns))
        if unknown:
            raise ImportError_(
                f"Bundle column(s) {unknown} do not exist in target table {table}. "
                "Schema drift — align versions before importing."
            )
        placeholders = ", ".join(f"%s::{casts[c]}" for c in columns)
        cur.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [_adapt_value(row[c], casts[c]) for c in columns],
        )
    return patches


def _null_unknown_user_refs(
    rows: list[dict[str, Any]],
    table: str,
    user_fk_map: dict[str, list[tuple[str, bool]]],
    known_users: set[str],
    stats: dict[str, int],
) -> list[dict[str, Any]]:
    """Null (or drop) references to platform users that are not in the bundle."""

    kept: list[dict[str, Any]] = []
    for row in rows:
        drop_row = False
        for column, is_nullable in user_fk_map.get(table, []):
            value = row.get(column)
            if value is None or str(value) in known_users:
                continue
            if is_nullable:
                row[column] = None
                stats["nulled_user_refs"] += 1
            else:
                drop_row = True
                stats["dropped_rows_unknown_user"] += 1
                break
        if not drop_row:
            kept.append(row)
    return kept


def _ensure_plans(cur: Any, plan_codes: set[str]) -> list[str]:
    """Create unlimited Edition plan rows for any missing plan codes."""

    created: list[str] = []
    for code in sorted(c for c in plan_codes if c):
        cur.execute("SELECT 1 FROM plans WHERE code = %s", (code,))
        if cur.fetchone():
            continue
        # Standalone edition has no commercial plan limits (DATABASE.md §1):
        # one row with effectively-unlimited caps satisfies the FK and any
        # residual limit checks.
        cur.execute(
            """
            INSERT INTO plans (
                code, name, monthly_price_aud, student_limit, user_limit,
                storage_limit_mb, features
            )
            VALUES (%s, %s, 0, 1000000, 1000000, 1048576, '{}'::jsonb)
            """,
            (code, f"PWE Studio Edition ({code}, unlimited)"),
        )
        created.append(code)
    return created


def _copy_media(bundle_root: Path, media_dir: Path) -> int:
    """Unpack the bundle media tree into the Edition media directory."""

    source = bundle_root / "media"
    if not source.is_dir():
        return 0
    count = 0
    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(source)
        dest = media_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
        count += 1
    return count


def _print_reconciliation(
    manifest: dict[str, Any],
    imported_counts: dict[str, int],
    db_ledger: dict[str, str],
    stats: dict[str, int],
    bundle_sha: str,
    media_files: int,
    warnings: list[str],
    status_note: str,
) -> bool:
    """Print the 验收对账单 block; return True when every check passes."""

    tenant = manifest["tenant"]
    ok = True
    print("=" * 72)
    print("验收对账单 (Acceptance Reconciliation)")
    print("=" * 72)
    print(f"来源租户   : {tenant['name']} ({tenant['slug']})  id={tenant['id']}")
    print(f"导出时间   : {manifest.get('created_at', 'unknown')}")
    print(f"来源版本   : {manifest.get('source_app_version', 'unknown')}")
    print(f"包 SHA-256 : {bundle_sha}")
    print("-" * 72)
    print(f"{'快照文件':<44}{'包内':>8}{'已导入':>8}{'核对':>6}")
    for filename in IMPORT_ORDER:
        expected = int(manifest["tables"].get(filename, {}).get("rows", 0))
        if filename == "memberships.json":
            expected -= stats["stripped_platform_memberships"]
        expected -= stats.get(f"dropped:{filename}", 0)
        actual = imported_counts.get(filename, 0)
        mark = "✓" if actual == expected else "✗"
        if mark == "✗":
            ok = False
        print(f"{filename:<44}{expected:>8}{actual:>8}{mark:>6}")
    print("-" * 72)
    for label, key in (
        ("课时账本余额合计 (credit_accounts.balance)", "credit_accounts_balance_total"),
        ("流水金额合计 (credit_transactions.amount)", "credit_transactions_amount_total"),
    ):
        expected = Decimal(manifest["ledger"][key])
        actual = Decimal(db_ledger[key])
        mark = "✓" if expected == actual else "✗"
        if mark == "✗":
            ok = False
        print(f"{label}: 包内 {expected} / 导入后 {actual}  {mark}")
    print("-" * 72)
    print(f"剔除平台成员行 (tenant_id IS NULL) : {stats['stripped_platform_memberships']}")
    print(f"置空的平台用户引用                 : {stats['nulled_user_refs']}")
    print(f"因未知用户被跳过的行               : {stats['dropped_rows_unknown_user']}")
    print(f"媒体文件已落盘                     : {media_files}")
    print(f"租户状态                           : {status_note}")
    print("demo_seed_locked                   : true (防误 seed)")
    print("用户密码                           : 已重置为随机不可用值 — 交付时为 owner 重设并当场改掉")
    for warning in warnings:
        print(f"WARN: {warning}")
    print("=" * 72)
    print("导入校验通过 ✓" if ok else "导入校验失败 ✗ — 事务已回滚")
    print("=" * 72)
    return ok


def main(argv: list[str] | None = None) -> int:
    """Preview or apply an Edition bundle import into a fresh database."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--confirm-fresh-db",
        action="store_true",
        help="Actually import. Without this flag the tool only previews.",
    )
    parser.add_argument(
        "--media-dir",
        default="",
        help="Edition media root (default: $STUDIOSAAS_MEDIA_DIR or backend/media).",
    )
    args = parser.parse_args(argv)

    bundle = args.bundle.expanduser().resolve()
    if not bundle.is_file():
        raise SystemExit(f"ERROR: bundle not found: {bundle}")
    bundle_sha = _sha256_file(bundle)

    import os

    media_dir = Path(
        args.media_dir
        or os.environ.get("STUDIOSAAS_MEDIA_DIR", "").strip()
        or (BACKEND_ROOT / "media")
    ).expanduser().resolve()

    with tempfile.TemporaryDirectory(prefix="edition-import-") as tmp:
        root = _safe_extract(bundle, Path(tmp))
        manifest = _load_manifest(root)
        # A tampered or truncated bundle is an expected failure on delivery day
        # (a bad scp, an edited JSON), not a bug in this tool — report it the
        # same way as a failed precondition instead of a Python traceback in
        # front of the customer.
        try:
            _verify_file_hashes(root, manifest)
        except ImportError_ as exc:
            raise SystemExit(
                f"REFUSED: {exc}\n"
                "包内容与 manifest 校验和不一致：传输损坏或被改动过。"
                "请重新从平台侧导出并核对 SHA-256 后再传。 "
                "Bundle contents do not match the manifest checksums — re-export "
                "and verify the SHA-256 before transferring again."
            ) from exc

        snapshot_files = {filename for filename, _, _ in SNAPSHOT_TABLES}
        if set(IMPORT_ORDER) != snapshot_files:
            raise SystemExit(
                "ERROR: IMPORT_ORDER is out of sync with tenant_archive.SNAPSHOT_TABLES.\n"
                f"  missing from order: {sorted(snapshot_files - set(IMPORT_ORDER))}\n"
                f"  unknown in order:   {sorted(set(IMPORT_ORDER) - snapshot_files)}"
            )
        table_by_file = {filename: table for filename, table, _ in SNAPSHOT_TABLES}

        # Lift the app's 30s statement cap: media-heavy tenants insert a lot.
        with connect(statement_timeout_ms=0, lock_timeout_ms=0) as conn:
            try:
                warnings = _check_preconditions(conn, manifest)
            except ImportError_ as exc:
                raise SystemExit(f"REFUSED: {exc}") from exc

            if not args.confirm_fresh_db:
                total_rows = sum(int(t["rows"]) for t in manifest["tables"].values())
                print("PREVIEW ONLY — no data written. Re-run with --confirm-fresh-db to apply.")
                print(f"Bundle:  {bundle.name}  sha256={bundle_sha}")
                print(
                    f"Tenant:  {manifest['tenant']['name']} ({manifest['tenant']['slug']})"
                    f"  status={manifest['tenant']['status']}"
                )
                print(f"Tables:  {len(manifest['tables'])} files, {total_rows} rows")
                print(f"Ledger:  {manifest['ledger']}")
                print(f"Media:   {manifest.get('media', {})}")
                for warning in warnings:
                    print(f"WARN: {warning}")
                return 0

            stats = {
                "stripped_platform_memberships": 0,
                "nulled_user_refs": 0,
                "dropped_rows_unknown_user": 0,
            }
            imported_counts: dict[str, int] = {}
            user_fk_map = _user_fk_columns(conn)

            tenant_row = json.loads((root / "db" / "tenant.json").read_text(encoding="utf-8"))
            if not tenant_row:
                raise SystemExit("ERROR: bundle tenant.json is empty.")

            data_by_file: dict[str, list[dict[str, Any]]] = {"tenant.json": [tenant_row]}
            for filename in IMPORT_ORDER[1:]:
                path = root / "db" / filename
                data_by_file[filename] = (
                    json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
                )

            # Users in the bundle (the only valid user references after import).
            known_users = {str(row["id"]) for row in data_by_file["users.json"]}

            # Strip platform membership rows before any FK filtering.
            memberships = data_by_file["memberships.json"]
            tenant_scoped = [row for row in memberships if row.get("tenant_id") is not None]
            stats["stripped_platform_memberships"] = len(memberships) - len(tenant_scoped)
            data_by_file["memberships.json"] = tenant_scoped

            # Imported users cannot keep platform passwords (the export never
            # includes password_hash) — issue random unusable ones.
            for row in data_by_file["users.json"]:
                row["password_hash"] = hash_password(secrets.token_urlsafe(32))

            original_status = str(tenant_row.get("status") or "")
            if original_status != "active":
                # Edition invariant: exactly one ACTIVE tenant (README §3 方案 A).
                tenant_row["status"] = "active"
                status_note = f"active (原状态 {original_status}，安装时固化)"
            else:
                status_note = "active"

            try:
                with conn.cursor() as cur:
                    plan_codes = {str(tenant_row.get("plan_code") or "")}
                    plan_codes.update(
                        str(row.get("plan_code") or "")
                        for row in data_by_file["subscriptions.json"]
                    )
                    created_plans = _ensure_plans(cur, plan_codes)
                    if created_plans:
                        warnings.append(
                            "Created unlimited Edition plan row(s): " + ", ".join(created_plans)
                        )

                    all_patches: list[tuple[str, str, str, Any]] = []
                    for filename in IMPORT_ORDER:
                        table = table_by_file[filename]
                        rows = data_by_file[filename]
                        before = len(rows)
                        rows = _null_unknown_user_refs(
                            rows, table, user_fk_map, known_users, stats
                        )
                        dropped = before - len(rows)
                        if dropped:
                            stats[f"dropped:{filename}"] = dropped
                        casts = _column_types(conn, table)
                        patches = _insert_rows(
                            cur, table, rows, casts, DEFERRED_COLUMNS.get(table, ())
                        )
                        all_patches.extend((table, *patch) for patch in patches)
                        imported_counts[filename] = len(rows)

                    for table, row_id, column, value in all_patches:
                        cur.execute(
                            f"UPDATE {table} SET {column} = %s::uuid WHERE id = %s::uuid",
                            (value, row_id),
                        )

                    # Lock the tenant against demo seeding (DATABASE.md §4).
                    cur.execute(
                        """
                        UPDATE tenants
                        SET settings = jsonb_set(COALESCE(settings, '{}'::jsonb),
                                                 '{demo_seed_locked}', 'true'::jsonb, true),
                            updated_at = now()
                        WHERE id = %s::uuid
                        """,
                        (str(tenant_row["id"]),),
                    )

                db_ledger_rows = {
                    "credit_accounts_balance_total": fetch_one(
                        conn,
                        "SELECT COALESCE(sum(balance), 0) AS t FROM credit_accounts",
                        (),
                    )["t"],
                    "credit_transactions_amount_total": fetch_one(
                        conn,
                        "SELECT COALESCE(sum(amount), 0) AS t FROM credit_transactions",
                        (),
                    )["t"],
                }
                db_ledger = {key: str(value) for key, value in db_ledger_rows.items()}

                media_files = _copy_media(root, media_dir)

                ok = _print_reconciliation(
                    manifest,
                    imported_counts,
                    db_ledger,
                    stats,
                    bundle_sha,
                    media_files,
                    warnings,
                    status_note,
                )
                if not ok:
                    conn.rollback()
                    return 1
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    print(f"媒体目录: {media_dir}")
    print("下一步: 重启 app（去掉 STUDIOSAAS_SKIP_STANDALONE_CHECKS）→ 走 DEPLOYMENT.md §4 验收清单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
