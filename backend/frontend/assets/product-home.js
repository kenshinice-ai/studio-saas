/**
 * The product home page's own behaviour: the enquiry form.
 *
 * The nav, the mobile panel, the sticky state, the reveal animation and the
 * footer year moved to marketing-shell.js when the pricing page began sharing
 * this header. This file used to throw if the enquiry form was absent, which
 * is right for the page that has one and wrong for every page that reuses the
 * header — so the shared half is now shared and this half still insists.
 */
(() => {
  'use strict';

  const supportForm = document.getElementById('supportForm');
  const messagesButton = document.getElementById('openMessages');
  if (!supportForm || !messagesButton) {
    throw new Error('PWE Studio product home is missing a required interactive control.');
  }

  // ── enquiry form ──────────────────────────────────────────────────────────
  const fieldValue = (id) => {
    const field = document.getElementById(id);
    if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement)) {
      throw new Error(`Support field '${id}' is unavailable.`);
    }
    return field.value.trim();
  };

  const buildMessage = () => {
    const topic = fieldValue('supportTopic');
    const studio = fieldValue('supportStudio');
    const message = fieldValue('supportMessage');
    const header = studio ? `Studio: ${studio}\n` : '';
    return {
      subject: `PWE Studio · ${topic}`,
      body: `${header}Topic: ${topic}\n\n${message}`,
    };
  };

  // ── where the enquiry goes ────────────────────────────────────────────────
  // Both handlers used to build `mailto:?subject=…` and `sms:?&body=…` — no
  // recipient in either. The page's one conversion action opened a blank
  // composer addressed to nobody, and the visitor was left to work out the
  // address themselves. `info@pwestudio.site` routes through Cloudflare Email
  // Routing; the number is the one already published beside these buttons.
  const CONTACT_EMAIL = 'info@pwestudio.site';
  const CONTACT_SMS = '+61488885850';

  // A mailto: URL is an address bar, not a payload, and an over-long one does
  // not fail — it does nothing at all, with no error anywhere. Measured on
  // this form, a Chinese message past roughly 142 characters produced no mail
  // window: percent-encoding costs nine URL characters per Chinese character,
  // so 142 of them is already ~1,300 bytes. The textarea's maxlength="1500"
  // cannot express that limit, because the limit is in encoded bytes and the
  // cost per character is between one and nine depending on the language.
  // So: build it, measure it, and trim the body to fit.
  const URL_BUDGET = 1200;
  const TRIMMED = {
    en: '\n\n[Trimmed so your mail app would open it — please paste the rest.]',
    zh: '\n\n[为了让邮件应用能打开，此处已截断——请把余下内容粘贴进来。]',
  };

  const trimToBudget = (body, budget) => {
    if (encodeURIComponent(body).length <= budget) return body;
    const note = TRIMMED[document.documentElement.lang.startsWith('zh') ? 'zh' : 'en'];
    const room = budget - encodeURIComponent(note).length;
    let text = body;
    // Percent-encoding is not a fixed ratio, so step back until it fits
    // rather than dividing by an assumed cost per character.
    while (text && encodeURIComponent(text).length > room) {
      text = text.slice(0, Math.max(0, text.length - Math.ceil(text.length / 8) || 1));
    }
    return text + note;
  };

  const enquiryHref = (scheme, payload) => {
    const head = scheme === 'mailto'
      ? `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(payload.subject)}&body=`
      : `sms:${CONTACT_SMS}?&body=`;
    const body = scheme === 'mailto'
      ? payload.body
      : `${payload.subject}\n${payload.body}`;
    return head + encodeURIComponent(trimToBudget(body, URL_BUDGET - head.length));
  };

  supportForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!supportForm.reportValidity()) return;
    window.location.href = enquiryHref('mailto', buildMessage());
  });

  messagesButton.addEventListener('click', () => {
    if (!supportForm.reportValidity()) return;
    window.location.href = enquiryHref('sms', buildMessage());
  });
})();
