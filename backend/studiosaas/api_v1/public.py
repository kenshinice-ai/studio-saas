"""api_v1.public — mechanically split from api_v1.py (v10.11.0). Pure move."""
import json
import os
import re
import hashlib
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
from ..errors import api_error
from ..services import calendar_subscriptions as _calendar_subs
from ..presets import (
    FREE_ACCENT_STYLE_ID,
    INDUSTRY_PRESETS,
    INDUSTRY_SECTION_COPY,
    VISUAL_STYLE_PRESETS,
    public_industry_presets,
    public_visual_style_presets,
    accent_hue_of_colour,
    resolve_style_id,
    style_theme,
)
from ..services.media import (
    MediaQuotaExceededError,
    MediaUploadError,
    send_media_asset,
    store_media_asset,
)
from ..services import cms_notifications as _cms_notifications
from ..services import notifications as _notifications
from ..services.public_site import public_plan_rows
from ..services.student_access import (
    access_lock_seconds_remaining as _student_access_lock_seconds,
    access_locked as _student_access_locked,
    clear_failed_access as _clear_student_access_failures,
    create_access_session as _create_student_access_session,
    find_student as _find_public_student,
    generate_access_code as _generate_student_access_code,
    lookup_fingerprint as _student_lookup_fingerprint,
    record_failed_access as _record_student_access_failure,
    resolve_access_session as _resolve_student_access_session,
    revoke_access_code as _revoke_student_access_code,
    revoke_access_session as _revoke_student_access_session,
    verify_access_code as _verify_student_access_code,
)
from ..tenant_context import (
    bind_user_session as _bind_user_session,
    bind_tenant_session as _bind_tenant_session,
    TenantGoneError,
    TenantResolutionError,
    canonical_slug_for,
    forget_retired_addresses,
    resolve_tenant,
    slug_from_request,
)
from ._shared import (
    SHOWCASE_FEATURED_RANK_MAX,
    TIMETABLE_DEFAULT_WEEKS,
    TIMETABLE_FIELD_DEFAULTS,
    _audit,
    _audit_request,
    _cacheable_json,
    _clean_text,
    _client_ip,
    _default_faq_items,
    _default_hero_profile,
    _default_principal_profile,
    _default_registration_profile,
    _default_visual_theme,
    _default_website_profile,
    _error,
    _find_matching_student,
    _json_payload,
    _legacy_identity_copy,
    _localized_pair,
    _media_error,
    _media_token,
    _normalize_localized_copy,
    _normalize_message_templates,
    _normalize_visual_theme,
    _normalize_website_profile,
    _phone_digits,
    _plan_feature_enabled,
    _preset_for,
    _rate_limited,
    _roster_date,
    _send_media_asset,
    _store_media_asset,
    _tenant_timezone,
    _validate_optional_email,
    api_v1,
    showcase_limit_for,
)


# The version of the privacy notice the public pages render. It is served to
# the portal and the register page through /brand and stored with each consent
# record, so the version a visitor agreed to always matches the text they saw.
# Bump this whenever the privacy copy in tenant-template/index.html changes.
PRIVACY_NOTICE_VERSION = "2026-07-12"


def _student_cookie_secure() -> bool:
    """Return whether public student cookies must use HTTPS-only semantics."""

    if request.is_secure or os.environ.get("COOKIE_SECURE") == "1":
        return True
    if os.environ.get("STUDIOSAAS_ENV", "local").strip().lower() in {"pilot", "production"}:
        return True
    return bool(
        request.remote_addr in {"127.0.0.1", "::1"}
        and request.headers.get("X-Forwarded-Proto", "").lower() == "https"
    )




def _student_cookie_name() -> str:
    """Use the hardened host cookie in HTTPS environments and a local name in dev."""

    return "__Host-studiosaas-student" if _student_cookie_secure() else "studiosaas_student"




def _student_cookie_token() -> str:
    """Read either supported cookie name to make HTTPS transitions explicit."""

    return str(
        request.cookies.get("__Host-studiosaas-student")
        or request.cookies.get("studiosaas_student")
        or ""
    )



# How many works one page of the public board carries. The first screen of a
# portfolio is an argument, not an archive.
SHOWCASE_PAGE_SIZE = 12


# The home page is a doorway to the full portfolio, not a second archive.  It
# asks the same endpoint for a deliberately smaller, server-controlled preview
# so a tenant cannot accidentally turn the landing page into a 500-item feed.
SHOWCASE_PREVIEW_SIZE = 6



def _ordered_showcase_items(items: list[dict]) -> list[dict]:
    """Return active works with ranked items first and stable legacy order."""

    return [
        item
        for _index, item in sorted(
            enumerate(items),
            key=lambda pair: (
                pair[1].get("featured_rank") is None,
                pair[1].get("featured_rank") or SHOWCASE_FEATURED_RANK_MAX + 1,
                pair[0],
            ),
        )
    ]




def _stored_visual_theme(
    value,
    primary_color: str = "",
    secondary_color: str = "",
    category: str = "general",
) -> dict:
    """Re-normalise a STORED theme, and never raise doing it.

    A stored record is not user input. It was written by whichever release the
    owner last saved under, and it is read on every public page load by a
    visitor who cannot fix anything. So the only two acceptable outcomes here
    are the studio's theme and the default theme — never an exception.

    That distinction was missing until v8.5.4 and the read path simply called
    the write validator. When v8.5.2 renamed one style id, five of six live
    tenants started answering 500 for their whole brand payload: not just the
    colours, but every word and every image on the page, because the copy and
    the palette travel in the same response. The portals looked wiped.

    The alias in `RETIRED_STYLE_ALIASES` is what makes those tenants come back
    on their OWN palette. This is the net under it: any other stored value
    that a future release stops accepting costs that studio its theme for one
    page load, and costs it nothing else.
    """

    try:
        return _normalize_visual_theme(
            value, primary_color, secondary_color, category, strict=False
        )
    except (ValueError, TypeError):
        current_app.logger.warning(
            "visual_theme could not be normalised; serving the default theme",
            exc_info=True,
        )
        return _default_visual_theme(primary_color, secondary_color, category)




def _published_schemes(theme: object) -> dict:
    """Both palettes, when the site may be asked to render either.

    A page that follows the visitor's device has to hold the light tokens and
    the dark tokens at once — it cannot fetch the other one when the OS setting
    changes mid-visit, and a studio that publishes only the mode it happens to
    prefer would leave half its visitors on a palette solved for the other
    surface. So the scheme preference decides what is SENT, not just what is
    applied.
    """

    if not isinstance(theme, dict):
        return {}
    style_id = theme.get("style_id") or ""
    if theme.get("scheme_preference") != "system" or style_id not in VISUAL_STYLE_PRESETS:
        return {}
    hue = theme.get("accent_hue")
    hue = float(hue) if isinstance(hue, (int, float)) else None
    return {mode: style_theme(style_id, mode, hue)
            for mode in VISUAL_STYLE_PRESETS[style_id]["modes"]}




def _find_pending_registration(cur, *, tenant_id: str, first_name: str, last_name: str, mobile: str):
    """Return an existing pending/contacted registration for the same tenant/person."""

    cur.execute(
        """
        SELECT id
        FROM registrations
        WHERE tenant_id = %s
          AND status IN ('pending', 'contacted')
          AND regexp_replace(mobile, '[^0-9]', '', 'g') = %s
          AND lower(first_name) = lower(%s)
          AND lower(last_name) = lower(%s)
        ORDER BY submitted_at DESC
        LIMIT 1
        """,
        (tenant_id, _phone_digits(mobile), first_name, last_name),
    )
    return cur.fetchone()




# A studio names its own sections, and those names are also its nav items. One
# studio's English course label is the full list of media it teaches — 74
# characters, 241 pixels, and with every section switched on the bar wrapped to
# a second line inside a header one line tall. The heading on the page keeps
# the whole sentence; only the entry in the bar is clipped.
NAV_LABEL_LIMIT = {"zh": 10, "en": 24}


# The call to action is tighter than the rest of the bar. It is a bordered pill
# sitting next to the language switch, so it has the least room and the most
# padding, and the field behind it is the one a studio is most likely to fill
# with a sentence: one studio's reads 「原创油画 × 私人定制」. The hero button
# still shows the whole thing — it reads that field directly, not this label.
CTA_LABEL_LIMIT = {"zh": 7, "en": 18}



def _clip_nav_label(value: str, language: str, limits: dict[str, int] | None = None) -> str:
    """Shorten a label to something a navigation bar can hold."""

    limit = (limits or NAV_LABEL_LIMIT).get(language, 24)
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"




def _public_surface_entry(key: str, intent: bool, ready: bool, href: str,
                          *, reason: str = "no_content", next_action: str = "review_in_studio_admin",
                          surface: str | None = None, placement: str = "home",
                          navigation_eligible: bool = True, footer_eligible: bool = True,
                          content_ready: bool | None = None,
                          dependency_ready: bool | None = None,
                          published_version: int | None = None,
                          label: dict | None = None) -> dict:
    """Build the public navigation contract used by every tenant surface.

    ``intent`` is the owner's switch; ``ready`` is the smallest truthful
    content check for that route.  Keeping both values in the response lets
    Studio Admin explain why an entry is hidden instead of merely removing it.
    """

    effective_content_ready = bool(ready if content_ready is None else content_ready)
    effective_dependency_ready = bool(ready if dependency_ready is None else dependency_ready)
    effective_ready = bool(ready and effective_content_ready and effective_dependency_ready)
    visible = bool(intent and effective_ready)
    result = {
        "key": key,
        "intent": bool(intent),
        "ready": effective_ready,
        "contentReady": effective_content_ready,
        "dependencyReady": effective_dependency_ready,
        "visible": visible,
        "href": href,
        "surface": surface or key,
        "placement": placement,
        "navigationEligible": bool(navigation_eligible),
        "footerEligible": bool(footer_eligible),
        "reasonCode": "ready" if visible else (reason if intent else "disabled_by_owner"),
        "nextAction": "" if visible else next_action,
        "publishedVersion": published_version,
    }
    # Keep the helper backwards-compatible for internal callers that only
    # need readiness. Public shell entries opt into a localized label so every
    # page can render the same navigation copy without scraping the homepage.
    if label is not None:
        result["label"] = {
            "zh": str(label.get("zh") or label.get("en") or "").strip(),
            "en": str(label.get("en") or label.get("zh") or "").strip(),
        }
    return result




