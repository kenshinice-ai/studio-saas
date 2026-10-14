"""Claude drafting routes: a tenant's switch, and one draft at a time.

The rules are in services/drafting.py and the plan in
docs/design/Claude_Drafting_Plan_2026-10-14.md. What this module adds is who
may ask and when:

* The tenant's owner turns drafting on; it is off for every tenant until then
  (Lee, 2026-10-14). Turning it on is where the studio accepts the privacy
  terms on behalf of its families.
* Each kind of draft needs the permission its record already needs: a
  progress report needs progress_reports:write, an invoice billing:read, a
  booking reply class_bookings:review, a message about a student students:write.
* A tenant has a monthly number of drafts. Drafting is included in the plan
  (Lee, 2026-10-14); the limit stops a mistake or a loop from running up a bill.
* Every draft writes one audit row with the model, token counts and an
  estimated cost. The text of the draft and the facts are never stored.
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import g, jsonify

from ..auth import PermissionDeniedError, auth_required, require_permission, tenant_admin_required
from ..db import connect, fetch_one
from ..models import Role
from ..services import drafting as _drafting
from ._shared import (
    _audit_request,
    _error,
    _json_payload,
    _tenant_context,
    _tenant_timezone,
    api_v1,
)

#: Drafts per tenant per calendar month (tenant's own time zone).
MONTHLY_LIMIT = 300

#: Lee chose Haiku 5.5 on 2026-10-14 after the evaluation
#: (docs/design/Claude_Drafting_Eval_2026-10-14.md): tone within noise of
#: Opus 5.5, no invented figures, about 1/23 of the cost, 2.6 s median.
#: Override with STUDIOSAAS_DRAFTING_MODEL on the host.
DEFAULT_MODEL = "claude-haiku-5-5"

KIND_PERMISSIONS = {
    _drafting.REPORT_COMMENT: "progress_reports:write",
    _drafting.OVERDUE_INVOICE: "billing:read",
    _drafting.BOOKING_REPLY: "class_bookings:review",
    _drafting.LOW_CREDITS: "students:write",
    _drafting.MISSED_LESSONS: "students:write",
    _drafting.EXPIRING_MAKEUP: "students:write",
}

VOICE_MAX = 500
NOTE_MAX = 300

_client = None


def _api_key() -> str:
    return (os.environ.get("STUDIOSAAS_DRAFTING_API_KEY") or "").strip()


def _model() -> str:
    return (os.environ.get("STUDIOSAAS_DRAFTING_MODEL") or DEFAULT_MODEL).strip()


def _get_client():
    """One client per process, created on first use with the host's key."""

    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=_api_key(), timeout=20.0)
    return _client


def _settings(conn, tenant_id: str) -> dict:
    row = fetch_one(
        conn,
        """
        SELECT COALESCE((settings->>'drafting_enabled')::boolean, false) AS enabled,
               COALESCE(settings->>'drafting_voice', '') AS voice
        FROM tenants WHERE id = %s
        """,
        (tenant_id,),
    ) or {}
    return {"enabled": bool(row.get("enabled")), "voice": row.get("voice") or ""}


def _used_this_month(conn, tenant_id: str) -> int:
    zone = ZoneInfo(_tenant_timezone(conn, tenant_id))
    start = datetime.now(zone).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    row = fetch_one(
        conn,
        "SELECT count(*) AS n FROM audit_logs WHERE tenant_id = %s AND action = 'draft.created' AND created_at >= %s",
        (tenant_id, start),
    )
    return int((row or {}).get("n") or 0)


