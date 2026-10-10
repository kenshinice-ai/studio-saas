/**
 * The product home page's own behaviour: the enquiry form.
 *
 * The nav, the mobile panel, the sticky state, the reveal animation and the
 * footer year moved to marketing-shell.js when the pricing page began sharing
 * this header. This file used to throw if the enquiry form was absent, which
 * is right for the page that has one and wrong for every page that reuses the
 * header — so the shared half is now shared and this half still insists.
 *
 * The form sends to the enquiry service at this same origin
 * (`POST /v1/assist/enquiries`, the `pwe-assist` Worker), which stores the
 * message and emails it to PWE. Until this release the form sent nothing: both
 * buttons opened the visitor's own mail or messages app. That path is still
 * here, as what the page falls back to when the service cannot be reached —
 * the one outcome that is never acceptable is losing what somebody wrote.
 */
(() => {
  'use strict';

  const form = document.getElementById('supportForm');
  const sendButton = document.getElementById('supportSend');
  const status = document.getElementById('supportStatus');
  const fallback = document.getElementById('supportFallback');
  const done = document.getElementById('supportDone');
  const mailButton = document.getElementById('openMail');
  const messagesButton = document.getElementById('openMessages');
  if (!form || !sendButton || !status || !fallback || !done || !mailButton || !messagesButton) {
    throw new Error('PWE Studio product home is missing a required interactive control.');
  }

  const LANG = document.documentElement.lang.startsWith('zh') ? 'zh' : 'en';
  const ENDPOINT = '/v1/assist/enquiries';
  const SITE = 'pwe-studio';

  // The service answers with codes, never sentences: the words a visitor
  // reads belong to the page, in the page's language.
  const COPY = {
    en: {
      sending: 'Sending…',
      rateLimited: 'Too many messages from this connection in the last minute. Wait a moment and send again — nothing you wrote has been cleared.',
      required: 'This is needed so that we can reply.',
      invalid: 'This does not look right. Check it and send again.',
      too_long: 'This is too long. Shorten it and send again.',
      email: 'Enter an email address we can reply to, such as name@example.com.',
    },
    zh: {
      sending: '正在发送…',
      rateLimited: '这个网络在过去一分钟里发送得太频繁。请稍等片刻再发——你写的内容没有被清空。',
      required: '需要这一项，我们才能回复你。',
      invalid: '这一项看起来不对，请检查后再发送。',
      too_long: '这一项太长了，请缩短后再发送。',
      email: '请填写一个能收到回复的邮箱，例如 name@example.com。',
    },
  }[LANG];

  // Service field name → the control that holds it.
  const FIELDS = {
    name: 'supportName',
    email: 'supportEmail',
    type: 'supportTopic',
    organisation: 'supportStudio',
    brief: 'supportMessage',
  };

  const control = (id) => {
    const field = document.getElementById(id);
    if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement)) {
      throw new Error(`Support field '${id}' is unavailable.`);
    }
    return field;
  };
  const fieldValue = (id) => control(id).value.trim();

  // ── field errors ──────────────────────────────────────────────────────────
  // Each control already names its error paragraph in `aria-describedby`, so
  // filling the paragraph is what makes a screen reader announce it with the
  // field. Colour is not the signal: the message is text, and the control is
  // marked `aria-invalid`.
  const setError = (id, message) => {
    const field = control(id);
    const note = document.getElementById(`${id}Error`);
    if (!note) return;
    note.textContent = message || '';
    note.hidden = !message;
    if (message) field.setAttribute('aria-invalid', 'true');
    else field.removeAttribute('aria-invalid');
  };

  const clearErrors = () => Object.values(FIELDS).forEach((id) => setError(id, ''));

  const showErrors = (errors) => {
    clearErrors();
    let first = null;
    Object.keys(FIELDS).forEach((name) => {
      const code = errors[name];
      if (!code) return;
      const id = FIELDS[name];
      setError(id, name === 'email' && code === 'invalid' ? COPY.email : (COPY[code] || COPY.invalid));
      first = first || control(id);
    });
    if (first) first.focus();
    return Boolean(first);
  };

  // The same checks the service makes, made first so that an obvious slip does
  // not cost a round trip. The service's answer is still the authority.
  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const localErrors = () => {
    const errors = {};
    if (!fieldValue(FIELDS.name)) errors.name = 'required';
    const email = fieldValue(FIELDS.email);
    if (!email) errors.email = 'required';
    else if (!EMAIL.test(email)) errors.email = 'invalid';
    if (!fieldValue(FIELDS.brief)) errors.brief = 'required';
    return errors;
  };

  Object.values(FIELDS).forEach((id) => {
    control(id).addEventListener('input', () => setError(id, ''));
  });

  // ── sending ───────────────────────────────────────────────────────────────
  let sending = false;
  // The page is served in one language, so the button holds one label.
  const sendLabel = sendButton.textContent.trim();

  const setSending = (on) => {
    sending = on;
    sendButton.disabled = on;
    sendButton.textContent = on ? COPY.sending : sendLabel;
  };

  const showDone = () => {
    form.hidden = true;
    done.hidden = false;
    done.focus();
  };

  const showFallback = () => {
    setSending(false);
    status.textContent = '';
    fallback.hidden = false;
    mailButton.focus();
  };

  const showRateLimited = () => {
    setSending(false);
    status.textContent = COPY.rateLimited;
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (sending) return;
    fallback.hidden = true;
    status.textContent = '';
    if (showErrors(localErrors())) return;

    setSending(true);
    const payload = {
      site: SITE,
      lang: LANG,
      source: 'form',
      page: window.location.pathname,
      name: fieldValue(FIELDS.name),
      email: fieldValue(FIELDS.email),
      type: fieldValue(FIELDS.type),
      brief: fieldValue(FIELDS.brief),
      // The trap: a person never sees this control, so for a person it is ''.
      website: control('supportWebsite').value,
    };
    const organisation = fieldValue(FIELDS.organisation);
    if (organisation) payload.organisation = organisation;

    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    }).then((response) => response.json().catch(() => ({})).then((data) => {
      if (response.status === 201 && data.ok) return showDone();
      if (response.status === 429) return showRateLimited();
      if (response.status === 400 && data.fields) {
        setSending(false);
        if (showErrors(data.fields)) return undefined;
      }
      // Anything else — a refused origin, an oversized body, a server error,
      // an address that does not exist — is "this page cannot send".
      return showFallback();
    })).catch(showFallback);
  });

  // ── the fallback: the visitor's own mail or messages app ─────────────────
  const buildMessage = () => {
    const topic = fieldValue(FIELDS.type);
    const studio = fieldValue(FIELDS.organisation);
    const name = fieldValue(FIELDS.name);
    const email = fieldValue(FIELDS.email);
    const header = [
      name ? `Name: ${name}` : '',
      email ? `Email: ${email}` : '',
      studio ? `Studio: ${studio}` : '',
      `Topic: ${topic}`,
    ].filter(Boolean).join('\n');
    return {
      subject: `PWE Studio · ${topic}`,
      body: `${header}\n\n${fieldValue(FIELDS.brief)}`,
    };
  };

  // Both handlers once built `mailto:?subject=…` and `sms:?&body=…` — no
  // recipient in either, so the composer opened addressed to nobody.
  // `info@pwestudio.site` routes through Cloudflare Email Routing; the number
  // is the one already published beside the form.
  const CONTACT_EMAIL = 'info@pwestudio.site';
  const CONTACT_SMS = '+61488885850';

  // A mailto: URL is an address bar, not a payload, and an over-long one does
  // not fail — it does nothing at all, with no error anywhere. Measured on
  // this form, a Chinese message past roughly 142 characters produced no mail
  // window: percent-encoding costs nine URL characters per Chinese character,
  // so 142 of them is already ~1,300 bytes. The textarea's maxlength cannot
  // express that limit, because the limit is in encoded bytes and the cost per
  // character is between one and nine depending on the language.
  // So: build it, measure it, and trim the body to fit.
  const URL_BUDGET = 1200;
  const TRIMMED = {
    en: '\n\n[Trimmed so your mail app would open it — please paste the rest.]',
    zh: '\n\n[为了让邮件应用能打开，此处已截断——请把余下内容粘贴进来。]',
  };

  const trimToBudget = (body, budget) => {
    if (encodeURIComponent(body).length <= budget) return body;
    const note = TRIMMED[LANG];
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

  mailButton.addEventListener('click', () => {
    window.location.href = enquiryHref('mailto', buildMessage());
  });

  messagesButton.addEventListener('click', () => {
    window.location.href = enquiryHref('sms', buildMessage());
  });
})();