def _public_surface_actions(hero: dict, modules: dict[str, dict],
                            secondary_label: dict | None = None) -> dict[str, dict]:
    """Resolve hero actions against the same readiness contract as navigation.

    A button must never point at a hidden or empty section. ``auto`` exists only
    for pre-v9.8.9 tenants and selects the first ready public destination;
    explicit choices fail closed so Studio Admin can explain what to fix.
    """

    register = modules["register"]
    primary = {
        "key": "primary",
        "targetType": "register",
        "href": register["href"],
        "visible": bool(register["visible"]),
        "reasonCode": register["reasonCode"],
        "nextAction": register["nextAction"],
    }
    if register.get("label") is not None:
        primary["label"] = register["label"]
    requested = str(hero.get("secondary_cta_target") or "auto").strip().lower()
    if requested == "hidden":
        result = {
            "primary": primary,
            "secondary": {
                "key": "secondary", "targetType": "hidden", "href": "", "visible": False,
                "reasonCode": "disabled_by_owner", "nextAction": "choose_secondary_cta_target",
            },
        }
        if secondary_label is not None:
            result["secondary"]["label"] = secondary_label
        return result
    if requested == "external":
        href = str(hero.get("secondary_cta_href") or "").strip()
        if not re.match(r"^https://\S+$", href, re.IGNORECASE):
            href = ""
        result = {
            "primary": primary,
            "secondary": {
                "key": "secondary", "targetType": "external", "href": href,
                "visible": bool(href),
                "reasonCode": "ready" if href else "missing_external_url",
                "nextAction": "" if href else "add_secondary_cta_url",
            },
        }
        if secondary_label is not None:
            result["secondary"]["label"] = secondary_label
        return result

    candidates = ("courses", "showcase", "timetable", "register")
    target = requested
    if requested == "auto":
        target = next((key for key in candidates if modules[key]["visible"]), "register")
    module = modules.get(target, register)
    result = {
        "primary": primary,
        "secondary": {
            "key": "secondary", "targetType": target, "href": module["href"],
            "visible": bool(module["visible"]), "reasonCode": module["reasonCode"],
            "nextAction": module["nextAction"],
        },
    }
    if secondary_label is not None:
        result["secondary"]["label"] = secondary_label
    return result




@api_v1.route("/public/<tenant_slug>/surface", methods=["GET"])
def public_surface(tenant_slug: str):
    """Return one effective contract for public navigation and footer links.

    The endpoint intentionally reports readiness from published data, not from
    the admin editor. A link therefore appears only when its target can render
    useful content, while the ``reasonCode`` remains available to previews and
    support tooling.
    """

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        row = fetch_one(
            conn,
            """
            SELECT name, contact_phone, contact_email, address,
                   COALESCE(settings->>'category', 'general') AS category,
                   COALESCE(settings->'website_profile', '{}'::jsonb) AS website,
                   COALESCE(settings->'principal_profile', '{}'::jsonb) AS principal,
                   COALESCE(settings->'hero_profile', '{}'::jsonb) AS hero,
                   COALESCE(settings->'localized_copy', '{}'::jsonb) AS localized_copy,
                   COALESCE(settings->'faq_items', '[]'::jsonb) AS faq,
                   COALESCE(settings->'registration_profile', '{}'::jsonb) AS registration
            FROM tenants WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        profile = _normalize_website_profile((row or {}).get("website") or {})
        category = str((row or {}).get("category") or "general")
        localized_copy = _normalize_localized_copy(
            (row or {}).get("localized_copy") or {},
            category,
            legacy={
                "courses_label": profile.get("courses_label", ""),
                "gallery_label": profile.get("gallery_label", ""),
                "faq_label": profile.get("faq_label", ""),
                "contact_label": profile.get("contact_label", ""),
            },
        )
        principal = row.get("principal") or {}
        hero = row.get("hero") or {}
        faq = row.get("faq") or []
        registration = row.get("registration") or {}
        course_row = fetch_one(
            conn,
            "SELECT count(*) AS n FROM courses WHERE tenant_id = %s AND is_active",
            (tenant.tenant_id,),
        )
        gallery_row = fetch_one(
            conn,
            """
            SELECT count(*) AS n
            FROM portfolio_items p
            JOIN students s ON s.id = p.student_id AND s.tenant_id = p.tenant_id
            JOIN media_variants mv ON mv.tenant_id = p.tenant_id
              AND mv.media_asset_id = p.media_asset_id AND mv.variant = 'display'
            JOIN LATERAL (
                SELECT status
                FROM student_publication_consent_events e
                WHERE e.tenant_id = p.tenant_id AND e.student_id = p.student_id
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
            ) consent ON consent.status = 'confirmed'
            WHERE p.tenant_id = %s AND p.visibility = 'shared'
              AND p.public_consent_at IS NOT NULL AND s.status <> 'archived'
            """,
            (tenant.tenant_id,),
        ) if _plan_feature_enabled(conn, tenant.tenant_id, "portfolio") else {"n": 0}
        timetable_ready = False
        if profile.get("show_timetable"):
            timezone_name = _tenant_timezone(conn, tenant.tenant_id)
            weeks = profile.get("timetable_weeks") or TIMETABLE_DEFAULT_WEEKS
            _today, occurrences = _timetable_occurrences(
                conn, tenant.tenant_id, weeks, timezone_name)
            timetable_ready = bool(occurrences)
        limit = showcase_limit_for(conn, tenant.tenant_id)
        published = fetch_one(
            conn,
            """
            SELECT version_number, published_at
            FROM tenant_brand_versions
            WHERE tenant_id = %s
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (tenant.tenant_id,),
        ) or {}

    active_items = [
        item for item in profile.get("showcase_items", [])
        if item.get("publication_state") == "active"
    ]
    showcase_ready = bool(_ordered_showcase_items(active_items)[:limit])
    contact_ready = bool(row.get("contact_phone") or row.get("contact_email") or row.get("address"))
    principal_ready = bool(str(principal.get("bio") or "").strip())
    about_ready = bool(
        _localized_pair(profile, "about_title", limit=600)["zh"]
        or _localized_pair(profile, "about_body", limit=600)["zh"]
        or profile.get("about_images")
        or profile.get("about_items")
    )
    published_version = published.get("version_number")
    preset = _preset_for(category)
    work_noun = preset.get("work_noun") or {"zh": "作品", "en": "work", "en_plural": "works"}
    venue_noun = preset.get("venue_noun") or {"zh": "工作室", "en": "studio"}

    def public_label_text(value, language: str) -> str:
        """Resolve industry placeholders before labels enter the public shell."""

        result = str(value or "").strip()
        if not result:
            return ""
        work = str(work_noun.get(language) or work_noun.get("zh") or "作品")
        works = str(
            (work_noun.get("en_plural") or work_noun.get("en") or work)
            if language == "en"
            else (work_noun.get("zh") or work)
        )
        venue = str(venue_noun.get(language) or venue_noun.get("zh") or "工作室")
        return (
            result.replace("%WORKS%", works)
            .replace("%WORK%", work)
            .replace("%VENUE%", venue)
        )

    def surface_label(value, fallback: dict[str, str], limit: int = 80,
                      limits: dict[str, int] | None = None) -> dict[str, str]:
        pair = _localized_pair({"value": value}, "value", limit=limit)
        return {
            "zh": _clip_nav_label(public_label_text(pair["zh"] or fallback["zh"], "zh"), "zh", limits),
            "en": _clip_nav_label(public_label_text(pair["en"] or fallback["en"], "en"), "en", limits),
        }

    labels = {
        "principal": {"zh": "主理人", "en": "Principal"},
        "showcase": surface_label(profile.get("showcase_label"), {"zh": "工作室作品", "en": "Selected Work"}),
        "courses": surface_label(localized_copy.get("courses_label"), {"zh": "课程与班次", "en": "Courses & Classes"}),
        "timetable": surface_label(profile.get("timetable_label"), {"zh": "课程安排", "en": "Timetable"}),
        "gallery": surface_label(localized_copy.get("gallery_label"), {"zh": "学员作品", "en": "Student Works"}),
        "faq": surface_label(localized_copy.get("faq_label"), {"zh": "常见问题", "en": "Questions & Answers"}),
        "student": {"zh": "学员专区", "en": "Student Login"},
        "register": surface_label(localized_copy.get("primary_cta"), {"zh": "预约体验", "en": "Book a Trial"},
                                  limits=CTA_LABEL_LIMIT),
    }
    secondary_label = surface_label(localized_copy.get("secondary_cta"), {"zh": "查看课程", "en": "Explore Programs"})
    modules = {
        "about": _public_surface_entry(
            "about", bool(profile.get("show_about", False)), about_ready,
            "#home:about", reason="missing_about_content", next_action="complete_space_profile",
            surface="home", placement="after_hero", navigation_eligible=False,
            footer_eligible=False, published_version=published_version,
        ),
        "principal": _public_surface_entry(
            "principal", bool(profile.get("show_principal", True)), principal_ready,
            "#home:artist", reason="missing_content", next_action="add_principal_bio", surface="home",
            placement="after_about", footer_eligible=False, published_version=published_version,
            label=labels["principal"],
        ),
        "showcase": _public_surface_entry(
            "showcase", bool(profile.get("show_showcase", False)), showcase_ready,
            f"/{tenant.slug}/showcase", reason="no_published_works", next_action="publish_showcase_work", surface="showcase",
            placement="after_principal", published_version=published_version, label=labels["showcase"],
        ),
        "courses": _public_surface_entry(
            "courses", bool(profile.get("show_courses", True)), int((course_row or {}).get("n") or 0) > 0,
            "#home:courses", reason="no_published_courses", next_action="publish_course", surface="home",
            placement="after_showcase", published_version=published_version, label=labels["courses"],
        ),
        "timetable": _public_surface_entry(
            "timetable", bool(profile.get("show_timetable", False)), timetable_ready,
            f"/{tenant.slug}/timetable", reason="no_upcoming_classes", next_action="publish_timetable", surface="timetable",
            placement="navigation", published_version=published_version, label=labels["timetable"],
        ),
        "gallery": _public_surface_entry(
            "gallery", bool(profile.get("show_gallery", True)), int((gallery_row or {}).get("n") or 0) > 0,
            "#home:gallery", reason="no_consented_student_work", next_action="share_student_work", surface="home",
            placement="after_courses", published_version=published_version, label=labels["gallery"],
        ),
        "faq": _public_surface_entry(
            "faq", bool(profile.get("show_faq", True)), bool(faq),
            "#home:faq", reason="no_faq_content", next_action="add_faq", surface="home",
            placement="after_gallery", published_version=published_version, label=labels["faq"],
        ),
        "contact": _public_surface_entry(
            "contact", bool(profile.get("show_contact", True)), contact_ready,
            "#home:contact", reason="missing_contact_details", next_action="add_contact_details", surface="home",
            placement="after_faq", navigation_eligible=False, footer_eligible=False,
            published_version=published_version,
        ),
        "student": _public_surface_entry(
            "student", bool(profile.get("show_student_area", hero.get("show_student_login", True))), True,
            "#my", surface="home", placement="utility", published_version=published_version, label=labels["student"],
        ),
        "register": _public_surface_entry(
            "register", True, bool(registration or row.get("name")), "#join",
            reason="registration_unavailable", next_action="complete_registration_profile", surface="register",
            placement="action", published_version=published_version, label=labels["register"],
        ),
    }
    navigation = [module for module in modules.values() if module["navigationEligible"]]
    footer = [module for module in modules.values() if module["footerEligible"]]
    actions = _public_surface_actions(hero, modules, secondary_label)
    return jsonify({"contract": {
        "version": 3,
        "contractVersion": 3,
        "generatedAt": _datetime.now(_timezone.utc).isoformat(),
        "publishedVersion": published_version,
        "publishedAt": published.get("published_at"),
        "modules": modules,
        "navigation": navigation,
        "footer": footer,
        "actions": actions,
        "shell": {"navigation": navigation, "footer": footer, "actions": actions},
    }})




