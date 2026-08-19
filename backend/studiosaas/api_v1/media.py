"""api_v1.media — mechanically split from api_v1.py (v10.11.0). Pure move."""
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_from_directory
from ..auth import (
    PermissionDeniedError,
    auth_required,
    hash_password as _auth_hash_password,
    permission_required,
    require_permission,
    super_admin_required,
    tenant_admin_required,
    tenant_owner_required,
    verify_password as _auth_verify_password,
)
from ..db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from ..models import Role
from ..services.media import (
    MediaQuotaExceededError,
    MediaUploadError,
    send_media_asset,
    store_media_asset,
)
from ._shared import (
    _active_publication_consent,
    _audit_request,
    _clean_text,
    _error,
    _json_payload,
    _media_error,
    _media_token,
    _plan_feature_enabled,
    _send_media_asset,
    _tenant_context,
    api_v1,
)



def _validate_portfolio_visibility(value: str) -> str:
    """Return a supported portfolio visibility value or raise a clear error."""

    visibility = str(value or "private").strip().lower()
    if visibility not in {"private", "shared"}:
        raise ValueError("visibility must be one of: private, shared.")
    return visibility




@api_v1.route("/portfolio", methods=["GET"])
@permission_required("portfolio:read")
def list_portfolio():
    """List recent portfolio items for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.title, p.description, p.artwork_date, p.visibility,
                   p.created_at, s.display_name AS student_name,
                   m.storage_key, m.mime_type
            FROM portfolio_items p
            JOIN students s ON s.id = p.student_id
            JOIN media_assets m ON m.id = p.media_asset_id
            WHERE p.tenant_id = %s
            ORDER BY p.created_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"portfolio": rows})




@api_v1.route("/media/<media_asset_id>", methods=["GET"])
@permission_required("students:read")
def get_media_asset(media_asset_id: str):
    """Serve one tenant-owned media asset for authenticated studio admins."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        return _send_media_asset(conn, tenant_id=tenant.tenant_id, media_asset_id=media_asset_id)




