"""Turn a video link a studio pasted into a provider and an id — or nothing.

Video is the one thing on the showcase board this product does NOT host. A
studio pastes a link, we store two short fields, and the visitor's browser
talks to the provider directly. Zero bytes stored, zero bandwidth served.

That makes the parse the security boundary, so it is written as a whitelist
and never as a rewrite:

  * only three providers are recognised, and everything else returns nothing;
  * only the ID is kept — never the studio's string, never a query fragment,
    never a path. The embed URL is built from OUR template and THEIR id;
  * the id itself must match a strict character class, so a value that reaches
    the page cannot carry a quote, an angle bracket or a slash.

The consequence worth stating: a hostile link cannot become an attribute in
the DOM, because the only thing that survives this module is `[A-Za-z0-9_-]`.

Standard library only — this is imported by the request path.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

# Embed origins, which are also what the CSP `frame-src` must allow. Kept here
# beside the parser so the two cannot drift: a provider added below without a
# matching CSP entry is a silently blank frame, which is exactly how the
# Cormorant Garamond link failed for a whole release.
EMBED_ORIGINS = {
    # The -nocookie host is not a privacy nicety, it is the difference between
    # a visitor being tracked by Google for reading a piano teacher's page and
    # not being tracked.
    "youtube": "https://www.youtube-nocookie.com",
    "vimeo": "https://player.vimeo.com",
    "bilibili": "https://player.bilibili.com",
}

EMBED_TEMPLATES = {
    "youtube": "https://www.youtube-nocookie.com/embed/{id}?rel=0",
    "vimeo": "https://player.vimeo.com/video/{id}",
    "bilibili": "https://player.bilibili.com/player.html?bvid={id}&autoplay=0",
}

PROVIDER_LABELS = {
    "youtube": {"zh": "YouTube", "en": "YouTube"},
    "vimeo": {"zh": "Vimeo", "en": "Vimeo"},
    "bilibili": {"zh": "哔哩哔哩", "en": "Bilibili"},
}

# Deliberately narrow. Every id this product will ever render matches it, and
# nothing that matches it can terminate an HTML attribute or a URL path.
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com",
                  "youtube-nocookie.com", "www.youtube-nocookie.com"}
_VIMEO_HOSTS = {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}
_BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com",
                   "player.bilibili.com", "b23.tv"}


def _first_segment(path: str, skip: tuple[str, ...] = ()) -> str:
    parts = [p for p in path.split("/") if p and p not in skip]
    return parts[0] if parts else ""


def parse_video_url(value: str) -> tuple[str, str]:
    """Return ``(provider, id)`` for a recognised link, or ``("", "")``.

    Returning empty rather than raising is deliberate: this runs on a stored
    record as well as on a submission, and a link that stops being parseable
    must cost the studio its video, never its page.
    """

    text = str(value or "").strip()
    if not text or len(text) > 400:
        return "", ""
    if "://" not in text:
        text = "https://" + text

    try:
        url = urlparse(text)
    except ValueError:
        return "", ""
    if url.scheme not in ("http", "https"):
        return "", ""

    host = (url.hostname or "").lower()
    query = parse_qs(url.query or "")

    if host in _YOUTUBE_HOSTS:
        # watch?v=ID, /embed/ID, /shorts/ID, /live/ID
        candidate = (query.get("v") or [""])[0] or _first_segment(
            url.path, skip=("embed", "shorts", "live", "v"))
        provider = "youtube"
    elif host == "youtu.be":
        candidate, provider = _first_segment(url.path), "youtube"
    elif host in _VIMEO_HOSTS:
        # vimeo.com/123456789 and player.vimeo.com/video/123456789. An unlisted
        # link carries a second segment (the private hash) — dropped on
        # purpose: we do not republish a link its owner kept unlisted.
        candidate, provider = _first_segment(url.path, skip=("video",)), "vimeo"
    elif host in _BILIBILI_HOSTS:
        candidate = (query.get("bvid") or [""])[0] or _first_segment(
            url.path, skip=("video",))
        provider = "bilibili"
    else:
        return "", ""

    if not _ID.match(candidate):
        return "", ""
    return provider, candidate


def embed_url(provider: str, video_id: str) -> str:
    """The frame source, built from our template and a validated id."""

    template = EMBED_TEMPLATES.get(provider)
    if not template or not _ID.match(str(video_id or "")):
        return ""
    return template.format(id=video_id)


def frame_src_directive() -> str:
    """The CSP value that lets the three providers render.

    `frame-src` is absent from a default policy, which means it falls back to
    `default-src` — and this product's `default-src` is `'self'`. So before
    this existed, every embed on every portal was blocked with no error
    anywhere, the same failure mode as the webfont that never loaded.
    """

    return " ".join(["frame-src", "'self'", *sorted(EMBED_ORIGINS.values())])
