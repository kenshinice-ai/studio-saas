/**
 * PWE Studio product home.
 *
 * Language is a URL now, not a runtime toggle: `/` serves English and `/zh/`
 * serves Chinese, each as a single-language document. The switch in the nav is
 * an ordinary link, so nothing here has to know which language it is on — and
 * the old localStorage preference is gone with it, because remembering a
 * language and then serving it under a canonical that claims another one is
 * the exact confusion this release removes.
 */
(() => {
  'use strict';

  const root = document.documentElement;
  const year = document.getElementById('year');
  const supportForm = document.getElementById('supportForm');
  const messagesButton = document.getElementById('openMessages');
  const nav = document.getElementById('siteNav');
  const menuButton = document.getElementById('menuButton');
  const navLinks = document.getElementById('navLinks');

  if (!year || !supportForm || !messagesButton || !nav || !menuButton || !navLinks) {
    throw new Error('PWE Studio product home is missing a required interactive control.');
  }

  year.textContent = String(new Date().getFullYear());

  // The customer-resources pages (FAQ, privacy, terms) still switch language
  // in the DOM and read this key. They are linked from the footer, so without
  // this a visitor reading /zh/ would land on an English privacy policy.
  try {
    window.localStorage.setItem('pwe-public-language', root.lang.startsWith('zh') ? 'zh' : 'en');
  } catch (error) {
    // Private browsing can refuse storage; the language of this page is in its
    // URL either way, so there is nothing to recover from here.
  }

  // ── reveal on scroll ──────────────────────────────────────────────────────
  // `.reveal` is only hidden once `js` is on the root, so a visitor whose
  // script failed — or a crawler that does not run one — still sees the whole
  // page. Anything already on screen is marked in the same task that adds the
  // class, so nothing is painted visible and then hidden back.
  const revealed = Array.from(document.querySelectorAll('.reveal'));
  root.classList.add('js');
  const onScreen = (el) => el.getBoundingClientRect().top < window.innerHeight;
  revealed.forEach((el) => { if (onScreen(el)) el.classList.add('in'); });

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('in');
        observer.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    revealed.forEach((el) => { if (!el.classList.contains('in')) observer.observe(el); });
  } else {
    revealed.forEach((el) => el.classList.add('in'));
  }

  // ── sticky nav ────────────────────────────────────────────────────────────
  const syncNav = () => nav.classList.toggle('solid', window.scrollY > 8);
  syncNav();
  window.addEventListener('scroll', syncNav, { passive: true });

  // ── mobile menu ───────────────────────────────────────────────────────────
  const setMenu = (open) => {
    document.body.classList.toggle('menu-open', open);
    menuButton.setAttribute('aria-expanded', String(open));
  };
  menuButton.addEventListener('click', () => {
    setMenu(menuButton.getAttribute('aria-expanded') !== 'true');
  });
  // Every link in the panel navigates within this page, so leaving the panel
  // open would cover the destination the visitor just chose.
  navLinks.addEventListener('click', (event) => {
    if (event.target instanceof Element && event.target.closest('a')) setMenu(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('menu-open')) {
      setMenu(false);
      menuButton.focus();
    }
  });

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
