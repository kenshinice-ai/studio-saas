(() => {
  'use strict';

  const root = document.documentElement;
  const languageButton = document.getElementById('languageButton');
  const year = document.getElementById('year');
  const supportForm = document.getElementById('supportForm');
  const messagesButton = document.getElementById('openMessages');

  if (!languageButton || !year || !supportForm || !messagesButton) {
    throw new Error('PWE Studio product home is missing a required interactive control.');
  }

  const setLanguage = (language) => {
    root.lang = language;
    languageButton.textContent = language === 'en' ? '中文' : 'English';
    window.localStorage.setItem('pwe-public-language', language);
  };

  setLanguage(window.localStorage.getItem('pwe-public-language') === 'zh' ? 'zh' : 'en');
  languageButton.addEventListener('click', () => setLanguage(root.lang === 'en' ? 'zh' : 'en'));
  year.textContent = String(new Date().getFullYear());

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