@api_v1.route("/public/<tenant_slug>/brand", methods=["GET"])
def public_brand(tenant_slug: str):
    """Return public brand settings for registration and parent views."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        row = fetch_one(
            conn,
            """
            SELECT name, slug, primary_color, secondary_color, welcome_message,
                   contact_phone, contact_email, address,
                   settings->>'logo_url' AS logo_url,
                   settings->>'cms_layout' AS cms_layout,
                   settings->>'show_welcome' AS show_welcome,
                   COALESCE(settings->>'category', 'general') AS category,
                   settings->>'category_label' AS category_label,
                   settings->>'slogan' AS slogan,
                   settings->'registration_profile' AS registration_profile,
                   settings->'copy_pack' AS copy_pack,
                   settings->'localized_copy' AS localized_copy,
                   settings->'hero_profile' AS hero_profile,
                   settings->'website_profile' AS website_profile,
                   settings->'principal_profile' AS principal_profile,
                   settings->'faq_items' AS faq_items,
                   settings->'message_templates' AS message_templates,
                   settings->'visual_theme' AS visual_theme,
                   COALESCE((settings->>'professional_demo')::boolean, false) AS demo_tenant
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        published = fetch_one(
            conn,
            """
            SELECT version_number, published_at
            FROM tenant_brand_versions
            WHERE tenant_id = %s
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (tenant.tenant_id,),
        ) or {}
    category = row["category"] or "general"
    preset = _preset_for(category)
    row["category_label"] = row["category_label"] or preset["label"]
    row["slogan"] = row["slogan"] or preset["slogan"]
    row["registration_profile"] = row["registration_profile"] or _default_registration_profile(category)
    row["copy_pack"] = row["copy_pack"] or preset["copy_pack"]
    row["hero_profile"] = row["hero_profile"] or _default_hero_profile(category, row["name"])
    row["website_profile"] = row["website_profile"] or _default_website_profile()
    row["principal_profile"] = row["principal_profile"] or _default_principal_profile(row["name"])
    row["localized_copy"] = _normalize_localized_copy(
        row["localized_copy"] or {},
        category,
        legacy=_legacy_identity_copy(row),
    )
    row["faq_items"] = row["faq_items"] or _default_faq_items(category)
    row["message_templates"] = _normalize_message_templates(row["message_templates"])
    # A stored theme is whatever set of tokens existed on the day it was saved.
    # v8.4.0 added eighteen — the `info` role, the quiet form of every role,
    # `--surface-hover` and `--on-accent-muted` — so every tenant record written
    # before today is missing them.
    #
    # The page skips a token it is not sent, which means those eighteen would
    # fall through to portal-theme.css: a studio on recital-plum would get plum
    # surfaces and a vintage-press `--info` and `--success-soft`. Half a theme,
    # and no error anywhere.
    #
    # Re-normalising on read fills the gaps from the studio's OWN style rather
    # than from the default, and leaves every token the record does carry
    # exactly as stored. It is not a migration: the record is untouched until
    # the owner next saves.
    row["visual_theme"] = _stored_visual_theme(
        row["visual_theme"], row["primary_color"], row["secondary_color"], category
    ) if row["visual_theme"] else _default_visual_theme(
        row["primary_color"], row["secondary_color"], category
    )
    row["primaryColor"] = row["primary_color"]
    row["secondaryColor"] = row["secondary_color"]
    row["welcomeMessage"] = row["welcome_message"]
    row["contactPhone"] = row["contact_phone"]
    row["contactEmail"] = row["contact_email"]
    row["logoUrl"] = row["logo_url"]
    row["cmsLayout"] = row["cms_layout"]
    row["showWelcome"] = row["show_welcome"]
    row["categoryLabel"] = row["category_label"]
    row["registrationProfile"] = row["registration_profile"]
    row["copyPack"] = row["copy_pack"]
    row["localizedCopy"] = row["localized_copy"]
    row["heroProfile"] = row["hero_profile"]
    row["websiteProfile"] = row["website_profile"]
    row["principalProfile"] = row["principal_profile"]
    row["faqItems"] = row["faq_items"]
    row["messageTemplates"] = row["message_templates"]
    row["visualTheme"] = row["visual_theme"]
    row["visualThemes"] = _published_schemes(row["visual_theme"])
    # Industry nouns for the public template's %VENUE% / %WORK% tokens.
    row["venueNoun"] = dict(preset["venue_noun"])
    row["workNoun"] = dict(preset["work_noun"])
    # The portal and register page each hard-coded this string, so a consent
    # record could cite a version the visitor's page never rendered. One value,
    # served with the notice it refers to.
    row["privacyNoticeVersion"] = PRIVACY_NOTICE_VERSION
    # A demonstration tenant publishes synthetic work under an invented
    # person's name on a public URL. The portal says "these are Janet's own
    # paintings" — which is true of the fiction and false of the world, and a
    # visitor who arrives from a search engine has no way to tell. So the
    # tenant carries the fact into its own footer rather than relying on
    # everyone who links to it to explain.
    row["demoTenant"] = bool(row.get("demo_tenant"))
    row["demo_tenant"] = row["demoTenant"]
    row["publishedVersion"] = published.get("version_number")
    row["publishedAt"] = published.get("published_at")

    # The board itself is served by /public/<slug>/showcase, not from here.
    #
    # This response is the portal's critical path — every word, every image,
    # the principal's biography, the contact details — and in v8.5.4 one
    # unreadable field in it left five sites blank. A list with no fixed upper
    # bound is exactly what should not grow inside it.
    #
    # The SWITCH stays, because the page needs to know whether to reserve the
    # section before the board arrives. That is also the race this re-creates:
    # the switch is here and the content is elsewhere, so the portal must hold
    # the switch in `state.sectionsOff` and honour it in the renderer — the
    # v8.5.3 defect, designed around rather than rediscovered.
    for served_separately in ("showcase_items", "showcase_categories"):
        row["website_profile"].pop(served_separately, None)
    row["websiteProfile"] = row["website_profile"]
    # 42KB that every visitor to a studio's home page fetched in full, on every
    # load, with no ETag and a Vary: Cookie that stopped any shared cache from
    # helping. A studio's brand changes when someone edits it, which the ETag
    # notices; 60 seconds is short enough that an owner clicking Publish sees the
    # result while they are still looking at it.
    return _cacheable_json({"brand": row}, max_age=60)




# ──────────────────────────────────────────────
# v8.9.0: the public timetable
#
# `class_schedules` stores a RULE — "every Wednesday at four". A visitor wants
# DATES. Turning one into the other is this endpoint's whole job, and it is
# done on the server for a reason that has already cost this product once:
# dates.
#
#   The studio's week is defined in `tenants.timezone`. A parent opening the
#   page from another timezone, or at 11pm on a Sunday, must see the studio's
#   days — not their device's. `/v1/...` dates are RFC 1123 elsewhere in this
#   API precisely because a client-side reinterpretation once silently shifted
#   them by a day. Here the projection, "today", and the week boundaries are
#   all computed against the tenant's zone before anything is serialised.
# ──────────────────────────────────────────────

def _timetable_occurrences(conn, tenant_id: str, weeks: int, timezone_name: str):
    """Project public weekly rules onto real dates, exceptions applied.

    Returns (today, [(date, schedule_row, exception_or_None)]) ordered by date
    then start time. Cancelled dates are INCLUDED and flagged, never dropped:
    a class that silently disappears for one week looks like a broken website,
    while one struck through and labelled 停课 · 公众假期 looks like a studio
    that is minding the shop.
    """

    import datetime as _dt

    today = _dt.datetime.now(ZoneInfo(timezone_name)).date()
    horizon = today + _timedelta(days=weeks * 7)
    rows = fetch_all(
        conn,
        """
        SELECT cs.id, cs.label, cs.weekday,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, cs.capacity, cs.room,
               c.name AS course_name, c.description AS course_description,
               c.age_range, c.price_aud_cents,
               COALESCE(NULLIF(m.public_display_name, ''), u.full_name) AS teacher_name,
               COALESCE(m.show_on_public_timetable, false) AS teacher_public,
               (SELECT count(*) FROM class_schedule_students css
                 WHERE css.schedule_id = cs.id) AS enrolled
        FROM class_schedules cs
        LEFT JOIN courses c ON c.id = cs.course_id
        LEFT JOIN users u ON u.id = cs.teacher_user_id
        LEFT JOIN memberships m
               ON m.user_id = cs.teacher_user_id AND m.tenant_id = cs.tenant_id
        WHERE cs.tenant_id = %s AND cs.is_active AND cs.is_public
        ORDER BY cs.start_time, lower(cs.label)
        """,
        (tenant_id,),
    )
    exceptions = {
        (str(r["schedule_id"]), r["on_date"]): r
        for r in fetch_all(
            conn,
            "SELECT schedule_id, on_date, cancelled, note FROM class_schedule_exceptions "
            "WHERE tenant_id = %s AND on_date >= %s AND on_date < %s",
            (tenant_id, today, horizon),
        )
    }
    # Approved bookings hold seats; pending ones deliberately do not. See
    # `public_class_booking` — a request nobody has looked at yet must not
    # block a family who would actually turn up.
    booked: dict[tuple[str, object], int] = {}
    for r in fetch_all(
        conn,
        "SELECT schedule_id, on_date, count(*) AS n FROM class_bookings "
        "WHERE tenant_id = %s AND status = 'approved' AND on_date >= %s AND on_date < %s "
        "GROUP BY schedule_id, on_date",
        (tenant_id, today, horizon),
    ):
        booked[(str(r["schedule_id"]), r["on_date"])] = int(r["n"] or 0)

    out = []
    for offset in range((horizon - today).days):
        day = today + _timedelta(days=offset)
        # class_schedules.weekday follows JS getDay(): 0=Sunday..6=Saturday.
        weekday = day.isoweekday() % 7
        for row in rows:
            if int(row["weekday"]) != weekday:
                continue
            key = (str(row["id"]), day)
            out.append((day, row, exceptions.get(key), booked.get(key, 0)))
    return today, out




def _timetable_entry(day, row, exception, approved, fields, want_booking):
    """One class on one date, as the public page receives it.

    Two rules run through every line here:

    * **The switch is a ceiling, the content is a floor — intersect them.** A
      field turned on with nothing behind it prints nothing, so a studio never
      publishes an empty "Room:".
    * **No internal identifiers leave.** The occurrence is addressed by date
      and start time. Emitting the schedule uuid would turn a primary key into
      a public contract we could never rebuild the row without honouring.
    """

    cancelled = bool(exception and exception["cancelled"])
    capacity = int(row["capacity"] or 0)
    taken = int(row["enrolled"] or 0) + int(approved or 0)
    seats_left = max(0, capacity - taken)

    entry = {
        "date": day.isoformat(),
        "start": row["start_time"],
        "title": row["course_name"] or row["label"] or "",
        # The label becomes a subtitle only when it is not already the title —
        # "Wednesday group" under "Kids Oil Painting" is useful, under itself
        # it is noise.
        "subtitle": row["label"] if (row["course_name"] and row["label"]) else "",
        "cancelled": cancelled,
        "note": (exception["note"] if exception else "") or "",
    }
    if fields.get("teacher") and row["teacher_public"] and row["teacher_name"]:
        # AND, never OR. The layout preference and the person's consent are
        # different questions, and consent wins.
        entry["teacher"] = row["teacher_name"]
    if fields.get("room") and row["room"]:
        entry["room"] = row["room"]
    if fields.get("age_range") and row["age_range"]:
        entry["ageRange"] = row["age_range"]
    if fields.get("duration") and row["duration_minutes"]:
        entry["durationMinutes"] = int(row["duration_minutes"])
        entry["end"] = _end_of_class(row["start_time"], int(row["duration_minutes"]))
    if fields.get("price") and row["price_aud_cents"]:
        entry["priceAudCents"] = int(row["price_aud_cents"])
    if fields.get("capacity") and capacity > 0:
        entry["capacity"] = capacity
        entry["seatsLeft"] = seats_left
        # Proportional, not absolute. Capacity runs from 1 (one-to-one) to 30
        # (a big class), and "nearly full" at a fixed 3 is wrong at both ends.
        entry["nearlyFull"] = 0 < seats_left <= max(1, -(-capacity * 25 // 100))
    if want_booking and not cancelled:
        entry["bookable"] = True
    return entry




def _end_of_class(start: str, minutes: int) -> str:
    """HH:MM plus a duration, wrapping at midnight rather than overflowing."""

    try:
        hour, minute = (int(part) for part in str(start).split(":", 1))
    except (TypeError, ValueError):
        return ""
    total = (hour * 60 + minute + max(0, minutes)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"




@api_v1.route("/public/<tenant_slug>/timetable", methods=["GET"])
def public_timetable(tenant_slug: str):
    """Upcoming public classes for one studio, as dates rather than rules.

    Its own endpoint and its own page. `/brand` carries only the switch, for
    the same reason the showcase board does: `/brand` is the portal's critical
    path, and a list with no fixed upper bound does not belong in it.

    Never emits a student's name. `seatsLeft` is an aggregate — a count, not a
    roster — and the names behind it stay on the private side of this wall.
    """

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        row = fetch_one(
            conn,
            "SELECT name, COALESCE(settings->'website_profile', '{}'::jsonb) AS website "
            "FROM tenants WHERE id = %s",
            (tenant.tenant_id,),
        )
        profile = _normalize_website_profile((row or {}).get("website") or {})
        if not profile.get("show_timetable"):
            # Off is not an error and not a 404. The page renders its own
            # "nothing published yet" state rather than a failure.
            return jsonify({"enabled": False, "days": [], "timezone": "",
                            "weeks": 0, "booking": False})

        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        weeks = profile.get("timetable_weeks") or TIMETABLE_DEFAULT_WEEKS
        fields = profile.get("timetable_fields") or dict(TIMETABLE_FIELD_DEFAULTS)
        want_booking = bool(profile.get("show_timetable_booking"))
        today, occurrences = _timetable_occurrences(
            conn, tenant.tenant_id, weeks, timezone_name)

    days: list[dict] = []
    for day, schedule, exception, approved in occurrences:
        entry = _timetable_entry(day, schedule, exception, approved, fields, want_booking)
        if not days or days[-1]["date"] != entry["date"]:
            days.append({"date": entry["date"],
                         "weekday": day.isoweekday() % 7,
                         "classes": []})
        days[-1]["classes"].append(entry)

    return jsonify({
        "enabled": True,
        "timezone": timezone_name,
        "today": today.isoformat(),
        "weeks": weeks,
        "booking": want_booking,
        "fields": fields,
        "label": profile.get("timetable_label") or {"zh": "", "en": ""},
        "lead": profile.get("timetable_lead") or {"zh": "", "en": ""},
        "studio": (row or {}).get("name") or "",
        "days": days,
    })




@api_v1.route("/public/<tenant_slug>/timetable/book", methods=["POST"])
def public_class_booking(tenant_slug: str):
    """Ask for a place in one class, on one date, without an account.

    Three decisions carry this endpoint, and every one of them is about what
    the RESPONSE says rather than what the database stores.

    **1. The reply must not reveal whether this phone belongs to a student.**
    The server does match the name and phone against existing students — the
    CMS needs to know — but the body returned is byte-for-byte the same either
    way. Otherwise the form stops being a form: type a number, watch for a
    different answer, and you have a way to ask "is this person enrolled
    here?" about anyone. That is not a hypothetical; it is the same endpoint
    used slightly differently.

    **2. A pending request does not hold a seat.** Capacity is re-checked at
    approval, not here. A tap that nobody has looked at yet must not lock out
    a family who would actually turn up, and by approval time this moment's
    arithmetic is stale anyway.

    **3. But the parent is told where they stand.** A class showing "1 place
    left" that quietly collects five requests will disappoint four people. The
    reply says how many are already waiting, and hands the choice back.

    Booking is bounded by the same `timetable_weeks` the page projects: a date
    a visitor cannot see is a date they cannot ask for. Deliberately not a
    second setting — two horizons drift apart, and the person who finds the
    drift is always the parent.
    """

    from .services.student_access import find_student, normalize_phone

    payload = _json_payload()
    name = _clean_text(payload, "name", _clean_text(payload, "contactName"))[:80]
    phone_raw = _clean_text(payload, "phone", _clean_text(payload, "contactPhone"))[:40]
    phone = normalize_phone(phone_raw)
    message = _clean_text(payload, "message")[:300]
    start = _clean_text(payload, "start", _clean_text(payload, "startTime"))
    language = _clean_text(payload, "language")[:8]
    if not name or not phone:
        return _error("Please give a full name and a contact phone number.")
    if not re.match(r"^\d{2}:\d{2}$", start):
        return _error("Please choose a class from the timetable.")
    try:
        on_date = _roster_date(payload.get("date"))
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        # Same limiter shape as the balance lookup this borrows its identity
        # rule from — the form is only worth rate-limiting because it can be
        # asked repeatedly, which is exactly what decision 1 is about.
        if _rate_limited(f"booking:{tenant.tenant_id}:{_client_ip()}", 10):
            return _error("Too many requests. Please try again shortly.", 429)

        row = fetch_one(
            conn,
            "SELECT COALESCE(settings->'website_profile', '{}'::jsonb) AS website "
            "FROM tenants WHERE id = %s",
            (tenant.tenant_id,),
        )
        profile = _normalize_website_profile((row or {}).get("website") or {})
        if not (profile.get("show_timetable") and profile.get("show_timetable_booking")):
            return _error("This studio is not taking booking requests here.", 404)

        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        weeks = profile.get("timetable_weeks") or TIMETABLE_DEFAULT_WEEKS
        today, occurrences = _timetable_occurrences(
            conn, tenant.tenant_id, weeks, timezone_name)

        # Addressed by date and start time, never by uuid: the public page was
        # never given one. This also means an occurrence that is not currently
        # published simply cannot be booked.
        match = next(
            (item for item in occurrences
             if item[0] == on_date and item[1]["start_time"] == start),
            None,
        )
        if match is None:
            return _error(
                "That class is not on the published timetable. Please pick one from the list.",
                404,
            )
        _day, schedule, exception, approved = match
        if exception and exception["cancelled"]:
            return _error("That class is not running on this date.")

        capacity = int(schedule["capacity"] or 0)
        taken = int(schedule["enrolled"] or 0) + int(approved or 0)
        seats_left = max(0, capacity - taken)
        class_title = schedule["course_name"] or schedule["label"] or ""

        # Matching happens here and the result goes ONLY into the record. It
        # never reaches the branch that builds the response.
        #
        # "matched" is the service's word, and it is the ONLY status that means
        # one unambiguous person: "ambiguous" (two students share a name and a
        # number) and "missing" both have to fall through to the new-enquiry
        # path. Guessing between two families is worse than asking.
        lookup = find_student(conn, tenant_id=tenant.tenant_id, name=name, phone=phone)
        student_id = (lookup.student or {}).get("id") if lookup.status == "matched" else None

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO class_bookings
                    (tenant_id, schedule_id, on_date, student_id, contact_name,
                     contact_phone, message, privacy_notice_version, source_language, campaign)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (schedule_id, on_date, contact_phone)
                    WHERE status = 'pending' DO NOTHING
                RETURNING id
                """,
                (tenant.tenant_id, schedule["id"], on_date, student_id, name, phone,
                 message, PRIVACY_NOTICE_VERSION, language,
                 json.dumps(_campaign_from_payload(payload), ensure_ascii=False)),
            )
            created = cur.fetchone()
            cur.execute(
                "SELECT count(*) AS n FROM class_bookings "
                "WHERE schedule_id = %s AND on_date = %s AND status = 'pending'",
                (schedule["id"], on_date),
            )
            waiting = int((cur.fetchone() or {}).get("n") or 0)
        if created:
            _cms_notifications.create(
                conn,
                tenant_id=tenant.tenant_id,
                notification_type="class_booking.created",
                title="新约课申请",
                summary=f"{name} · {class_title or '课程'} · {on_date.isoformat()} {start}",
                resource_type="class_booking",
                resource_id=str(created["id"]),
                target_tab="pending",
                target_subtab="bookings",
                dedupe_key=f"class_booking:{created['id']}",
            )
        # The booking and its CMS notification must be durable before an SMTP
        # attempt, and a duplicate submission must never send a second alert.
        conn.commit()
        if created is not None:
            tenant_row = fetch_one(
                conn,
                """
                SELECT name, contact_email,
                       settings->>'studio_admin_email' AS studio_admin_email
                FROM tenants
                WHERE id = %s
                """,
                (tenant.tenant_id,),
            )
            admin_email = (
                (tenant_row.get("studio_admin_email") or tenant_row.get("contact_email") or "").strip()
                if tenant_row else ""
            )
            if admin_email:
                _notifications.send_safely(
                    conn,
                    tenant_id=tenant.tenant_id,
                    template_key="class_booking_admin_alert",
                    to_email=admin_email,
                    context={
                        "booking_id": str(created["id"]),
                        "class_title": class_title or "—",
                        "class_date": on_date.isoformat(),
                        "start_time": start,
                        "contact_name": name,
                        "mobile": phone,
                        "message": message or "—",
                        "studio_name": tenant_row["name"] or tenant_slug,
                    },
                )
                conn.commit()

    return jsonify({
        "ok": True,
        # `duplicate` is not an error. A parent who is unsure the first tap
        # worked taps again; the honest answer is "we already have it", not a
        # red box and not a second row in somebody's queue.
        "duplicate": created is None,
        "seatsLeft": seats_left,
        "waiting": waiting,
        "date": on_date.isoformat(),
        "start": start,
        "title": class_title,
    })




