#!/usr/bin/env python3
"""Browser smoke for the two no-build consoles (Studio Admin, Super Admin).

These pages are the thinnest-tested surface in the repository: their JS is
plain inline/asset script, a single ReferenceError silently aborts the whole
function that raised it, and no pytest opens them in a browser. This script is
the net that must be green BEFORE anyone moves that script around — it drives
headless Chrome (the capture_manual_shots.py CDP framing) and asserts:

  1. the page loads with ZERO uncaught JS errors / unhandled rejections,
  2. the boot sequence actually ran (the login panel is un-hidden),
  3. the i18n runtime mounted (the language switch is in the DOM),
  4. a wrong-password login round-trips the api() helper and renders the
     page's own error message — proof the interactive layer is alive, not
     just parsed.

Usage:
    python backend/scripts/console_smoke.py --base http://localhost:8899
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_manual_shots import CHROME, Browser  # noqa: E402  (the CDP framing)

HOOK = """
window.__smokeErrors = [];
window.addEventListener('error', (e) => {
  window.__smokeErrors.push(String((e.error && e.error.stack) || e.message || e));
});
window.addEventListener('unhandledrejection', (e) => {
  window.__smokeErrors.push('unhandledrejection: ' + String((e.reason && e.reason.stack) || e.reason));
});
"""

PAGES = [
    ("studio-admin", "/lets-paint-showcase/studio-admin", "[data-admin-language-switch]"),
    ("super-admin", "/super-admin", "[data-admin-language-switch]"),
]


def evaluate(browser, expression):
    result = browser.call(
        "Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True
    )
    if "exceptionDetails" in result:
        raise RuntimeError(json.dumps(result["exceptionDetails"])[:400])
    return result.get("result", {}).get("value")


def smoke(browser, base, name, path, switch_selector):
    failures = []
    browser.call("Page.addScriptToEvaluateOnNewDocument", source=HOOK)
    browser.call("Page.navigate", url=f"{base}{path}")
    time.sleep(3.0)  # boot + deferred i18n + first fetch round-trip

    errors = evaluate(browser, "JSON.stringify(window.__smokeErrors || ['hook missing'])")
    errors = json.loads(errors)
    if errors:
        failures.append(f"uncaught JS errors: {errors}")

    if not evaluate(browser, "!!document.getElementById('loginForm')"):
        failures.append("login form missing — boot did not reach the login panel")
    if evaluate(browser, "(document.getElementById('loginPanel')||{}).hidden === true"):
        failures.append("login panel still hidden — the boot sequence aborted")
    if not evaluate(browser, f"!!document.querySelector('{switch_selector}')"):
        failures.append("language switch missing — i18n runtime did not mount")

    # A wrong login must round-trip api() and render the page's own error.
    evaluate(browser, """
      (() => {
        const email = document.getElementById('loginEmail');
        const password = document.getElementById('loginPassword');
        if (!email || !password) return false;
        email.value = 'smoke@invalid.test';
        password.value = 'wrong-password';
        document.getElementById('loginForm').dispatchEvent(
          new Event('submit', {bubbles: true, cancelable: true}));
        return true;
      })()
    """)
    deadline = time.time() + 8
    message = ""
    while time.time() < deadline:
        message = evaluate(
            browser,
            "(() => { const b = document.getElementById('loginError');"
            " return b && !b.hidden ? b.textContent.trim() : ''; })()",
        ) or ""
        if message:
            break
        time.sleep(0.4)
    if not message:
        failures.append("wrong-password login produced no visible error — api()/render path is dead")

    late = json.loads(evaluate(browser, "JSON.stringify(window.__smokeErrors || [])"))
    fresh = [e for e in late if e not in errors]
    if fresh:
        failures.append(f"interaction raised uncaught JS errors: {fresh}")

    status = "ok" if not failures else "FAIL"
    print(f"  {name:14s} {status}" + (f"  error message shown: {message!r}" if message else ""))
    for failure in failures:
        print(f"    ✗ {failure}")
    return not failures


def _free_port() -> int:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class _OwnServer:
    """Boot backend/server.py on a free port so the gate needs no operator.

    verify_local.sh has a database but no running application; starting one
    here is what lets this check be a gate step rather than a thing somebody
    remembers to run. Inherits the environment, so STUDIOSAAS_DATABASE_URL
    from the gate reaches the server unchanged.
    """

    def __init__(self) -> None:
        import subprocess
        import urllib.error
        import urllib.request

        self.port = _free_port()
        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ, PORT=str(self.port))
        self._log = open(  # noqa: SIM115 — closed in stop()
            Path(tempfile.gettempdir()) / f"console-smoke-server-{self.port}.log", "w"
        )
        self._process = subprocess.Popen(
            [sys.executable, str(root / "backend" / "server.py")],
            cwd=str(root), env=env, stdout=self._log, stderr=subprocess.STDOUT,
        )
        self.base = f"http://127.0.0.1:{self.port}"
        deadline = time.time() + 40
        while time.time() < deadline:
            if self._process.poll() is not None:
                raise SystemExit(
                    f"server exited with {self._process.returncode}; see {self._log.name}"
                )
            try:
                with urllib.request.urlopen(f"{self.base}/v1/health", timeout=2) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.4)
        self.stop()
        raise SystemExit(f"server did not become healthy; see {self._log.name}")

    def stop(self) -> None:
        import subprocess

        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._log.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=None,
        help="An already-running instance. Omit to boot one for the run.",
    )
    args = parser.parse_args()

    if not Path(CHROME).exists():
        print(f"console smoke: SKIPPED — no Chrome at {CHROME}")
        return 0

    server = None
    if args.base:
        base = args.base
    else:
        server = _OwnServer()
        base = server.base
        print(f"console smoke: booted its own instance on {base}")

    ok = True
    try:
        with tempfile.TemporaryDirectory(prefix="console-smoke-") as profile:
            browser = Browser(Path(profile))
            try:
                for name, path, switch in PAGES:
                    ok = smoke(browser, base, name, path, switch) and ok
            finally:
                browser.close()
    finally:
        if server is not None:
            server.stop()
    print("console smoke:", "all green" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