@api_v1.route("/media/upload", methods=["POST"])
@auth_required
def upload_media_asset():
    """Upload one tenant media asset through the canonical v1 endpoint.

    Portfolio uploads follow portfolio:write so teachers/staff can use the
    canonical endpoint (they previously had to detour through the legacy CMS
    upload); every other kind (brand/site assets) stays owner/manager.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        kind = str(request.form.get("kind") or "portfolio").strip() or "portfolio"
        try:
            if kind == "portfolio":
                require_permission(g.actor, "portfolio:write")
            elif g.actor.role not in {Role.SUPER_ADMIN, Role.OWNER, Role.MANAGER}:
                raise PermissionDeniedError("Tenant owner/admin privileges required.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        if kind == "portfolio" and not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        owner_student_id = str(
            request.form.get("studentId")
            or request.form.get("ownerStudentId")
            or ""
        ).strip() or None
        storage_provider = str(request.form.get("storageProvider") or "local").strip().lower() or "local"
        try:
            media = store_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                file_storage=f,
                kind=kind,
                owner_student_id=owner_student_id,
                storage_provider=storage_provider,
            )
        except MediaUploadError as exc:
            return _media_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="media.uploaded",
            resource_type="media_asset",
            resource_id=media["id"],
            metadata={
                "kind": kind,
                "byte_size": media["byte_size"],
                "storage_provider": media["storage_provider"],
            },
        )
    media_id = str(media["id"])
    return jsonify(
        {
            "ok": True,
            "mediaAssetId": media_id,
            "filename": _media_token(media_id),
            "url": f"/s/{tenant.slug}/v1/media/{media_id}",
            "mimeType": media["mime_type"],
            "byteSize": media["byte_size"],
            "storageProvider": media["storage_provider"],
        }
    ), 201




@api_v1.route("/share-links/<link_id>/revoke", methods=["POST"])
@permission_required("portfolio:write")
def revoke_share_link(link_id: str):
    """Revoke one share link; the public viewer and media URLs stop working."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            UPDATE share_tokens SET revoked_at = now()
            WHERE id = %s AND tenant_id = %s AND scope = 'student_portfolio' AND revoked_at IS NULL
            RETURNING student_id
            """,
            (link_id, tenant.tenant_id),
        )
        if not row:
            return _error("Share link not found or already revoked.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.share_link_revoked",
            resource_type="student",
            resource_id=str(row["student_id"]),
            metadata={"share_token_id": link_id},
        )
        conn.commit()
    return jsonify({"ok": True})




# ──────────────────────────────────────────────
# P0: Portfolio CRUD
# ──────────────────────────────────────────────

@api_v1.route("/portfolio", methods=["POST"])
@permission_required("portfolio:write")

def create_portfolio_item():
    """Create a portfolio item linked to a media asset and student."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        payload = _json_payload()

        student_id = _clean_text(payload, "studentId")
        media_asset_id = _clean_text(payload, "mediaAssetId")
        title = _clean_text(payload, "title", "")
        description = _clean_text(payload, "description", "")
        try:
            visibility = _validate_portfolio_visibility(_clean_text(payload, "visibility", "private"))
        except ValueError as exc:
            return _error(str(exc))
        if not student_id:
            return _error("studentId is required.")
        if not media_asset_id:
            return _error("mediaAssetId is required.")

        # Verify ownership
        student = fetch_one(
            conn, "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)
        if visibility == "shared" and not _active_publication_consent(
            conn, tenant_id=tenant.tenant_id, student_id=student_id
        ):
            return _error(
                "An active student publication consent record is required before publishing.",
                400,
            )

        media = fetch_one(
            conn, "SELECT id FROM media_assets WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, media_asset_id),
        )
        if not media:
            return _error("Media asset was not found.", 404)

        artwork_date_str = _clean_text(payload, "artworkDate")
        try:
            from datetime import date as _date
            artwork_date_val = None
            if artwork_date_str:
                artwork_date_val = _date.fromisoformat(artwork_date_str)
        except (ValueError, TypeError):
            return _error("artwork_date must be ISO-8601 date (YYYY-MM-DD).")

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO portfolio_items (
                tenant_id, student_id, media_asset_id, title, description,
                artwork_date, visibility, public_consent_at,
                public_consent_by_user_id, public_consent_note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s,
                      CASE WHEN %s = 'shared' THEN now() ELSE NULL END,
                      CASE WHEN %s = 'shared' THEN %s ELSE NULL END,
                      CASE WHEN %s = 'shared' THEN 'Confirmed before public publishing' ELSE '' END)
            RETURNING id
            """,
            (
                tenant.tenant_id, student_id, media_asset_id, title, description,
                artwork_date_val, visibility, visibility, visibility,
                getattr(g.actor, "user_id", None), visibility,
            ),
        )
        item_id = str(cur.fetchone()["id"])
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.uploaded",
            resource_type="portfolio_item",
            resource_id=item_id,
            metadata={"student_id": student_id, "media_asset_id": media_asset_id},
        )

    return jsonify({"ok": True, "portfolioItemId": item_id}), 201




@api_v1.route("/portfolio/<portfolio_item_id>", methods=["PATCH"])
@permission_required("portfolio:write")

def update_portfolio_item(portfolio_item_id: str):
    """Update a portfolio item's metadata for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        title = _clean_text(payload, "title")
        description = _clean_text(payload, "description")
        try:
            visibility = _validate_portfolio_visibility(_clean_text(payload, "visibility")) if "visibility" in payload else ""
        except ValueError as exc:
            return _error(str(exc))
        if visibility == "shared" and not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        artwork_date_str = _clean_text(payload, "artworkDate")

        try:
            from datetime import date as _date
            artwork_date_val = None
            if artwork_date_str:
                artwork_date_val = _date.fromisoformat(artwork_date_str)
        except (ValueError, TypeError):
            return _error("artwork_date must be ISO-8601 date (YYYY-MM-DD).")

        existing_item = fetch_one(
            conn,
            "SELECT student_id FROM portfolio_items WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, portfolio_item_id),
        )
        if not existing_item:
            return _error("Portfolio item was not found.", 404)
        if visibility == "shared" and not _active_publication_consent(
            conn,
            tenant_id=tenant.tenant_id,
            student_id=str(existing_item["student_id"]),
        ):
            return _error(
                "An active student publication consent record is required before publishing.",
                400,
            )

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE portfolio_items
            SET title = COALESCE(NULLIF(%s, ''), title),
                description = COALESCE(NULLIF(%s, ''), description),
                visibility = COALESCE(NULLIF(%s, ''), visibility),
                public_consent_at = CASE WHEN %s = 'shared' THEN now() ELSE public_consent_at END,
                public_consent_by_user_id = CASE WHEN %s = 'shared' THEN %s ELSE public_consent_by_user_id END,
                public_consent_note = CASE WHEN %s = 'shared' THEN 'Confirmed before public publishing' ELSE public_consent_note END,
                artwork_date = COALESCE(%s, artwork_date),
                updated_at = now()
            WHERE tenant_id = %s AND id = %s
            RETURNING id
            """,
            (
                title, description, visibility, visibility, visibility,
                getattr(g.actor, "user_id", None), visibility, artwork_date_val,
                tenant.tenant_id, portfolio_item_id,
            ),
        )
        if not cur.fetchone():
            return _error("Portfolio item was not found.", 404)

    return jsonify({"ok": True})




@api_v1.route("/portfolio/<portfolio_item_id>", methods=["DELETE"])
@permission_required("portfolio:write")

def delete_portfolio_item(portfolio_item_id: str):
    """Delete a portfolio item for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM portfolio_items WHERE tenant_id = %s AND id = %s RETURNING id",
            (tenant.tenant_id, portfolio_item_id),
        )
        if not cur.fetchone():
            return _error("Portfolio item was not found.", 404)

    return jsonify({"ok": True})


