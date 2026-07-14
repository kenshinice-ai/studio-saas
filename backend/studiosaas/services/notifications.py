"""Tenant email notifications (B3, v1).

Pluggable backend selected by STUDIOSAAS_EMAIL_BACKEND:
  - ``console`` (default): render and print to the server log — safe for
    local pilots, no external delivery.
  - ``smtp``: deliver via STUDIOSAAS_SMTP_HOST/PORT/USER/PASSWORD/FROM.

Templates resolve from the per-tenant ``email_templates`` table first
(key match), falling back to the built-in defaults below. Rendering uses
``str.format_map`` with missing keys left visible as ``{key}`` so a bad
template never raises.

Every attempt is recorded in ``notification_logs`` (channel='email').
Callers should treat sending as best-effort: use :func:`send_safely`
from request handlers so a mail failure never breaks the main flow.
"""

from __future__ import annotations

import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from typing import Any

DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "registration_received": (
        "We received your registration — {studio_name}",
        "Hi {parent_name},\n\n"
        "Thanks for registering {student_name} with {studio_name}. "
        "Our team will review your registration and get back to you soon.\n\n"
        "— {studio_name}",
    ),
    "registration_approved": (
        "Registration approved — {studio_name}",
        "Hi {parent_name},\n\n"
        "Great news! {student_name}'s registration with {studio_name} has been approved. "
        "We'll be in touch with class details shortly.\n\n"
        "— {studio_name}",
    ),
    "registration_rejected": (
        "About your registration — {studio_name}",
        "Hi {parent_name},\n\n"
        "Thank you for your interest in {studio_name}. Unfortunately we can't "
        "take {student_name}'s registration forward right now.{review_note_line}\n\n"
        "— {studio_name}",
    ),
}


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # keep unknown placeholders visible
        return "{" + key + "}"


def _render(template: str, context: dict[str, Any]) -> str:
    return template.format_map(_SafeDict(**{k: ("" if v is None else v) for k, v in context.items()}))


def _resolve_template(conn, tenant_id, template_key: str) -> tuple[str, str] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT subject, body FROM email_templates WHERE tenant_id = %s AND template_key = %s",
            (tenant_id, template_key),
        )
        row = cur.fetchone()
    if row:
        return row["subject"], row["body"]
    return DEFAULT_TEMPLATES.get(template_key)


def _deliver(subject: str, body: str, to_email: str) -> str:
    """Deliver one email; returns a provider message id ('' for console)."""

    backend = (os.environ.get("STUDIOSAAS_EMAIL_BACKEND") or "console").strip().lower()
    if backend == "smtp":
        host = os.environ.get("STUDIOSAAS_SMTP_HOST", "localhost")
        port = int(os.environ.get("STUDIOSAAS_SMTP_PORT", "587"))
        user = os.environ.get("STUDIOSAAS_SMTP_USER", "")
        password = os.environ.get("STUDIOSAAS_SMTP_PASSWORD", "")
        sender = os.environ.get("STUDIOSAAS_SMTP_FROM", user or "noreply@studiosaas.local")
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender
        msg["To"] = to_email
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(sender, [to_email], msg.as_string())
        return ""
    # console backend
    print(f"[email:console] to={to_email!r} subject={subject!r}\n{body}\n[/email]", flush=True)
    return ""


def send(conn, *, tenant_id, template_key: str, to_email: str, context: dict[str, Any]) -> bool:
    """Render and send one notification; always logs to notification_logs.

    Returns True when delivery succeeded (or console-printed). The caller
    owns the transaction — commit after calling.
    """

    to_email = (to_email or "").strip()
    if not to_email:
        return False
    resolved = _resolve_template(conn, tenant_id, template_key)
    if not resolved:
        return False
    subject = _render(resolved[0], context)
    body = _render(resolved[1], context)

    status, error_message, provider_id = "sent", "", ""
    try:
        provider_id = _deliver(subject, body, to_email)
    except Exception as exc:  # delivery must never raise into callers
        status, error_message = "failed", str(exc)[:500]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notification_logs
                (tenant_id, channel, recipient, subject, status, provider_message_id, error_message)
            VALUES (%s, 'email', %s, %s, %s, %s, %s)
            """,
            (tenant_id, to_email, subject[:500], status, provider_id, error_message),
        )
    return status == "sent"


def send_safely(conn, **kwargs) -> bool:
    """Best-effort wrapper: swallow every error so callers never break."""

    try:
        return send(conn, **kwargs)
    except Exception:
        return False