def _campaign_from_payload(payload: dict) -> dict:
    """The UTM-ish fields a public form may carry, bounded and stringified."""

    raw = payload.get("campaign")
    if not isinstance(raw, dict):
        return {}
    return {
        str(key)[:40]: str(value or "")[:120]
        for key, value in list(raw.items())[:8]
        if str(key).strip()
    }




_PUBLIC_ANALYTICS_EVENTS = {
    "page_view",
    "cta_click",
    "registration_started",
    "registration_submitted",
}



def _analytics_text_map(value: object, *, keys: set[str], limit: int) -> dict[str, str]:
    """Return only allowlisted, bounded strings for an analytics JSON field."""

    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key in keys:
        item = str(value.get(key) or "").strip()[:limit]
        if item:
            cleaned[key] = item
    return cleaned




@api_v1.route("/public/<tenant_slug>/analytics", methods=["POST"])
def public_record_analytics(tenant_slug: str):
    """Record one anonymous, allowlisted portal conversion event.

    The supplied browser token is salted and hashed before persistence. The
    table never receives an IP address, user agent, student identifier, name,
    phone, email, or raw token.
    """

    if _rate_limited(f"analytics:{tenant_slug}:{_client_ip()}", 60):
        return _error("Too many analytics events.", 429)
    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    event_name = str(payload.get("event") or "").strip()
    if event_name not in _PUBLIC_ANALYTICS_EVENTS:
        return _error("Unsupported analytics event.")
    browser_token = str(payload.get("sessionId") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", browser_token):
        return _error("A valid anonymous session ID is required.")
    path = str(payload.get("path") or "").strip()[:200]
    if path and (not path.startswith("/") or "\n" in path or "\r" in path):
        return _error("Analytics path is invalid.")
    campaign = _analytics_text_map(
        payload.get("campaign"),
        keys={"source", "medium", "campaign"},
        limit=80,
    )
    metadata = _analytics_text_map(payload.get("metadata"), keys={"label"}, limit=80)
    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        secret = str(current_app.config.get("SECRET_KEY") or current_app.secret_key or "")
        session_hash = hashlib.sha256(
            f"{secret}:{tenant.tenant_id}:{browser_token}".encode("utf-8")
        ).hexdigest()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public_analytics_events (
                    tenant_id, event_name, path, session_hash, campaign, metadata
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (
                    tenant.tenant_id,
                    event_name,
                    path,
                    session_hash,
                    json.dumps(campaign),
                    json.dumps(metadata),
                ),
            )
    return jsonify({"ok": True}), 202




def _public_portfolio_copy(value: object) -> str:
    """Remove obvious contact details and seeded full-name titles from public copy."""

    text = str(value or "").strip()[:500]
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\s().-]*){8,}", text):
        return ""
    if re.match(r"^.+['’]s\s+Demo\s+Work$", text, re.IGNORECASE):
        return "Student artwork"
    return text




