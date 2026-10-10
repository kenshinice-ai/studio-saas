"""PWE Assist on the product site: the window, the form, and what the pages say.

Three changes that have to arrive together, because each makes a sentence
somewhere else false if it arrives alone:

  * the assistant's window is offered on the product site's pages — and only
    those; a tenant's portal, the registration flow and every signed-in
    surface must never load it, because it knows nothing about any tenant;
  * the home page form sends to the enquiry service instead of opening the
    visitor's mail app — so the page can no longer say it stores nothing;
  * the privacy policy says what is kept, by whom and for how long.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOME = (PROJECT_ROOT / "product-home.html").read_text(encoding="utf-8")
FORM_JS = (PROJECT_ROOT / "backend/frontend/assets/product-home.js").read_text(encoding="utf-8")
PRIVACY = (PROJECT_ROOT / "customer-resources/Privacy_Policy.html").read_text(encoding="utf-8")
SUPPORT = (PROJECT_ROOT / "customer-resources/Support_Policy.html").read_text(encoding="utf-8")

PRODUCT_SITE = (
    ("/studio", "en"), ("/zh/studio/", "zh"),
    ("/pricing", "en"), ("/zh/pricing", "zh"),
    ("/manual/", "en"), ("/zh/manual/", "zh"),
    ("/customer-resources/FAQ.html", "en"), ("/zh/customer-resources/FAQ.html", "zh"),
    ("/customer-resources/Support_Policy.html", "en"),
    ("/customer-resources/Privacy_Policy.html", "en"),
    ("/zh/customer-resources/Privacy_Policy.html", "zh"),
    ("/customer-resources/Terms_of_Service.html", "en"),
    ("/customer-resources/Release_Notes.html", "en"),
)

WIDGET = "/v1/assist/widget.js"


def _js_code(source: str) -> str:
    """Script with comments removed, so an assertion cannot pass on prose."""

    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(line for line in source.splitlines() if not line.strip().startswith("//"))


@pytest.fixture()
def no_plan_query(monkeypatch):
    """The pages render without a database; the grid is not what is tested."""

    import server

    monkeypatch.setattr(server, "public_plan_rows", lambda: [])


# ── B: where the window is offered ──────────────────────────────────────────

@pytest.mark.parametrize("path,language", PRODUCT_SITE)
def test_every_product_site_page_offers_the_window(client, no_plan_query, path, language) -> None:
    body = client.get(path).get_data(as_text=True)
    assert body.count(WIDGET) == 1, path
    assert "'data-site','pwe-studio'" in body
    assert f"'data-lang','{language}'" in body, "the window must open in the page's language"
    # Open to every visitor: no opt-in condition stands in front of the loader.
    assert "pwe-assist:try" not in body
    # `data-lang` is these pages' authoring marker. It reaches the widget from
    # script, never as an attribute in the markup that is sent.
    assert "data-lang=" not in body
    assert "<!--ASSIST-WIDGET-->" not in body, "the placeholder was served instead of replaced"
    # It is loaded last, so a failure to load it cannot hold up the page.
    assert body.index(WIDGET) > body.index("</main>") if "</main>" in body else True


def test_the_window_is_open_and_the_gate_still_works() -> None:
    """The switch is "on" since v10.20.8: the gated window was used on
    production under v10.20.7 and Lee approved opening it (2026-10-10).

    The gate stays in the code. Turning the assistant off for visitors while
    keeping it reachable for a check is one word, not a revert — and "gate"
    opts in one tab with `?assist=1` and shows nobody else anything."""

    from studiosaas.services.public_site import ASSIST_WIDGET_MODE, render_assist_widget

    assert ASSIST_WIDGET_MODE == "on", (
        "the switch moved. If the assistant was pulled back on purpose, say so "
        "here and in the handoff; visitors lost the window the moment this changed"
    )
    gated = render_assist_widget("en", "gate")
    assert "assist=1" in gated and "sessionStorage.getItem('pwe-assist:try')!=='1')return" in gated
    assert "<script defer src=" not in gated, "the gate must not also load the script outright"

    opened = render_assist_widget("zh", "on")
    assert "s.src='/v1/assist/widget.js'" in opened
    assert "'data-site','pwe-studio'" in opened and "'data-lang','zh'" in opened
    assert "pwe-assist:try" not in opened and "data-lang=" not in opened
    assert render_assist_widget("en", "off") == ""
    with pytest.raises(ValueError):
        render_assist_widget("en", "maybe")


def test_no_tenant_or_signed_in_surface_loads_the_window() -> None:
    """The assistant knows the product site's words. On a tenant's portal it
    would answer a parent's question about their child's studio from PWE's
    marketing copy."""

    for relative in (
        "tenant-template/index.html", "tenant-template/register.html",
        "legacy-root/index.html", "legacy-root/register.html",
        "backend/frontend/studio-admin.html", "super-admin.html",
        "backend/frontend/setup-password.html",
    ):
        path = PROJECT_ROOT / relative
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        assert "ASSIST-WIDGET" not in source and WIDGET not in source, relative

    server = (PROJECT_ROOT / "backend/server.py").read_text(encoding="utf-8")
    # `(?<!\w)`: `render_assist_widget(language)` ends in the same characters.
    calls = re.findall(r"def (\w+)\([^)]*\):(?:(?!\ndef ).)*?(?<!\w)_assist_widget\(language\)", server, flags=re.S)
    assert sorted(calls) == sorted([
        "_serve_manual", "_serve_product_home", "_serve_pricing", "_serve_customer_resource_page",
    ]), calls


def test_the_edition_has_no_window(client, no_plan_query, monkeypatch) -> None:
    """A customer's own host has no `/v1/assist/`. A script tag there is a
    request that fails on every page view."""

    import server

    monkeypatch.setattr(server, "is_standalone", lambda: True)
    for path in ("/manual/", "/customer-resources/FAQ.html", "/zh/customer-resources/Privacy_Policy.html"):
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.get_data(as_text=True)
        assert WIDGET not in body and "ASSIST-WIDGET" not in body, path


def test_the_window_script_is_not_assist_knowledge(client, monkeypatch) -> None:
    import server
    from studiosaas.services.assist_knowledge import text_of

    monkeypatch.setattr(server, "public_plan_rows", lambda: [])
    home = client.get("/studio").get_data(as_text=True)
    assert WIDGET in home
    assert not any("assist/widget" in line or "pwe-assist" in line for line in text_of(home, "main"))


# ── C: the form sends ───────────────────────────────────────────────────────

def test_the_form_asks_for_what_a_reply_needs() -> None:
    form = HOME[HOME.index('<form class="form" id="supportForm"'):HOME.index("</form>")]
    for control, attributes in (
        ('id="supportName"', ('name="name"', "required", 'maxlength="100"', 'autocomplete="name"')),
        ('id="supportEmail"', ('name="email"', 'type="email"', "required", 'maxlength="254"')),
        ('id="supportStudio"', ('name="organisation"', 'maxlength="120"')),
        ('id="supportMessage"', ('name="brief"', "required", 'maxlength="4000"')),
    ):
        tag = re.search(r"<(?:input|textarea)[^>]*%s[^>]*>" % re.escape(control), form).group(0)
        for attribute in attributes:
            assert attribute in tag, (control, attribute)
    # The studio name is optional and says so; it must not be required.
    assert "required" not in re.search(r'<input[^>]*id="supportStudio"[^>]*>', form).group(0)
    assert "Studio name (optional)" in form and "工作室名称（选填）" in form


def test_every_control_names_its_error_message() -> None:
    """An error a screen reader does not announce with its field is an error
    the visitor has to go looking for."""

    form = HOME[HOME.index('<form class="form" id="supportForm"'):HOME.index("</form>")]
    for control in ("supportName", "supportEmail", "supportTopic", "supportStudio", "supportMessage"):
        assert f'aria-describedby="{control}Error"' in form, control
        assert f'<p class="field-error" id="{control}Error" hidden></p>' in form, control
    code = _js_code(FORM_JS)
    assert "setAttribute('aria-invalid', 'true')" in code and "first.focus()" in code


def test_the_trap_field_is_off_screen_not_removed() -> None:
    form = HOME[HOME.index('<form class="form" id="supportForm"'):HOME.index("</form>")]
    trap = form[form.index('<div class="form-trap"'):]
    trap = trap[:trap.index("</div>")]
    assert 'aria-hidden="true"' in trap
    assert 'name="website"' in trap and 'tabindex="-1"' in trap and 'autocomplete="off"' in trap
    css = (PROJECT_ROOT / "backend/frontend/assets/marketing.css").read_text(encoding="utf-8")
    rule = css[css.index(".form-trap {"):]
    rule = rule[:rule.index("}")]
    assert "display: none" not in rule and "left: -9999px" in rule


def test_the_form_posts_to_the_enquiry_service_at_this_origin() -> None:
    code = _js_code(FORM_JS)
    assert "const ENDPOINT = '/v1/assist/enquiries';" in code, "the address must be relative: same origin, no CORS"
    assert "const SITE = 'pwe-studio';" in code
    assert "source: 'form'" in code and "page: window.location.pathname" in code
    assert "'content-type': 'application/json'" in code
    for field in ("name:", "email:", "type:", "brief:", "website:"):
        assert field in code, field
    # Optional, so it is sent only when the visitor gave one.
    assert "if (organisation) payload.organisation = organisation;" in code


def test_each_answer_from_the_service_has_its_own_outcome() -> None:
    code = _js_code(FORM_JS)
    assert "response.status === 201 && data.ok" in code and "showDone()" in code
    assert "response.status === 429" in code and "showRateLimited()" in code
    assert "response.status === 400 && data.fields" in code
    # Everything else, and a network failure, is "this page cannot send".
    assert code.count("showFallback") >= 3 and ".catch(showFallback)" in code


def test_a_failure_never_clears_what_the_visitor_wrote() -> None:
    """The fallback opens the visitor's own mail or messages app with the same
    text. Nothing in any failure path may reset the form."""

    code = _js_code(FORM_JS)
    assert ".reset()" not in code
    assert ".value = ''" not in code and '.value = ""' not in code
    assert "mailto:${CONTACT_EMAIL}?" in code and "sms:${CONTACT_SMS}?" in code
    fallback = HOME[HOME.index('id="supportFallback"'):]
    fallback = fallback[:fallback.index("</form>")]
    assert 'id="openMail"' in fallback and 'id="openMessages"' in fallback
    assert re.search(r'<div class="form-fallback" id="supportFallback" hidden>', HOME)


def test_the_form_never_logs_what_was_written() -> None:
    code = _js_code(FORM_JS)
    assert "console." not in code


def test_the_success_message_is_the_agreed_sentence() -> None:
    """Lee's wording, 2026-10-05. The assistant's window shows the same one."""

    done = HOME[HOME.index('id="supportDone"'):]
    done = done[:done.index("</div>")]
    assert "We reply to the email you gave on the same business day. The next step is a 30-minute walkthrough." in done
    assert "我们会在工作日当天回复，下一步是一次 30 分钟演示。" in done
    assert re.search(r'<div class="form form-done" id="supportDone" role="status" tabindex="-1" hidden>', HOME)


def test_states_a_visitor_has_not_reached_are_not_assist_knowledge(client, monkeypatch) -> None:
    """"This page could not send your message" and "Received." are true only
    after something happened. Read as page copy they are false statements."""

    import server
    from studiosaas.services.assist_knowledge import text_of

    monkeypatch.setattr(server, "public_plan_rows", lambda: [])
    lines = "\n".join(text_of(client.get("/studio").get_data(as_text=True), "main"))
    for phrase in ("could not send your message", "Received.", "same business day", "Open Mail"):
        assert phrase not in lines, phrase


# ── C and D: what the pages now say ─────────────────────────────────────────

def test_the_form_says_what_sending_does_and_links_the_policy() -> None:
    form = HOME[HOME.index('<form class="form" id="supportForm"'):HOME.index("</form>")]
    assert "does not silently transmit or store" not in HOME
    assert "stores your message with PWE and emails it to our team" in form
    assert form.count('href="/customer-resources/Privacy_Policy.html#website-enquiries"') == 2
    assert PRIVACY.count('id="website-enquiries"') == 1


def test_the_chinese_form_links_the_chinese_policy(client, no_plan_query) -> None:
    chinese = client.get("/zh/studio/").get_data(as_text=True)
    assert 'href="/zh/customer-resources/Privacy_Policy.html#website-enquiries"' in chinese


def test_the_privacy_policy_covers_the_form_and_the_assistant(client, no_plan_query) -> None:
    for path, phrases in (
        ("/customer-resources/Privacy_Policy.html", (
            "10 · Our own website: enquiries and the AI assistant",
            "your name, your email address, the studio name if you gave one",
            "24 months after our last contact",
            "an AI model made by Anthropic",
            "which may take place outside Australia",
            "keeps it for no more than 30 days before deleting it",
            "or is required by law to keep",
            "The record of the conversation is kept by us, not by Anthropic",
            "the copy it holds for a short time is in the United States",
            "stay on our host in Melbourne",
            "deleted after 90 days",
            "it has no access to any studio’s records",
            "11 · Changes to this policy",
        )),
        ("/zh/customer-resources/Privacy_Policy.html", (
            "十 · 我们自己的网站：留言与 AI 助手",
            "最后一次联系后 24 个月",
            "由 Anthropic 公司的 AI 模型 Claude 生成",
            "以及法律要求它保留的除外",
            "对话在 90 天后删除",
            "十一 · 本政策的变更",
        )),
    ):
        body = client.get(path).get_data(as_text=True)
        for phrase in phrases:
            assert phrase in body, (path, phrase)


def test_the_policy_no_longer_says_nothing_goes_overseas() -> None:
    """Section 5 said "we do not transfer personal information overseas for our
    own purposes". With an assistant whose answers are generated outside
    Australia that is true of a studio's data and false of a visitor's."""

    assert "We do not transfer personal information overseas for our own purposes." not in PRIVACY
    assert "we do not send a studio’s personal information overseas for our own purposes." in PRIVACY
    assert "section 10 sets that out" in PRIVACY


# ── where the service runs ──────────────────────────────────────────────────
#
# Production moved from AWS in Sydney to Oracle Cloud in Melbourne on
# 2026-09-17. The internal documents were aligned that day. The four pages a
# customer reads — and two of them are in the Assist knowledge in full — went
# on saying Sydney for three weeks, privacy policy included.

HOSTING_PAGES = (
    "product-home.html",
    "customer-resources/FAQ.html",
    "customer-resources/Privacy_Policy.html",
    "customer-resources/Terms_of_Service.html",
)


@pytest.mark.parametrize("relative", HOSTING_PAGES)
def test_no_public_page_places_the_service_in_sydney(relative) -> None:
    source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
    for stale in ("ap-southeast-2", "Lightsail", "on the same instance", "同一实例"):
        assert stale not in source, (relative, stale)
    # Sydney and AWS may be named only as where the service USED to run.
    for line in source.splitlines():
        if re.search(r"Sydney|悉尼|AWS|Amazon Web Services", line):
            assert "17 September 2026" in line or "9 月 17 日" in line, (relative, line.strip()[:120])
    assert "Melbourne" in source and "墨尔本" in source, relative


def test_the_pages_agree_on_the_region_and_the_assist_knowledge_carries_it(client, monkeypatch) -> None:
    import server

    monkeypatch.setattr(server, "public_plan_rows", lambda: [])
    for relative in ("product-home.html", "customer-resources/FAQ.html", "customer-resources/Privacy_Policy.html"):
        assert "ap-melbourne-1" in (PROJECT_ROOT / relative).read_text(encoding="utf-8"), relative

    from studiosaas.services.assist_knowledge import text_of

    faq = "\n".join(text_of(client.get("/customer-resources/FAQ.html").get_data(as_text=True), "main"))
    assert "Oracle Cloud in the Melbourne region" in faq
    assert "Sydney region" not in faq and "same instance" not in faq


def test_the_backup_answer_states_its_own_limits() -> None:
    """A privacy page that lists only controls is a sales document. The three
    limits are the point of the answer, not its small print."""

    faq = (PROJECT_ROOT / "customer-resources/FAQ.html").read_text(encoding="utf-8")
    for phrase in (
        "encrypted on the host before it leaves",
        "Media is copied monthly, not nightly",
        "kept in Cloudflare’s Oceania region, which is wider than Australia",
        "no automated alert if a backup run fails",
        "媒体是每月备份，不是每晚",
        "存放在 Cloudflare 的大洋洲区域",
    ):
        assert phrase in faq, phrase
    privacy = PRIVACY
    assert "Apart from that encrypted backup copy, which may sit outside Australia within Oceania, we do not send a studio’s personal information overseas" in privacy
    # Oceania is a region, not a country. The page may say the copy is in
    # Oceania; it must not let that read as "in Australia".
    assert "we do not describe that encrypted copy as held in Australia" in privacy


def test_the_support_policy_describes_the_form_that_exists() -> None:
    assert "It opens your device's Mail or Messages application with prepared text; you review and send it." not in SUPPORT
    assert "does not claim automated delivery" not in SUPPORT, "delivery is automated now; the claim was true and is not"
    assert "It sends your message to our team and we reply by email." in SUPPORT
    assert "它会把留言发给我们的团队，我们以邮件回复。" in SUPPORT
    # The support policy states no response time: targets exist only on a
    # signed order form, and this paragraph must not smuggle one in.
    paragraph = SUPPORT[SUPPORT.index("<strong>Current contact path.</strong>"):]
    paragraph = paragraph[:paragraph.index("</p>")]
    assert "business day" not in paragraph and "hours" not in paragraph
