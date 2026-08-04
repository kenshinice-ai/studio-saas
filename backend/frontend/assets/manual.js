/**
 * PWE Studio user manual.
 *
 * Four behaviours, all of which degrade to a plain document without them:
 * the contents highlight the section you are in, a filter box hides sections
 * that do not match, the contents collapse on a phone, and a button opens the
 * print dialogue. Nothing here is required to read the page — the manual is a
 * single HTML document that works with scripting off, which is also why the
 * print stylesheet un-hides anything the filter had hidden.
 *
 * Language is a URL (`/manual/` and `/zh/manual/`), so there is no toggle.
 */
(() => {
  'use strict';

  const toc = document.getElementById('toc');
  const search = document.getElementById('manualSearch');
  const printButton = document.getElementById('printButton');
  const tocButton = document.getElementById('tocButton');
  const sections = Array.from(document.querySelectorAll('article section[id]'));

  if (!toc || !search || !printButton || !tocButton || !sections.length) {
    throw new Error('PWE Studio manual is missing a required control.');
  }

  const links = new Map(
    Array.from(toc.querySelectorAll('a[href^="#"]'))
      .map((link) => [link.getAttribute('href').slice(1), link]),
  );

  // ── which section am I in ──────────────────────────────────────────────
  const highlight = (id) => {
    links.forEach((link, key) => link.classList.toggle('on', key === id));
  };

  if ('IntersectionObserver' in window) {
    // Top-biased margin: a heading counts as "current" once it reaches the
    // upper third, which is where a reader's eye actually is — keying off the
    // viewport centre makes the contents lag a full section behind.
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting);
      if (visible.length) highlight(visible[0].target.id);
    }, { rootMargin: '-72px 0px -66% 0px', threshold: 0 });
    sections.forEach((section) => observer.observe(section));
  }

  // ── filter ─────────────────────────────────────────────────────────────
  const empty = document.getElementById('noHits');
  const filter = (raw) => {
    const query = raw.trim().toLowerCase();
    document.body.classList.toggle('searching', Boolean(query));
    let hits = 0;
    sections.forEach((section) => {
      const match = !query || section.textContent.toLowerCase().includes(query);
      section.hidden = !match;
      const link = links.get(section.id);
      if (link) link.parentElement.hidden = !match;
      if (match) hits += 1;
    });
    if (empty) empty.classList.toggle('on', query && hits === 0);
  };

  search.addEventListener('input', () => filter(search.value));
  search.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { search.value = ''; filter(''); }
  });

  // ── contents on a phone ────────────────────────────────────────────────
  const setToc = (open) => {
    document.body.classList.toggle('toc-open', open);
    tocButton.setAttribute('aria-expanded', String(open));
  };
  tocButton.addEventListener('click', () => {
    setToc(tocButton.getAttribute('aria-expanded') !== 'true');
  });
  // Every entry scrolls this same page, so an open panel would cover the
  // destination the reader just picked.
  toc.addEventListener('click', (event) => {
    if (event.target instanceof Element && event.target.closest('a')) setToc(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('toc-open')) {
      setToc(false);
      tocButton.focus();
    }
  });

  // ── print ──────────────────────────────────────────────────────────────
  printButton.addEventListener('click', () => {
    // The printed footer names the day it was printed. CSS cannot produce a
    // date, and stamping it at page load would put a stale one on a tab left
    // open overnight.
    const today = new Date().toLocaleDateString(
      document.documentElement.lang.startsWith('zh') ? 'zh-CN' : 'en-AU',
      { year: 'numeric', month: 'long', day: 'numeric' },
    );
    document.querySelectorAll('.printed-on').forEach((slot) => { slot.textContent = today; });
    // A filtered page would print as a manual with sections missing. The
    // print stylesheet also un-hides them, but clearing the box is what keeps
    // the on-screen state and the paper honest with each other.
    search.value = '';
    filter('');
    window.print();
  });

  // The customer-resources pages still switch language in the DOM and read
  // this key; the manual's language is in its URL. Keeping them in step means
  // a reader who follows a footer link stays in the language they were in.
  try {
    window.localStorage.setItem(
      'pwe-public-language',
      document.documentElement.lang.startsWith('zh') ? 'zh' : 'en',
    );
  } catch (error) {
    // Private browsing can refuse storage; the URL still carries the language.
  }
})();
