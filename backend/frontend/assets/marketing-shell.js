/**
 * The marketing shell: the nav, the mobile panel, the sticky state, the
 * reveal-on-scroll and the footer year.
 *
 * Shared by the home page and the pricing page, for the same reason
 * marketing.css is: the header markup is one thing, so its behaviour has to
 * be one thing. product-home.js required the enquiry form to exist and threw
 * when it did not, which is correct for a page that has one and wrong for
 * every other page that reuses the header.
 *
 * Everything here is optional. A page without a `.reveal`, without a footer
 * year or without a menu button gets the parts it does have and no error.
 */
(() => {
  'use strict';

  const root = document.documentElement;

  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  // The customer-resources pages (FAQ, privacy, terms) still switch language
  // in the DOM and read this key. They are linked from the footer, so without
  // this a visitor reading a Chinese page would land on an English privacy
  // policy.
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
  const nav = document.getElementById('siteNav');
  if (nav) {
    const syncNav = () => nav.classList.toggle('solid', window.scrollY > 8);
    syncNav();
    window.addEventListener('scroll', syncNav, { passive: true });
  }

  // ── mobile menu ───────────────────────────────────────────────────────────
  const menuButton = document.getElementById('menuButton');
  const navLinks = document.getElementById('navLinks');
  if (menuButton && navLinks) {
    const setMenu = (open) => {
      document.body.classList.toggle('menu-open', open);
      menuButton.setAttribute('aria-expanded', String(open));
    };
    menuButton.addEventListener('click', () => {
      setMenu(menuButton.getAttribute('aria-expanded') !== 'true');
    });
    // A link in the panel navigates away from it, so leaving it open would
    // cover the destination the visitor just chose.
    navLinks.addEventListener('click', (event) => {
      if (event.target instanceof Element && event.target.closest('a')) setMenu(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && document.body.classList.contains('menu-open')) {
        setMenu(false);
        menuButton.focus();
      }
    });
  }
})();