@api_v1.route("/public/<tenant_slug>/showcase", methods=["GET"])
def public_showcase(tenant_slug: str):
    """The studio's own work, paginated, limited by the tenant's plan.

    Its own endpoint rather than a field on `/brand` for one reason: `/brand`
    is the critical path. Every word and every image of a portal arrives in
    that one response, and in v8.5.4 a single unreadable field in it took five
    sites blank. A list with no fixed upper bound does not belong there.

    **Publishing is limited here; storing is not limited anywhere.** A tenant
    that drops from growth (150) to starter (15) keeps all 150 works in its
    record — this endpoint serves the first 15. Upgrading restores the rest
    with no migration, because nothing was ever removed. A valid
    ``featured_rank`` is applied before that cap, so editorial intent survives
    a plan change without turning the rank into a second quota.

    The plan limit is applied BEFORE the category filter, not after. The other
    order would let a studio on the entry plan publish its whole archive by
    splitting it across drawers and linking each one. ``surface=home`` is a
    server-controlled six-item preview; all other requests use the twelve-item
    C-scheme page size.
    """

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        row = fetch_one(
            conn,
            "SELECT COALESCE(settings->'website_profile', '{}'::jsonb) AS website, "
            "       COALESCE(settings->>'category', 'general') AS category "
            "FROM tenants WHERE id = %s",
            (tenant.tenant_id,),
        )
        limit = showcase_limit_for(conn, tenant.tenant_id)

    profile = _normalize_website_profile((row or {}).get("website") or {})
    if not profile.get("show_showcase"):
        # Switched off is not an error, and not a 404 either: the section
        # simply has nothing to say.
        return jsonify({"enabled": False, "items": [], "categories": [],
                        "total": 0, "offset": 0, "hasMore": False})

    # Plan capacity applies only to active works.  Drafts and archived works
    # remain in the private workspace, so a downgrade never destroys them and
    # an upgrade can reveal them again after the owner marks them active.
    # Editorial rank is applied before the entitlement cap: the works the
    # owner deliberately selected are the ones that remain public when a plan
    # has fewer slots, while the displaced records stay stored and recoverable.
    active_items = [
        item for item in profile.get("showcase_items", [])
        if item.get("publication_state") == "active"
    ]
    published = _ordered_showcase_items(active_items)[:limit]
    categories = profile.get("showcase_categories", [])

    wanted = (request.args.get("category") or "").strip()[:24]
    if wanted and any(c["id"] == wanted for c in categories):
        visible = [item for item in published if item.get("category_id") == wanted]
    else:
        wanted, visible = "", published

    try:
        offset = max(0, int(request.args.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    surface = (request.args.get("surface") or "").strip().lower()
    page_size = SHOWCASE_PREVIEW_SIZE if surface == "home" else SHOWCASE_PAGE_SIZE
    page = visible[offset:offset + page_size]

    return jsonify({
        "enabled": True,
        "category": wanted,
        # Only the drawers that actually hold a published work. An empty
        # filter chip is a dead end the visitor has to discover by pressing it.
        "categories": [c for c in categories
                       if any(i.get("category_id") == c["id"] for i in published)],
        "items": page,
        "total": len(visible),
        "offset": offset,
        "pageSize": page_size,
        "nextOffset": offset + len(page),
        "hasMore": offset + len(page) < len(visible),
    })




@api_v1.route("/public/<tenant_slug>/gallery", methods=["GET"])
def public_gallery(tenant_slug: str):
    """Return public-gallery portfolio items explicitly shared by a tenant."""

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return jsonify({"items": [], "featureEnabled": False})
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.title, p.description, p.artwork_date, p.created_at
            FROM portfolio_items p
            JOIN media_assets m ON m.id = p.media_asset_id AND m.tenant_id = p.tenant_id
            JOIN media_variants mv
              ON mv.tenant_id = p.tenant_id
             AND mv.media_asset_id = p.media_asset_id
             AND mv.variant = 'display'
            JOIN students s ON s.id = p.student_id AND s.tenant_id = p.tenant_id
            JOIN LATERAL (
                SELECT status
                FROM student_publication_consent_events e
                WHERE e.tenant_id = p.tenant_id AND e.student_id = p.student_id
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
            ) consent ON consent.status = 'confirmed'
            WHERE p.tenant_id = %s
              AND p.visibility = 'shared'
              AND p.public_consent_at IS NOT NULL
              AND s.status <> 'archived'
            ORDER BY COALESCE(p.artwork_date, p.created_at::date) DESC, p.created_at DESC
            LIMIT 24
            """,
            (tenant.tenant_id,),
        )
    items = [
        {
            "id": str(row["id"]),
            "title": _public_portfolio_copy(row["title"]),
            "comment": _public_portfolio_copy(row["description"]),
            "date": str(row["artwork_date"] or row["created_at"].date()),
            "mediaUrl": f"/v1/public/{tenant_slug}/gallery/{row['id']}/media",
        }
        for row in rows
    ]
    return jsonify({"items": items})




@api_v1.route("/public/<tenant_slug>/gallery/<portfolio_item_id>/media", methods=["GET"])
def public_gallery_media(tenant_slug: str, portfolio_item_id: str):
    """Serve media for a public-gallery item without exposing private portfolios."""

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 404)
        row = fetch_one(
            conn,
            """
            SELECT p.media_asset_id
            FROM portfolio_items p
            JOIN students s ON s.id = p.student_id AND s.tenant_id = p.tenant_id
            JOIN media_variants mv
              ON mv.tenant_id = p.tenant_id
             AND mv.media_asset_id = p.media_asset_id
             AND mv.variant = 'display'
            JOIN LATERAL (
                SELECT status
                FROM student_publication_consent_events e
                WHERE e.tenant_id = p.tenant_id AND e.student_id = p.student_id
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
            ) consent ON consent.status = 'confirmed'
            WHERE p.tenant_id = %s
              AND p.id::text = %s
              AND p.visibility = 'shared'
              AND p.public_consent_at IS NOT NULL
              AND s.status <> 'archived'
            LIMIT 1
            """,
            (tenant.tenant_id, portfolio_item_id),
        )
        if not row:
            return _error("Portfolio item was not found.", 404)
        response = _send_media_asset(
            conn,
            tenant_id=tenant.tenant_id,
            media_asset_id=str(row["media_asset_id"]),
            variant="display",
        )
        if isinstance(response, tuple):
            return response
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response




@api_v1.route("/public/<tenant_slug>/balance-query", methods=["POST"])
def public_balance_query(tenant_slug: str):
    """Return low-sensitivity balance data after an exact, unambiguous match."""

    client_key = f"balance-query:{tenant_slug}:{_client_ip()}"
    if _rate_limited(client_key, 10):
        return _error("Too many balance queries. Please wait a moment.", 429)

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    code = str(payload.get("accessCode") or payload.get("code") or "").strip()
    if not name or not phone:
        return jsonify({"match": False, "error": "name_and_phone_required"}), 400
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        lookup = _find_public_student(
            conn,
            tenant_id=tenant.tenant_id,
            name=name,
            phone=phone,
        )
        # Name+phone alone is an enrolment/balance oracle for anyone holding
        # (or guessing) a family's details. Once the studio issues a student
        # an access code, that code becomes required here too — same secret
        # as the private area. Codeless students keep the legacy behaviour so
        # studios can adopt codes at their own pace.
        if lookup.student:
            stored_hash = str(lookup.student.get("access_code_hash") or "")
            code_active = bool(stored_hash) and not lookup.student.get("access_code_revoked_at")
            if code_active and not _verify_student_access_code(lookup.student, code):
                fingerprint = _student_lookup_fingerprint(name, phone)
                _record_student_access_failure(
                    conn,
                    tenant_id=tenant.tenant_id,
                    lookup_hash=fingerprint,
                    ip_address=_client_ip(),
                )
                _audit_request(
                    conn,
                    tenant_id=tenant.tenant_id,
                    action="public.balance_lookup",
                    resource_type="student_lookup",
                    metadata={"matched": False, "access_code_required": True},
                )
                conn.commit()
                return jsonify({"match": False, "accessCodeRequired": True})
        row = None
        if lookup.student:
            row = fetch_one(
                conn,
                """
                SELECT s.display_name, COALESCE(ca.balance, 0)::float AS balance
                FROM students s
                LEFT JOIN credit_accounts ca
                  ON ca.tenant_id = s.tenant_id
                 AND ca.student_id = s.id
                 AND ca.course_id IS NULL
                WHERE s.tenant_id = %s AND s.id = %s
                """,
                (tenant.tenant_id, lookup.student["id"]),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="public.balance_lookup",
            resource_type="student_lookup",
            metadata={"matched": bool(row), "ambiguous": lookup.status == "ambiguous"},
        )
        conn.commit()
        if not row:
            return jsonify({"match": False, "ambiguous": lookup.status == "ambiguous"})
        return jsonify(
            {
                "match": True,
                "name": row["display_name"],
                "balance": row["balance"],
            }
        )




_DUMMY_ACCESS_HASH: list[str] = []



def _dummy_access_verify(code: str) -> None:
    """Burn the same PBKDF2 work as a real verification.

    Without this, a miss on (name, phone) returns immediately while a hit
    spends ~100ms hashing — a timing oracle for pair validity. The dummy
    hash is computed once, lazily, so import stays cheap.
    """

    if not _DUMMY_ACCESS_HASH:
        _DUMMY_ACCESS_HASH.append(_auth_hash_password("000000"))
    _auth_verify_password(code or "000000", _DUMMY_ACCESS_HASH[0])




@api_v1.route("/public/<tenant_slug>/student/unlock", methods=["POST"])
def public_student_unlock(tenant_slug: str):
    """Issue a one-hour HttpOnly student session after access-code verification."""

    # Flat per-IP ceiling on top of the per-identity DB lockout: the lockout
    # stops repeated guesses at ONE family but not one IP spraying many
    # identities at one guess each.
    if _rate_limited(f"student-unlock:{tenant_slug}:{_client_ip()}", 10):
        return _error("Too many attempts. Please wait a minute.", 429)

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    code = str(payload.get("code") or "").strip()
    if not name or not phone or len(code) != 6 or not code.isdigit():
        return _error("Name, phone, and a six-digit access code are required.", 400)

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        fingerprint = _student_lookup_fingerprint(name, phone)
        lock_seconds = _student_access_lock_seconds(
            conn,
            tenant_id=tenant.tenant_id,
            lookup_hash=fingerprint,
            ip_address=_client_ip(),
        )
        if lock_seconds:
            # Retry-After lets the portal tell the family how long to wait
            # instead of an open-ended "please try again later".
            response = _error("Too many attempts. Please try again later.", 429)
            body, status = response if isinstance(response, tuple) else (response, 429)
            body.headers["Retry-After"] = str(lock_seconds)
            return body, status
        lookup = _find_public_student(
            conn, tenant_id=tenant.tenant_id, name=name, phone=phone
        )
        verified = bool(lookup.student) and _verify_student_access_code(lookup.student, code)
        if not lookup.student or not str((lookup.student or {}).get("access_code_hash") or ""):
            _dummy_access_verify(code)
        if not verified:
            _record_student_access_failure(
                conn,
                tenant_id=tenant.tenant_id,
                lookup_hash=fingerprint,
                ip_address=_client_ip(),
            )
            _audit(
                conn,
                tenant_id=tenant.tenant_id,
                action="student_access.failed",
                resource_type="student_access",
                metadata={"ambiguous": lookup.status == "ambiguous"},
            )
            conn.commit()
            return _error("The login details could not be verified.", 401)

        _clear_student_access_failures(
            conn,
            tenant_id=tenant.tenant_id,
            lookup_hash=fingerprint,
            ip_address=_client_ip(),
        )
        raw_token, expires_at = _create_student_access_session(
            conn,
            tenant_id=tenant.tenant_id,
            student_id=str(lookup.student["id"]),
            ip_address=_client_ip(),
        )
        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action="student_access.unlocked",
            resource_type="student",
            resource_id=str(lookup.student["id"]),
        )
        conn.commit()

    response = make_response(
        jsonify(
            {
                "ok": True,
                "name": lookup.student["display_name"],
                "expiresAt": expires_at,
            }
        )
    )
    response.set_cookie(
        _student_cookie_name(),
        raw_token,
        max_age=3600,
        secure=_student_cookie_secure(),
        httponly=True,
        samesite="Lax",
        path="/",
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response




@api_v1.route("/public/<tenant_slug>/student/private", methods=["GET"])
def public_student_private(tenant_slug: str):
    """Return private records for the student bound to the HttpOnly session."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        access = _resolve_student_access_session(
            conn, tenant_id=tenant.tenant_id, raw_token=_student_cookie_token()
        )
        if not access:
            return _error("Student access is required.", 401)
        student_id = str(access["student_id"])
        summary = fetch_one(
            conn,
            """
            SELECT s.display_name, COALESCE(ca.balance, 0)::float AS balance
            FROM students s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id
             AND ca.student_id = s.id
             AND ca.course_id IS NULL
            WHERE s.tenant_id = %s AND s.id = %s
            """,
            (tenant.tenant_id, student_id),
        )
        attendance = fetch_all(
            conn,
            """
            SELECT a.class_date::text AS date,
                   CASE WHEN a.reversed_at IS NULL THEN 'attended' ELSE 'voided' END AS status,
                   COALESCE(c.name, '') AS course,
                   a.note
            FROM attendance_sessions a
            LEFT JOIN courses c ON c.tenant_id = a.tenant_id AND c.id = a.course_id
            WHERE a.tenant_id = %s AND a.student_id = %s
            ORDER BY a.class_date DESC, a.attended_at DESC
            LIMIT 50
            """,
            (tenant.tenant_id, student_id),
        )
        portfolio = fetch_all(
            conn,
            """
            SELECT p.id, p.media_asset_id, p.title, p.description,
                   COALESCE(p.artwork_date, p.created_at::date)::text AS date
            FROM portfolio_items p
            JOIN media_variants mv
              ON mv.tenant_id = p.tenant_id
             AND mv.media_asset_id = p.media_asset_id
             AND mv.variant = 'display'
            WHERE p.tenant_id = %s AND p.student_id = %s
            ORDER BY COALESCE(p.artwork_date, p.created_at::date) DESC, p.created_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id, student_id),
        )
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        next_class = fetch_one(
            conn,
            """
            SELECT cs.label AS course, to_char(cs.start_time, 'HH24:MI') AS time,
                   ((now() AT TIME ZONE %s)::date
                     + ((cs.weekday - extract(dow FROM (now() AT TIME ZONE %s)::date)::int + 7) %% 7)
                   )::text AS date
            FROM class_schedules cs
            JOIN class_schedule_students css
              ON css.tenant_id = cs.tenant_id AND css.schedule_id = cs.id
            WHERE cs.tenant_id = %s AND css.student_id = %s AND cs.is_active
            ORDER BY ((cs.weekday - extract(dow FROM (now() AT TIME ZONE %s)::date)::int + 7) %% 7),
                     cs.start_time
            LIMIT 1
            """,
            (timezone_name, timezone_name, tenant.tenant_id, student_id, timezone_name),
        )
    response = jsonify(
        {
            "ok": True,
            "student": {
                "name": summary["display_name"],
                "balance": summary["balance"],
            },
            "nextClass": next_class,
            "attendance": attendance,
            "portfolio": [
                {
                    "id": str(row["id"]),
                    "title": row["title"] or "",
                    "comment": row["description"] or "",
                    "date": row["date"],
                    "mediaUrl": f"/v1/public/{tenant_slug}/student/media/{row['media_asset_id']}",
                }
                for row in portfolio
            ],
        }
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response




@api_v1.route("/public/<tenant_slug>/student/media/<media_asset_id>", methods=["GET"])
def public_student_media(tenant_slug: str, media_asset_id: str):
    """Serve a safe display derivative owned by the unlocked student."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        access = _resolve_student_access_session(
            conn, tenant_id=tenant.tenant_id, raw_token=_student_cookie_token()
        )
        if not access:
            return _error("Media asset was not found.", 404)
        owned = fetch_one(
            conn,
            """
            SELECT 1 FROM media_assets
            WHERE tenant_id = %s AND id = %s AND owner_student_id = %s
            """,
            (tenant.tenant_id, media_asset_id, access["student_id"]),
        )
        if not owned:
            return _error("Media asset was not found.", 404)
        response = _send_media_asset(
            conn,
            tenant_id=tenant.tenant_id,
            media_asset_id=media_asset_id,
            variant="display",
        )
        if isinstance(response, tuple):
            return response
        response.headers["Cache-Control"] = "private, no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response




@api_v1.route("/public/<tenant_slug>/student/logout", methods=["POST"])
def public_student_logout(tenant_slug: str):
    """Revoke the current private session and clear both cookie variants."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        _revoke_student_access_session(
            conn, tenant_id=tenant.tenant_id, raw_token=_student_cookie_token()
        )
        conn.commit()
    response = make_response(jsonify({"ok": True}))
    for cookie_name in ("__Host-studiosaas-student", "studiosaas_student"):
        response.delete_cookie(
            cookie_name,
            path="/",
            secure=cookie_name.startswith("__Host-"),
            httponly=True,
            samesite="Lax",
        )
    response.headers["Cache-Control"] = "private, no-store"
    return response




@api_v1.route("/public/<tenant_slug>/registration-media", methods=["POST"])
def public_registration_media_upload(tenant_slug: str):
    """Upload a tenant-scoped registration photo before the registration is submitted."""

    if _rate_limited(f"registration-media:{_client_ip()}", 5):
        return _error("Too many uploads. Please wait a moment.", 429)

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        if not _plan_feature_enabled(conn, tenant.tenant_id, "public_registration"):
            return _error("Public registration is not available for this studio plan.", 403)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        try:
            media = _store_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                file_storage=f,
                kind="registration_photo",
            )
        except MediaUploadError as exc:
            return _media_error(exc)
        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action="registration_photo.uploaded",
            resource_type="media_asset",
            resource_id=media["id"],
            metadata={"byte_size": media["byte_size"]},
        )
    media_id = str(media["id"])
    return jsonify(
        {
            "ok": True,
            "mediaAssetId": media_id,
            "filename": _media_token(media_id),
            "url": f"/v1/public/{tenant_slug}/media/{media_id}",
        }
    )




@api_v1.route("/public/<tenant_slug>/portfolio-token", methods=["POST"])
def public_portfolio_token(tenant_slug: str):
    """Reject the retired URL-token flow in favour of HttpOnly student sessions."""

    return api_error(
        "This private portfolio flow has been retired. Use the student access-code session.",
        410,
        error="student_session_required",
    )




@api_v1.route("/public/<tenant_slug>/media/<media_asset_id>", methods=["GET"])
def public_media_asset(tenant_slug: str, media_asset_id: str):
    """Serve safe public brand media or token-protected portfolio media."""

    raw_token = request.args.get("token", "")
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        asset = fetch_one(
            conn,
            "SELECT asset_type, mime_type FROM media_assets WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, media_asset_id),
        )
        if not asset:
            return _error("Media asset was not found.", 404)
        if asset["asset_type"] in {"logo", "website_image"}:
            if str(asset["mime_type"] or "").startswith("image/svg"):
                return _error("Media asset was not found.", 404)
            return _send_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                media_asset_id=media_asset_id,
                variant="display",
            )
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Media asset was not found.", 404)
        if not raw_token:
            return _error("Media token is required.", 401)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        allowed = fetch_one(
            conn,
            """
            SELECT 1
            FROM share_tokens st
            JOIN media_assets m
              ON m.tenant_id = st.tenant_id
             AND m.owner_student_id = st.student_id
            WHERE st.tenant_id = %s
              AND st.token_hash = %s
              AND st.scope = 'student_portfolio'
              AND st.expires_at > now()
              AND st.revoked_at IS NULL
              AND m.id = %s
            LIMIT 1
            """,
            (tenant.tenant_id, token_hash, media_asset_id),
        )
        if not allowed:
            return _error("Media asset was not found.", 404)
        response = _send_media_asset(
            conn,
            tenant_id=tenant.tenant_id,
            media_asset_id=media_asset_id,
            variant="display",
        )
        if isinstance(response, tuple):
            return response
        response.headers["Cache-Control"] = "private, no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response




@api_v1.route("/public/<tenant_slug>/programs", methods=["GET"])
def public_programs(tenant_slug: str):
    """Public course catalogue for the tenant landing page (B5)."""

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        rows = fetch_all(
            conn,
            """
            SELECT name, description, category, age_range, duration_minutes,
                   price_aud_cents
            FROM courses
            WHERE tenant_id = %s AND is_active
            ORDER BY category, name
            LIMIT 50
            """,
            (tenant.tenant_id,),
        )
    programs = [
        {
            "name": row["name"],
            "description": row["description"] or "",
            "category": row["category"] or "",
            "ageRange": row["age_range"] or "",
            "durationMinutes": row["duration_minutes"],
            "priceAud": (row["price_aud_cents"] or 0) / 100.0,
        }
        for row in rows
    ]
    return jsonify({"ok": True, "programs": programs})




@api_v1.route("/public/<tenant_slug>/registrations", methods=["POST"])
def public_create_registration(tenant_slug: str):
    """Create a public registration for a tenant-backed register page.

    Rate-limited to 5 requests per minute per client IP to prevent spam.
    """

    # Simple rate limiting: 5 requests per minute per IP
    if _rate_limited(_client_ip(), 5):
        return _error("Too many registration attempts. Please wait a moment.", 429)

    payload = request.get_json(silent=True) or {}
    # S4 (LetsPaintCMS v6.6.5): honeypot — the registration form renders a
    # hidden `website` field humans never see. Bots that fill it get a
    # silent fake success: nothing is stored, no signal is leaked.
    if str(payload.get("website") or "").strip():
        return jsonify({"ok": True, "success": True, "message": "Registration received."})

    consent_value = payload.get(
        "privacyConsent",
        payload.get("privacy_consent", payload.get("consent", False)),
    )
    privacy_consent = consent_value is True or str(consent_value).strip().lower() in {"1", "true", "yes", "on"}
    if not privacy_consent:
        return _error("Privacy consent is required before submitting registration.", 400)
    privacy_notice_version = str(
        payload.get("privacyNoticeVersion")
        or payload.get("privacy_notice_version")
        or PRIVACY_NOTICE_VERSION
    ).strip()[:40]
    publication_raw = payload.get("publicationConsent", payload.get("publication_consent"))
    publication_consent = None
    if isinstance(publication_raw, dict) and bool(publication_raw.get("confirmed")):
        publication_consent = {
            "confirmed": True,
            "consentBy": str(publication_raw.get("consentBy") or publication_raw.get("consent_by") or "").strip()[:120],
            "relationship": str(publication_raw.get("relationship") or "").strip()[:60],
            "method": str(publication_raw.get("method") or "registration_form").strip()[:60],
            "noticeVersion": str(publication_raw.get("noticeVersion") or privacy_notice_version).strip()[:40],
            "note": str(publication_raw.get("note") or "Optional artwork publication consent recorded at registration.").strip()[:500],
        }
        if not publication_consent["consentBy"] or not publication_consent["relationship"]:
            return _error("Publication consent requires the consenting person and relationship.")
        payload["publicationConsent"] = publication_consent

    first_name = str(
        payload.get("firstName")
        or payload.get("first_name")
        or payload.get("studentFirstName")
        or payload.get("student_first_name")
        or ""
    ).strip()[:80]
    last_name = str(
        payload.get("lastName")
        or payload.get("last_name")
        or payload.get("studentLastName")
        or payload.get("student_last_name")
        or ""
    ).strip()[:80]
    parent_name = str(payload.get("parentName") or payload.get("parent_name") or "").strip()[:120]
    mobile = re.sub(r"[^0-9+]", "", str(payload.get("mobile") or payload.get("phone") or ""))[:40]
    email = str(payload.get("email") or "").strip().lower()[:120]
    message = str(payload.get("message") or payload.get("notes") or "").strip()[:500]
    source = str(payload.get("source") or "standalone_register").strip().lower()[:40]
    if source not in {"portal", "standalone_register", "qr", "campaign"}:
        source = "standalone_register"
    source_path = str(payload.get("sourcePath") or payload.get("source_path") or request.referrer or "").strip()[:500]
    source_language = str(payload.get("language") or payload.get("sourceLanguage") or "").strip().lower()[:10]
    if source_language not in {"zh", "en", "zh-cn", "en-au"}:
        source_language = ""
    campaign = {
        key: str(payload.get(key) or "").strip()[:120]
        for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
        if str(payload.get(key) or "").strip()
    }
    if not first_name or not mobile:
        return _error("firstName and mobile are required.")
    try:
        _validate_optional_email("email", email)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        plan = fetch_one(
            conn,
            """
            SELECT p.features
            FROM tenants t
            JOIN plans p ON p.code = t.plan_code
            WHERE t.id = %s
            """,
            (tenant.tenant_id,),
        )
        if not plan or not bool((plan.get("features") or {}).get("public_registration", False)):
            return _error("Public registration is not available for this studio plan.", 403)
        with conn.cursor() as cur:
            existing_student = _find_matching_student(
                cur,
                tenant_id=tenant.tenant_id,
                first_name=first_name,
                last_name=last_name,
                mobile=mobile,
            )
            duplicate_registration = None
            if not existing_student:
                duplicate_registration = _find_pending_registration(
                    cur,
                    tenant_id=tenant.tenant_id,
                    first_name=first_name,
                    last_name=last_name,
                    mobile=mobile,
                )
            if existing_student or duplicate_registration:
                duplicate_kind = "student" if existing_student else "pending"
                review_note = (
                    "Matched existing active student."
                    if existing_student
                    else "Matched an existing pending registration."
                )
                cur.execute(
                    """
                    INSERT INTO registrations (
                        tenant_id, status, first_name, last_name, parent_name,
                        mobile, email, message, payload, student_id,
                        duplicate_of_registration_id, review_note,
                        source, source_path, source_language, campaign,
                        privacy_consent_at, privacy_notice_version
                    )
                    VALUES (
                        %s, 'duplicate', %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s, %s, %s, %s::jsonb, now(), %s
                    )
                    RETURNING id
                    """,
                    (
                        tenant.tenant_id,
                        first_name,
                        last_name,
                        parent_name,
                        mobile,
                        email,
                        message,
                        json.dumps(payload),
                        str(existing_student["id"]) if existing_student else None,
                        str(duplicate_registration["id"]) if duplicate_registration else None,
                        review_note,
                        source,
                        source_path,
                        source_language,
                        json.dumps(campaign),
                        privacy_notice_version,
                    ),
                )
                registration_id = cur.fetchone()["id"]
                _audit(
                    conn,
                    tenant_id=tenant.tenant_id,
                    action="registration.duplicate_detected",
                    resource_type="registration",
                    resource_id=registration_id,
                    metadata={
                        "duplicate": duplicate_kind,
                        "student_id": str(existing_student["id"]) if existing_student else None,
                        "duplicate_of_registration_id": str(duplicate_registration["id"]) if duplicate_registration else None,
                        "privacy_notice_version": privacy_notice_version,
                    },
                )
                conn.commit()
                return jsonify(
                    {
                        "ok": False,
                        "success": False,
                        "duplicate": duplicate_kind,
                        "registration_id": registration_id,
                        "id": registration_id,
                        "student_id": str(existing_student["id"]) if existing_student else None,
                        "duplicate_of_registration_id": str(duplicate_registration["id"]) if duplicate_registration else None,
                        "error": (
                            "This student already exists. Please use the balance/portfolio lookup."
                            if existing_student
                            else "This registration is already waiting for review."
                        ),
                    }
                )
            cur.execute(
                """
                INSERT INTO registrations (
                    tenant_id, status, first_name, last_name, parent_name,
                    mobile, email, message, payload,
                    source, source_path, source_language, campaign,
                    privacy_consent_at, privacy_notice_version
                )
                VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, now(), %s)
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    first_name,
                    last_name,
                    parent_name,
                    mobile,
                    email,
                    message,
                    json.dumps(payload),
                    source,
                    source_path,
                    source_language,
                    json.dumps(campaign),
                    privacy_notice_version,
                ),
            )
            registration_id = cur.fetchone()["id"]
        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action="registration.created",
            resource_type="registration",
            resource_id=registration_id,
            metadata={
                "source": source,
                "language": source_language,
                "campaign": campaign,
                "privacy_notice_version": privacy_notice_version,
            },
        )
        source_label = {
            "portal": "门户",
            "qr": "二维码",
            "campaign": "活动页",
        }.get(source, "报名页")
        _cms_notifications.create(
            conn,
            tenant_id=tenant.tenant_id,
            notification_type="registration.created",
            title="新报名申请",
            summary=f"{first_name} {last_name}".strip() + f" · {source_label}",
            resource_type="registration",
            resource_id=str(registration_id),
            target_tab="pending",
            target_subtab="registrations",
            dedupe_key=f"registration:{registration_id}",
        )
        # Make the lead and its CMS notification durable before any SMTP work.
        # External delivery is best-effort and must never decide whether the
        # registration exists.
        conn.commit()
        tenant_row = fetch_one(
            conn,
            """
            SELECT name, contact_email,
                   settings->>'studio_admin_email' AS studio_admin_email
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        studio_name = tenant_row["name"] if tenant_row else tenant_slug
        if email:
            _notifications.send_safely(
                conn,
                tenant_id=tenant.tenant_id,
                template_key="registration_received",
                to_email=email,
                context={
                    "parent_name": parent_name or "there",
                    "student_name": f"{first_name} {last_name}".strip(),
                    "studio_name": studio_name,
                },
            )
        admin_email = (
            (tenant_row.get("studio_admin_email") or tenant_row.get("contact_email") or "").strip()
            if tenant_row else ""
        )
        if admin_email:
            _notifications.send_safely(
                conn,
                tenant_id=tenant.tenant_id,
                template_key="registration_admin_alert",
                to_email=admin_email,
                context={
                    "registration_id": str(registration_id),
                    "student_name": f"{first_name} {last_name}".strip(),
                    "contact_name": parent_name or f"{first_name} {last_name}".strip(),
                    "mobile": mobile or "—",
                    "email": email or "—",
                    "studio_name": studio_name,
                },
            )
        conn.commit()
    return jsonify({
        "ok": True,
        "success": True,
        "registration_id": registration_id,
        "id": registration_id,
        "message": "Registration received. The studio will contact you soon.",
    })




@api_v1.route("/public/plans", methods=["GET"])
def public_plans():
    """Pricing for the marketing site — public fields only, no auth.

    The rows come from `services.public_site.public_plan_rows`, which is also
    what renders the home page's pricing cards. One query for both means the
    JSON an integrator reads and the numbers a visitor sees cannot disagree;
    the reason its columns are named rather than starred is documented there.

    Prices are public by definition — they are printed on the marketing page
    this feeds — so there is nothing here an anonymous caller should not see.
    """

    response = jsonify({"plans": public_plan_rows()})
    # Pricing changes rarely and this is on the critical path of the public
    # home page; a short shared cache keeps a traffic spike off PostgreSQL.
    response.headers["Cache-Control"] = "public, max-age=300"
    return response




@api_v1.route("/public/portfolio/<raw_token>", methods=["GET"])
def public_shared_portfolio(raw_token: str):
    """Public JSON for the shared portfolio viewer page. Rate-limited."""

    if _rate_limited(f"shared-portfolio:{_client_ip()}", 20):
        return _error("Too many requests. Please wait a moment.", 429)

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with connect() as conn:
        link = fetch_one(
            conn,
            """
            SELECT st.tenant_id, st.student_id, st.expires_at,
                   t.slug AS tenant_slug, t.name AS tenant_name,
                   t.primary_color, t.secondary_color,
                   t.settings->>'logo_url' AS logo_url,
                   s.display_name AS student_name
            FROM share_tokens st
            JOIN tenants t ON t.id = st.tenant_id
            JOIN students s ON s.id = st.student_id
            WHERE st.token_hash = %s
              AND st.scope = 'student_portfolio'
              AND st.expires_at > now()
              AND st.revoked_at IS NULL
            """,
            (token_hash,),
        )
        if not link:
            return _error("This link is invalid, expired, or has been revoked.", 410)
        if not _plan_feature_enabled(conn, link["tenant_id"], "portfolio"):
            return _error("This portfolio is not available for the current studio plan.", 410)
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.media_asset_id, p.title, p.description, p.artwork_date, p.created_at
            FROM portfolio_items p
            JOIN media_assets m ON m.id = p.media_asset_id AND m.tenant_id = p.tenant_id
            WHERE p.tenant_id = %s AND p.student_id = %s
            ORDER BY p.created_at DESC
            LIMIT 200
            """,
            (link["tenant_id"], link["student_id"]),
        )

    slug = link["tenant_slug"]
    items = [
        {
            "id": str(row["id"]),
            "mediaUrl": f"/v1/public/{slug}/media/{row['media_asset_id']}?token={raw_token}",
            "date": str(row["artwork_date"] or row["created_at"].date()),
            "note": row["description"] or "",
            "title": row["title"] or "",
        }
        for row in rows
    ]
    return jsonify({
        "ok": True,
        "studio": {
            "name": link["tenant_name"],
            "primaryColor": link["primary_color"],
            "secondaryColor": link["secondary_color"],
            "logoUrl": link["logo_url"],
        },
        "student": link["student_name"],
        "expiresAt": link["expires_at"].isoformat(),
        "items": items,
    })




@api_v1.route("/public/calendar/<token>.ics", methods=["GET"])
def public_calendar_feed(token: str):
    """The family's calendar feed.

    Unauthenticated by necessity: a calendar client subscribes with a URL and
    has no session to present. The token is 256 bits, matched by hash, and the
    tenant is read from the row it resolves to — never from anything the request
    supplied, which is what stops a token from one studio being pointed at
    another's data.
    """

    with connect() as conn:
        subscription = _calendar_subs.resolve(conn, token)
        if not subscription:
            # Deliberately the same answer as a revoked or malformed token: a
            # different one would let somebody probe for valid tokens.
            return _error("Calendar not found.", 404)
        document = _calendar_subs.build_document(conn, subscription)
        _calendar_subs.touch(conn, subscription["id"])
        conn.commit()

    response = Response(document.to_ics(), content_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = f'inline; filename="{document.filename}"'
    # Calendar clients poll on their own schedule; a short cache keeps a
    # re-subscribing client from hammering the feed without making a
    # reschedule wait noticeably longer than the client's own poll interval.
    response.headers["Cache-Control"] = "private, max-age=900"
    return response


