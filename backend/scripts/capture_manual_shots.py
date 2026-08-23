#!/usr/bin/env python3
"""Capture the user manual's screenshots from a local instance.

The images in `/manual/` go stale exactly the way its prose does, and
re-shooting by hand is the step that gets skipped — which is how
``docs/guides/`` stayed on a v8.1.0 baseline for nine releases. So the shot
list is executable: `docs/design/manual_shots.md` describes it for a reader,
SHOTS below is what actually runs, and a later release re-takes the set instead
of re-deriving it.

Source tenant is ``lets-paint-showcase``, whose records are synthetic by
construction (see ``reset_professional_demo.py``). No screenshot produced here
can contain a real student.

Driving Chrome
--------------
Chrome's ``--screenshot`` flag cannot carry a session, and half these screens
are behind a login. So Chrome is started with a debugging port and driven over
the DevTools Protocol: sign in with urllib, hand the session cookie to the
browser, navigate, click the tab, capture. CDP is JSON over a WebSocket, and
the ~60 lines of framing below are cheaper than a dependency this repository
would otherwise not have.

Usage
-----
    python scripts/capture_manual_shots.py --base http://localhost:8899
    python scripts/capture_manual_shots.py --only 03-roster    # one shot
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = APP_ROOT / "frontend" / "assets" / "manual"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SLUG = "lets-paint-showcase"

DESKTOP = (1440, 900)
MOBILE = (390, 844)
LANGUAGES = ("en", "zh")

# The CMS labels its tabs in the interface language, so the click target is a
# pair. Both come from cms-app.jsx; a rename there fails the capture.
TAB = {
    "roster":   {"en": "Class Schedule", "zh": "课程安排"},
    # The sidebar renders each item's long label (`l` in NAV_GROUPS), not the
    # short one it also carries: 学员档案, not 学员. Both translate to
    # "Students", so only the Chinese pass noticed when this drifted.
    "students": {"en": "Students", "zh": "学员档案"},
    "pending":  {"en": "Pending", "zh": "待处理"},
    "topup":    {"en": "Recharge & refunds", "zh": "充值与退款"},
    "logs":     {"en": "Activity Log", "zh": "操作日志"},
    "stats":    {"en": "Business Stats", "zh": "经营统计"},
}

# (name, role, path, viewport, tab, settle seconds, prepare JS or None)
# `tab` is the CMS tab's visible label. Clicking by label rather than by index
# means a renamed tab fails here loudly instead of quietly photographing the
# wrong screen.
SHOTS = [
    ("01-brand-workbench", "owner",   f"/{SLUG}/studio-admin", DESKTOP, None, 2.5, None),
    ("01-showcase-workbench", "owner", f"/{SLUG}/studio-admin", DESKTOP, None, 2.5, "showcase"),
    ("01-admissions-messages", "owner", f"/{SLUG}/studio-admin?view=messages", DESKTOP, None, 2.5, None),
    ("02-portal",          None,      f"/{SLUG}",              DESKTOP, None, 2.0, None),
    ("02-showcase-portal", None,      f"/{SLUG}",              DESKTOP, None, 2.0, "public_showcase"),
    ("02-showcase-page",   None,      f"/{SLUG}/showcase",     DESKTOP, None, 2.5, "showcase_page"),
    ("02-register",        None,      f"/{SLUG}/register",     DESKTOP, None, 1.5, None),
    ("02-pending",         "manager", f"/{SLUG}/cms",          DESKTOP, TAB["pending"], 2.0, None),
    ("03-courses",         "manager", f"/{SLUG}/cms?view=courses", DESKTOP, None, 2.0, None),
    ("03-roster",          "manager", f"/{SLUG}/cms",          DESKTOP, TAB["roster"], 2.0, "date"),
    ("03-roster-mobile",   "teacher", f"/{SLUG}/cms",          MOBILE,  TAB["roster"], 2.0, "date"),
    # v10.2.0 的四张：钱这一层与设置容器。演示租户从 v10.1.1 起就带着一学期
    # 的账，所以这几张拍出来是有数字的 —— 空列表的手册截图教不了任何东西。
    ("09-billing",         "owner",   f"/{SLUG}/cms?view=billing", DESKTOP, None, 2.5, None),
    ("09-finance",         "owner",   f"/{SLUG}/cms?view=finance", DESKTOP, None, 2.5, None),
    ("09-billing-identity","owner",   f"/{SLUG}/cms?view=settings&section=billing-identity", DESKTOP, None, 2.5, None),
    ("09-private-lessons", "owner",   f"/{SLUG}/cms?view=roster", DESKTOP, None, 2.5, None),
    ("04-timetable",       "owner",   f"/{SLUG}/studio-admin", DESKTOP, None, 2.5, "timetable"),
    ("04-booking",         None,      f"/{SLUG}/timetable",     MOBILE,  None, 2.0, "timetable_booking"),
    ("04-topup",           "manager", f"/{SLUG}/cms",          DESKTOP, TAB["topup"], 2.0, None),
    ("04-log",             "manager", f"/{SLUG}/cms",          DESKTOP, TAB["logs"], 2.0, None),
    ("05-portfolio",       "teacher", f"/{SLUG}/cms",          DESKTOP, TAB["students"], 2.0, "student"),
    ("05-works",           "teacher", f"/{SLUG}/cms?view=works", DESKTOP, None, 2.0, None),
    ("08-stats",           "manager", f"/{SLUG}/cms",          DESKTOP, TAB["stats"], 2.5, None),
    ("07-settings",        "owner",   f"/{SLUG}/cms?view=settings&section=account", DESKTOP, None, 2.0, None),
    ("06-student-area",    None,      f"/{SLUG}",              MOBILE,  None, 2.0, None),
]


def recent_class_date() -> str:
    """The most recent day the showcase actually taught.

    Two constraints meet on this line. An empty roster is the one screenshot a
    reader would take as "the feature does not work", so the date has to be a
    day that has classes. And check-in is refused outside `[today-90, today+1]`
    — so a *future* class day photographs the roster with a warning across the
    overview bar and every primary button greyed out, which teaches the reader
    something worse than nothing.

    Walking forward hit that second case on any Sunday, Monday, Wednesday or
    Friday: the capture landed two days out and the manual shipped a screen
    where nobody can be checked in. So walk backwards — today when today
    teaches, otherwise the last day that did, which is always inside the
    window and always has a live check-in button.
    """

    from datetime import date, timedelta

    # `class_schedules.weekday` is 1 = Monday … 7 = Sunday; Python's
    # `date.weekday()` is 0 = Monday. The seeded classes are 2, 4 and 6 —
    # Tuesday, Thursday and Saturday.
    scheduled = {2, 4, 6}
    today = date.today()
    for offset in range(8):
        candidate = today - timedelta(days=offset)
        if candidate.weekday() + 1 in scheduled:
            return candidate.isoformat()
    return today.isoformat()

ROLE_EMAIL = {
    "owner": f"owner.showcase@pwe-studio.invalid",
    "manager": f"manager.showcase@pwe-studio.invalid",
    "teacher": f"teacher.showcase@pwe-studio.invalid",
    "front_desk": f"frontdesk.showcase@pwe-studio.invalid",
}


# ── credentials ──────────────────────────────────────────────────────────────

def _credentials_path() -> Path:
    configured = os.environ.get("STUDIOSAAS_DEMO_CREDENTIALS_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".studiosaas" / "showcase-credentials.txt"


def read_demo_password() -> str:
    """The password `reset_professional_demo.py` wrote to its 0600 file.

    Read rather than accepted as an argument so it never reaches a process
    list, a shell history or this script's output.
    """

    path = _credentials_path()
    if not path.is_file():
        raise SystemExit(
            f"No showcase credentials at {path}. Run reset_professional_demo.py first."
        )
    match = re.search(r"password:\s*(\S+)", path.read_text(encoding="utf-8"), re.I)
    if not match:
        raise SystemExit(f"{path} does not contain a password line.")
    return match.group(1)


def login(base: str, email: str, password: str) -> str:
    """Sign in over HTTP and return the session cookie value."""

    request = urllib.request.Request(
        f"{base}/v1/auth/login",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        cookies = response.headers.get_all("Set-Cookie") or []
    for cookie in cookies:
        if cookie.startswith("session="):
            return cookie.split("=", 1)[1].split(";", 1)[0]
    raise SystemExit(f"login for {email} returned no session cookie")


# ── the smallest WebSocket client that can speak CDP ─────────────────────────

class _Socket:
    """Text-frame WebSocket over a plain socket. Client frames are masked."""

    def __init__(self, url: str) -> None:
        host_port, _, path = url[len("ws://"):].partition("/")
        host, _, port = host_port.partition(":")
        self._sock = socket.create_connection((host, int(port or 80)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall(
            f"GET /{path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n".encode()
        )
        self._buffer = b""
        while b"\r\n\r\n" not in self._buffer:
            self._buffer += self._sock.recv(4096)
        head, _, rest = self._buffer.partition(b"\r\n\r\n")
        if b"101" not in head.split(b"\r\n")[0]:
            raise RuntimeError(f"websocket upgrade refused: {head[:80]!r}")
        self._buffer = rest

    def _read(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise RuntimeError("websocket closed")
            self._buffer += chunk
        head, self._buffer = self._buffer[:count], self._buffer[count:]
        return head

    def send(self, text: str) -> None:
        payload = text.encode()
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 1 << 16:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        mask = os.urandom(4)
        header += mask
        self._sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self) -> str:
        while True:
            first, second = self._read(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(length)
            if opcode == 0x1:
                return payload.decode()
            if opcode == 0x8:
                raise RuntimeError("websocket closed by peer")
            # ping/pong and continuation frames are not used by CDP here


class Browser:
    """Just enough DevTools Protocol for this job."""

    def __init__(self, profile: Path) -> None:
        self._port = _free_port()
        self._process = subprocess.Popen(
            [CHROME, "--headless=new", f"--remote-debugging-port={self._port}",
             f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
             "--hide-scrollbars", "--force-color-profile=srgb", "--disable-gpu",
             "--force-prefers-color-scheme=light", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._socket = _Socket(self._wait_for_target())
        self._id = 0
        # `Page.addScriptToEvaluateOnNewDocument` silently does nothing until
        # the domain is enabled — which is how the first run captured every
        # screen in Chinese and reported success.
        self.call("Page.enable")
        self.call("Runtime.enable")
        self._seed: str | None = None

    def _wait_for_target(self) -> str:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self._port}/json", timeout=2) as r:
                    targets = json.load(r)
                for target in targets:
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return target["webSocketDebuggerUrl"]
            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                pass
            time.sleep(0.3)
        raise SystemExit("Chrome did not expose a debugging target")

    def call(self, method: str, **params):
        self._id += 1
        self._socket.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            message = json.loads(self._socket.recv())
            if message.get("id") != self._id:
                continue                       # an event, not our reply
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result", {})

    def close(self) -> None:
        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


# ── capture ──────────────────────────────────────────────────────────────────

# The navigation tabs carry a count badge, so their text is "Pending4" rather
# than "Pending". Matching label-plus-digits, and taking the smallest matching
# element, avoids both the near-miss and clicking a container that happens to
# contain the word.
CLICK_TAB = """
(() => {
  const wanted = %s;
  const pattern = new RegExp('^' + wanted.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '\\\\s*\\\\d*$');
  const hits = [...document.querySelectorAll('button, a, [role="tab"], li, div, span')]
    .filter(el => pattern.test((el.textContent || '').trim()));
  if (!hits.length) return 'MISSING';
  hits.sort((a, b) => a.getElementsByTagName('*').length - b.getElementsByTagName('*').length);
  (hits[0].closest('button, a, [role="tab"], li') || hits[0]).click();
  return 'ok';
})()
"""

# React owns these inputs, so assigning `.value` is discarded on the next
# render. The native setter plus a bubbling event is what React's onChange
# actually listens for.
SET_DATE = """
(() => {
  const input = document.querySelector('input[type="date"]');
  if (!input) return 'MISSING';
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value').set;
  setter.call(input, %s);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  return 'ok';
})()
"""

# Open the first student record so the portfolio block is on screen.
# The student record is a dialog with its own tabs, so this shot is two clicks:
# open the first card's Details, then move to the Portfolio tab the manual's
# caption and alt text both name ("停在作品集区块"). The previous matcher looked
# for "(12课" in any element — no card has read that way since the list became
# cards — and the caller discarded its result, so the figure quietly showed the
# student list instead. Both halves are fixed: the labels are the rendered ones,
# and a miss is fatal.
STUDENT_DETAILS = {"en": "Details", "zh": "详情"}
STUDENT_PORTFOLIO = {"en": "Portfolio", "zh": "作品集"}

CLICK_EXACT_BUTTON = """
(() => {
  const wanted = %s;
  const hits = [...document.querySelectorAll('button')]
    .filter(el => (el.textContent || '').trim() === wanted);
  if (!hits.length) return 'MISSING';
  hits[0].click();
  return 'ok';
})()
"""

# Open the actual Selected work tab and add one unsaved, link-only example so
# the manual shows the control the prose describes. The synthetic demo tenant
# remains unchanged: the card exists only in this browser tab and is never
# saved through the Owner form.
SHOWCASE_EDITOR = """
(() => {
  const tab = document.getElementById('tab-btn-showcase');
  const add = document.getElementById('showcaseAddItem');
  if (!tab || !add) return 'MISSING';
  tab.click();
  add.click();
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value').set;
  const video = document.getElementById('showcaseVideo0');
  if (!video || !setter) return 'MISSING';
  setter.call(video, 'https://youtu.be/your-video-id');
  video.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()
"""

SHOWCASE_PAGE = """
(() => {
  // v9.8.10 gave Selected Work its own page. Unlike PUBLIC_SHOWCASE this
  // rewrites nothing: since v9.9.2 the seeder owns the portal copy too, so
  // what is on screen is already the synthetic text we want photographed.
  const grid = document.getElementById('showcaseGrid');
  return grid && grid.children.length ? 'ok' : 'MISSING';
})()
"""


PUBLIC_SHOWCASE = """
(() => {
  const section = document.getElementById('showcase');
  const grid = document.getElementById('showcaseGrid');
  if (!section || !grid || !grid.children.length) return 'MISSING';
  const zh = document.documentElement.lang.startsWith('zh');
  document.getElementById('showcaseTitle').textContent = zh ? '工作室精选作品' : 'A curated selection from the studio';
  document.getElementById('showcaseLead').textContent = zh ? '一组由工作室亲自挑选的作品。' : 'A short selection, chosen by the studio.';
  [...grid.querySelectorAll('.sc-cap p')].forEach((caption, index) => {
    const en = ['Colour, material and light.', 'A study in colour and distance.', 'A focused observation.'][index] || 'A work selected by the studio.';
    const zhText = ['色彩、材质与光线练习。', '色彩与空间研究。', '专注观察的一次练习。'][index] || '由工作室精选的作品。';
    caption.textContent = zh ? zhText : en;
  });
  document.documentElement.style.scrollBehavior = 'auto';
  document.body.style.scrollBehavior = 'auto';
  const top = section.getBoundingClientRect().top + window.scrollY - 90;
  window.scrollTo(0, Math.max(0, top));
  return 'ok';
})()
"""

# Open the actual Public timetable panel and turn on both switches for the
# screenshot. The changes stay in this browser tab and are never saved.
TIMETABLE_EDITOR = """
(() => {
  const tab = document.getElementById('tab-btn-timetable');
  const page = document.getElementById('settingShowTimetable');
  const booking = document.getElementById('settingShowTimetableBooking');
  const weeks = document.getElementById('settingTimetableWeeks');
  if (!tab || !page || !booking || !weeks) return 'MISSING';
  tab.click();
  if (!page.checked) page.click();
  if (!booking.checked) booking.click();
  weeks.value = '2';
  weeks.dispatchEvent(new Event('change', { bubbles: true }));
  return 'ok';
})()
"""

# The demo tenant is deliberately seeded with no public timetable: it keeps
# the capture suite from publishing a customer-facing surface by accident.
# For the public screenshot, intercept only the timetable JSON in this browser
# tab and feed the real page a small, clearly synthetic schedule. No database
# write and no production API contract change is involved.
# The public timetable used to be photographed through a hand-written fixture
# that stubbed `/v1/public/<slug>/timetable`, because before v9.9.2 the showcase
# tenant had no timetable worth showing. The seeder now owns that half of the
# tenant, so the fixture had become a second source of truth — and it drifted:
# at v9.9.5 it rendered no booking buttons at all and failed this capture. The
# shot photographs the real seeded timetable now, like every other shot here.

ROSTER_UI_CONTRACT = """
(() => {
  const planner = document.querySelector('.cms-roster-planner');
  const dateNav = planner?.querySelector('.cms-roster-date-nav');
  const week = planner?.querySelector('.cms-roster-week');
  const summary = planner?.querySelector('.cms-roster-summary');
  const slots = planner?.querySelector('.cms-roster-slot-panel');
  const list = document.querySelector('.cms-roster-list');
  const add = document.querySelector('.cms-roster-add');
  const row = document.querySelector('.cms-roster-row');
  const info = row?.querySelector('.cms-roster-info');
  const actions = row?.querySelector('.cms-roster-actions');
  const more = row?.querySelector('.cms-roster-more');
  if (more) more.open = true;
  const menu = more?.querySelector('.cms-roster-menu');
  const context = menu?.querySelector('.cms-roster-menu__context');
  const positions = [dateNav, week, summary, slots, list, add]
    .map(el => el?.getBoundingClientRect().top);
  const desktop = innerWidth >= 760;
  const result = {
    named: [...document.querySelectorAll('h2')].some(el => /课程安排|Class Schedule/.test(el.textContent || '')),
    ordered: positions.every(Number.isFinite) && positions.every((top, i) => i === 0 || top > positions[i - 1]),
    // v10.13: the roster-editing block sits below the list it edits. Keeping it
    // out of the planner card is the whole reorder, so assert it directly and
    // not only through the ordering above.
    addOutsidePlanner: !!add && !!planner && !planner.contains(add),
    // The point of the reorder: on both captured viewports the first student
    // has to be visible without scrolling. Measured, not assumed.
    firstRowInFold: !!row && row.getBoundingClientRect().top < innerHeight,
    noOverflow: document.documentElement.scrollWidth <= innerWidth + 1,
    rowLayout: !!row && !!info && !!actions && (desktop
      ? Math.abs(info.getBoundingClientRect().top - actions.getBoundingClientRect().top) < 10
      : actions.getBoundingClientRect().top >= info.getBoundingClientRect().bottom),
    menuContext: !!menu && !!context && context.textContent.trim().length > 0,
  };
  if (more) more.open = false;
  return result;
})()
"""


# Staff screens remember their language in localStorage; the visitor-facing
# pages take it from `?lang=`. Seeding the key before the document exists is
# the only way to catch the app's own first read of it.
SEED_LANGUAGE = """
try {
  localStorage.setItem('studiosaas_admin_language', %s);
  localStorage.setItem('pwe_lang_lets-paint-showcase', %s);
} catch (e) {}
"""


def capture(browser: Browser, base: str, shot, session: str | None, language: str) -> bytes:
    """One screenshot, in one interface language.

    Every staff screen is captured twice. A Chinese screenshot in the English
    manual would be worse than no screenshot: the reader cannot tell whether
    they are looking at a different screen or a different install.
    """

    name, _role, path, (width, height), tab, settle, prepare = shot
    browser.call("Emulation.setDeviceMetricsOverride",
                 width=width, height=height, deviceScaleFactor=2,
                 mobile=(width < 500))
    if session:
        browser.call("Network.enable")
        browser.call("Network.setCookie", name="session", value=session,
                     domain="localhost", path="/")
    # Replace rather than add: these accumulate per session, and a stale seed
    # from the previous language would still be running.
    if browser._seed:
        browser.call("Page.removeScriptToEvaluateOnNewDocument", identifier=browser._seed)
    seed = SEED_LANGUAGE % (json.dumps(language), json.dumps(language))
    browser._seed = browser.call(
        "Page.addScriptToEvaluateOnNewDocument", source=seed)["identifier"]
    url = f"{base}{path}" + ("" if session else f"?lang={language}")
    browser.call("Page.navigate", url=url)
    time.sleep(settle)
    if tab:
        label = tab[language]
        result = browser.call("Runtime.evaluate",
                              expression=CLICK_TAB % json.dumps(label),
                              returnByValue=True)
        if result.get("result", {}).get("value") == "MISSING":
            raise SystemExit(
                f"{name}: no control labelled {label!r}. The tab was renamed — "
                "update SHOTS and docs/design/manual_shots.md together."
            )
        time.sleep(settle)
    if prepare == "date":
        result = browser.call("Runtime.evaluate", returnByValue=True,
                              expression=SET_DATE % json.dumps(recent_class_date()))
        if result.get("result", {}).get("value") == "MISSING":
            raise SystemExit(f"{name}: no date input on the roster screen")
        time.sleep(1.5)
    elif prepare == "student":
        for labels, missing in ((STUDENT_DETAILS, "no student card carries"),
                                (STUDENT_PORTFOLIO, "the open record has no tab")):
            label = labels[language]
            result = browser.call("Runtime.evaluate", returnByValue=True,
                                  expression=CLICK_EXACT_BUTTON % json.dumps(label))
            if result.get("result", {}).get("value") == "MISSING":
                raise SystemExit(
                    f"{name}: {missing} a control labelled {label!r}. The record "
                    "was rebuilt — update the label pairs here and "
                    "docs/design/manual_shots.md together.")
            time.sleep(1.5)
    elif prepare == "showcase":
        result = browser.call("Runtime.evaluate", returnByValue=True,
                              expression=SHOWCASE_EDITOR)
        if result.get("result", {}).get("value") == "MISSING":
            raise SystemExit(f"{name}: Selected work editor is missing its video field")
        time.sleep(1.0)
    elif prepare == "timetable":
        result = browser.call("Runtime.evaluate", returnByValue=True,
                              expression=TIMETABLE_EDITOR)
        if result.get("result", {}).get("value") == "MISSING":
            raise SystemExit(f"{name}: Public timetable settings are missing")
        time.sleep(1.0)
    elif prepare == "timetable_booking":
        for _attempt in range(8):
            result = browser.call(
                "Runtime.evaluate", returnByValue=True,
                expression="(() => { const button = document.querySelector('#days .book-btn'); if (!button) return 'WAIT'; button.click(); return 'ok'; })()",
            )
            if result.get("result", {}).get("value") == "ok":
                break
            time.sleep(0.75)
        else:
            raise SystemExit(f"{name}: public timetable did not render a booking button")
        time.sleep(0.75)
    elif prepare == "public_showcase":
        for _attempt in range(5):
            result = browser.call("Runtime.evaluate", returnByValue=True,
                                  expression=PUBLIC_SHOWCASE)
            if result.get("result", {}).get("value") == "ok":
                break
            time.sleep(1.0)
        else:
            raise SystemExit(f"{name}: public showcase did not load synthetic works")
    elif prepare == "showcase_page":
        for _attempt in range(6):
            result = browser.call("Runtime.evaluate", returnByValue=True,
                                  expression=SHOWCASE_PAGE)
            if result.get("result", {}).get("value") == "ok":
                break
            time.sleep(1.0)
        else:
            raise SystemExit(f"{name}: the Selected Work page rendered no works")
    if name.startswith("03-roster"):
        contract = browser.call(
            "Runtime.evaluate", returnByValue=True, expression=ROSTER_UI_CONTRACT
        ).get("result", {}).get("value") or {}
        failed = sorted(key for key, value in contract.items() if not value)
        if failed:
            raise SystemExit(f"{name}: roster UI contract failed: {', '.join(failed)}")
    # Wait for motion to finish before framing anything. The v10.x CMS slides
    # its settings page in, and a fixed settle raced that transition once in
    # production: 09-billing-identity shipped with the panel halfway across the
    # viewport and the search tooltip torn off mid-render. Asking the page
    # whether anything is still animating is cheap and cannot be outrun by a
    # slow first paint the way a sleep can.
    for _attempt in range(20):
        running = browser.call(
            "Runtime.evaluate", returnByValue=True,
            expression="document.getAnimations().filter(a => a.playState === 'running' && a.effect && a.effect.getTiming().iterations !== Infinity).length",
        ).get("result", {}).get("value")
        if running == 0:
            break
        time.sleep(0.5)
    else:
        raise SystemExit(f"{name}: the page is still animating after 10 seconds")
    # Give lazy images a beat; a half-loaded hero is the one artefact a reader
    # would read as a product fault rather than a capture fault.
    browser.call("Runtime.evaluate", expression="window.scrollTo(0, 0)")
    if prepare == "showcase":
        browser.call(
            "Runtime.evaluate",
            expression="document.getElementById('showcaseItemsEditor')?.scrollIntoView({block:'start'})",
        )
    elif prepare == "public_showcase":
        browser.call(
            "Runtime.evaluate",
            expression="(() => { const section = document.getElementById('showcase'); if (!section) return; document.documentElement.style.scrollBehavior = 'auto'; document.body.style.scrollBehavior = 'auto'; const top = section.getBoundingClientRect().top + window.scrollY - 90; window.scrollTo(0, Math.max(0, top)); })()",
        )
    elif prepare == "timetable":
        browser.call(
            "Runtime.evaluate",
            expression="(() => { const panel = document.getElementById('tab-timetable'); if (!panel) return; const top = panel.getBoundingClientRect().top + window.scrollY - 84; window.scrollTo(0, Math.max(0, top)); })()",
        )
    elif prepare == "timetable_booking":
        browser.call("Runtime.evaluate", expression="window.scrollTo(0, 0)")
    time.sleep(1.0)
    return base64.b64decode(browser.call("Page.captureScreenshot", format="png")["data"])


def to_webp(png: bytes, destination: Path, max_width: int = 1600) -> tuple[int, int, int]:
    from PIL import Image
    import io

    image = Image.open(io.BytesIO(png)).convert("RGB")
    if image.width > max_width:
        image = image.resize(
            (max_width, round(image.height * max_width / image.width)), Image.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "WEBP", quality=82, method=6)
    return image.width, image.height, destination.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8899")
    parser.add_argument("--only", help="capture a single shot by name")
    args = parser.parse_args()

    if not Path(CHROME).exists():
        raise SystemExit(f"Chrome not found at {CHROME}")

    shots = [s for s in SHOTS if not args.only or s[0] == args.only]
    if not shots:
        raise SystemExit(f"no shot named {args.only!r}")

    password = read_demo_password()
    sessions: dict[str, str] = {}
    for _, role, *_ in shots:
        if role and role not in sessions:
            sessions[role] = login(args.base, ROLE_EMAIL[role], password)
            print(f"  signed in as {role}")

    profile = Path(tempfile.mkdtemp(prefix="manual-shots-"))
    browser = Browser(profile)
    total = 0
    try:
        for shot in shots:
            name, role, *_ = shot
            for language in LANGUAGES:
                png = capture(browser, args.base, shot,
                              sessions.get(role) if role else None, language)
                width, height, size = to_webp(png, OUTPUT_DIR / f"{name}.{language}.webp")
                total += size
                print(f"  {name}.{language:<8} {width}x{height}  {size / 1024:6.1f} KB")
    finally:
        browser.close()
        shutil.rmtree(profile, ignore_errors=True)

    print(f"\n{len(shots) * len(LANGUAGES)} images, {total / 1024 / 1024:.2f} MB total → {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
