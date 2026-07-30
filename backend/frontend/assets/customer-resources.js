/* Language toggle for the served pages under /customer-resources/.
 *
 * product-home.js cannot be reused here: it throws when the support form is
 * absent, because on the gateway a missing form is a real defect. These pages
 * only need the language switch, so they get their own script that shares the
 * `pwe-public-language` key — a visitor who chose 中文 on the gateway keeps it
 * when they open the FAQ, the privacy policy or the terms.
 */
(() => {
  'use strict';

  const root = document.documentElement;
  const button = document.getElementById('languageButton');
  const year = document.getElementById('year');

  const readStoredLanguage = () => {
    try {
      return window.localStorage.getItem('pwe-public-language');
    } catch (_) {
      return null;
    }
  };

  const setLanguage = (language) => {
    root.lang = language;
    if (button) {
      button.textContent = language === 'en' ? '中文' : 'English';
      button.setAttribute('aria-label', language === 'en' ? 'Switch to Chinese' : '切换到英文');
    }
    try {
      window.localStorage.setItem('pwe-public-language', language);
    } catch (_) {
      /* Private browsing: the toggle still works for this page view. */
    }
  };

  setLanguage(readStoredLanguage() === 'zh' ? 'zh' : 'en');

  if (button) {
    button.addEventListener('click', () => setLanguage(root.lang === 'en' ? 'zh' : 'en'));
  }
  if (year) {
    year.textContent = String(new Date().getFullYear());
  }
})();