@api_v1.route("/drafting/settings", methods=["GET"])
@auth_required
def drafting_settings():
    """Whether drafting can be used here, and how much is left this month."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        current = _settings(conn, tenant.tenant_id)
        used = _used_this_month(conn, tenant.tenant_id)
    return jsonify({
        "enabled": current["enabled"],
        "voice": current["voice"],
        # False when the host has no key: the switch stays visible but cannot
        # produce anything, and the screen says why.
        "available": bool(_api_key()),
        "monthlyLimit": MONTHLY_LIMIT,
        "usedThisMonth": used,
    })


@api_v1.route("/drafting/settings", methods=["PATCH"])
@tenant_admin_required
def update_drafting_settings():
    """The owner turns drafting on or off and describes the studio's voice.

    Owner only, not every tenant admin: turning drafting on is where the studio
    accepts, for its families, that their details go to Anthropic. A manager
    can use drafting once it is on.
    """

    if getattr(g.actor, "role", None) not in {Role.OWNER, Role.SUPER_ADMIN}:
        return _error("Only the studio owner can change this.", 403)
    try:
        payload = _json_payload()
        changes = {}
        if "enabled" in payload:
            if not isinstance(payload["enabled"], bool):
                raise ValueError("enabled must be true or false.")
            changes["drafting_enabled"] = payload["enabled"]
        if "voice" in payload:
            voice = str(payload.get("voice") or "").strip()
            if len(voice) > VOICE_MAX:
                raise ValueError(f"voice must be at most {VOICE_MAX} characters.")
            changes["drafting_voice"] = voice
        if not changes:
            raise ValueError("Send enabled, voice, or both.")
    except ValueError as exc:
        return _error(str(exc))

    import json

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenants SET settings = COALESCE(settings, '{}'::jsonb) || %s::jsonb, "
                "updated_at = now() WHERE id = %s",
                (json.dumps(changes), tenant.tenant_id),
            )
        if "drafting_enabled" in changes:
            _audit_request(
                conn, tenant_id=tenant.tenant_id,
                action="drafting.enabled" if changes["drafting_enabled"] else "drafting.disabled",
                resource_type="tenant_settings",
            )
        conn.commit()
        current = _settings(conn, tenant.tenant_id)
    return jsonify({"ok": True, **current})


@api_v1.route("/drafts", methods=["POST"])
@auth_required
def create_draft():
    """Draft one message. Nothing is sent and nothing is changed."""

    payload = _json_payload()
    kind = str(payload.get("kind") or "")
    record_id = str(payload.get("recordId") or "").strip()
    language = str(payload.get("language") or "zh")
    decision = str(payload.get("decision") or "")
    # What the staff member wants to say, typed in the dialog. Evaluation
    # 2026-10-14: a "question" reply without it can only be a placeholder.
    note = str(payload.get("note") or "").strip()[:NOTE_MAX]
    if kind not in KIND_PERMISSIONS:
        return _error("Unknown draft kind.")
    if not record_id:
        return _error("recordId is required.")
    try:
        require_permission(g.actor, KIND_PERMISSIONS[kind])
    except PermissionDeniedError as exc:
        return _error(str(exc), 403)
    if not _api_key():
        return jsonify({"error": "unavailable", "message": "Drafting is not set up on this server."}), 503

    with connect() as conn:
        tenant = _tenant_context(conn)
        current = _settings(conn, tenant.tenant_id)
        if not current["enabled"]:
            return jsonify({"error": "disabled", "message": "Drafting is turned off for this studio."}), 403
        if _used_this_month(conn, tenant.tenant_id) >= MONTHLY_LIMIT:
            return jsonify({"error": "limit", "message": "This month's drafts are used up."}), 429
        today = datetime.now(ZoneInfo(_tenant_timezone(conn, tenant.tenant_id))).date()
        try:
            gathered = _drafting.gather(conn, tenant.tenant_id, kind, record_id, today=today, decision=decision)
            if note:
                gathered.facts["staff_note"] = note
            request = _drafting.build_request(kind, gathered.facts, voice=current["voice"], language=language)
        except _drafting.RecordNotFound:
            return _error("That record does not exist.", 404)
        except _drafting.DraftingError as exc:
            return jsonify({"error": exc.code, "message": str(exc)}), 400
        # The database transaction is not held open across the model call.
        conn.commit()

        model = _model()
        try:
            draft = _drafting.call_model(_get_client(), request, model=model)
        except _drafting.DraftingError as exc:
            _audit_request(conn, tenant_id=tenant.tenant_id, action="draft.failed",
                           resource_type=kind, resource_id=record_id,
                           metadata={"code": exc.code, "model": model})
            conn.commit()
            return jsonify({"error": exc.code, "message": str(exc)}), 502

        draft.unbacked = _drafting.unbacked_figures(draft.body, gathered.facts)
        _audit_request(
            conn, tenant_id=tenant.tenant_id, action="draft.created",
            resource_type=kind, resource_id=record_id,
            metadata={
                "model": draft.model, "inputTokens": draft.input_tokens,
                "outputTokens": draft.output_tokens, "cacheReadTokens": draft.cache_read_tokens,
                "costMicrosUsd": _drafting.estimated_cost_micros(draft),
                "unbacked": len(draft.unbacked), "missing": len(draft.missing),
            },
        )
        conn.commit()

    return jsonify({
        "draft": draft.as_dict(),
        # Shown beside the draft so staff can check it. Not stored.
        "facts": gathered.facts,
        # Fills the mailto:/sms: link on the screen. Never sent to Claude.
        "recipient": gathered.recipient,
    })
