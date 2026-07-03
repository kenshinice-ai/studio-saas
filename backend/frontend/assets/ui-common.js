/* StudioSaaS shared UI runtime.
 *
 * Load this as the FIRST script on every StudioSaaS page. It provides:
 *   - window.StudioSaaS.esc(value)  — HTML-escape helper (single source of truth)
 *   - a fetch patch that adds the CSRF protection header
 *     `X-Requested-With: StudioSaaS` to every same-origin request.
 *
 * The backend rejects cookie-authenticated mutations that lack the header
 * (see server.py CSRF guard), so pages that skip this script cannot mutate.
 */
(function () {
  'use strict';

  const ns = (window.StudioSaaS = window.StudioSaaS || {});

  ns.esc = function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch]));
  };

  const CSRF_HEADER = 'X-Requested-With';
  const CSRF_VALUE = 'StudioSaaS';

  function isSameOrigin(url) {
    if (!url) return true;
    if (url.startsWith('/')) return true;
    try {
      return new URL(url, location.href).origin === location.origin;
    } catch (err) {
      return false;
    }
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = function patchedFetch(input, init) {
    try {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      if (isSameOrigin(url)) {
        init = init || {};
        const headers = new Headers(
          init.headers || (typeof input === 'object' && input && input.headers) || undefined
        );
        if (!headers.has(CSRF_HEADER)) headers.set(CSRF_HEADER, CSRF_VALUE);
        init = { ...init, headers };
      }
    } catch (err) {
      /* never block the request over header decoration */
    }
    return originalFetch(input, init);
  };
})();
