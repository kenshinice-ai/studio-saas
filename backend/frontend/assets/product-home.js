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

  supportForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!supportForm.reportValidity()) return;
    const payload = buildMessage();
    window.location.href = `mailto:?subject=${encodeURIComponent(payload.subject)}&body=${encodeURIComponent(payload.body)}`;
  });

  messagesButton.addEventListener('click', () => {
    if (!supportForm.reportValidity()) return;
    const payload = buildMessage();
    window.location.href = `sms:?&body=${encodeURIComponent(`${payload.subject}\n${payload.body}`)}`;
  });
})();
