/* Privacy-preserving public portal analytics and tenant-scoped PWA setup. */
(function () {
  'use strict';

  var state = { tenantSlug: '', sessionId: '', started: false };

  function warn(message, error) {
    if (window.console && console.warn) console.warn('[StudioSaaS portal] ' + message, error || '');
  }

  function anonymousSessionId(slug) {
    var key = 'studiosaas_public_session_' + slug;
    try {
      var existing = sessionStorage.getItem(key);
      if (/^[A-Za-z0-9_-]{16,80}$/.test(existing || '')) return existing;
      var value = '';
      if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        value = window.crypto.randomUUID().replace(/-/g, '');
      } else if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
        var bytes = new Uint8Array(18);
        window.crypto.getRandomValues(bytes);
        value = Array.prototype.map.call(bytes, function (byte) {
          return byte.toString(16).padStart(2, '0');
        }).join('');
      }
      if (!value) throw new Error('Secure browser randomness is unavailable.');
      sessionStorage.setItem(key, value);
      return value;
    } catch (error) {
      warn('Anonymous analytics is disabled because a session ID could not be created.', error);
      return '';
    }
  }

  function campaign() {
    var params = new URLSearchParams(window.location.search);
    return {
      source: (params.get('utm_source') || '').slice(0, 80),
      medium: (params.get('utm_medium') || '').slice(0, 80),
      campaign: (params.get('utm_campaign') || '').slice(0, 80)
    };
  }

  function track(eventName, metadata) {
    if (!state.tenantSlug || !state.sessionId) return Promise.resolve(false);
    return fetch('/v1/public/' + encodeURIComponent(state.tenantSlug) + '/analytics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'omit',
      keepalive: true,
      body: JSON.stringify({
        event: eventName,
        sessionId: state.sessionId,
        path: window.location.pathname,
        campaign: campaign(),
        metadata: { label: String((metadata && metadata.label) || '').slice(0, 80) }
      })
    }).then(function (response) {
      if (!response.ok) throw new Error('Analytics endpoint returned ' + response.status + '.');
      return true;
    }).catch(function (error) {
      warn('An anonymous analytics event could not be recorded.', error);
      return false;
    });
  }

  function registerPortalPwa(slug) {
    var manifest = document.querySelector('link[data-tenant-portal-manifest]');
    if (manifest) manifest.href = '/' + encodeURIComponent(slug) + '/manifest-portal.json';
    if (!('serviceWorker' in navigator)) return;
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' + slug + '/' }).catch(function (error) {
        warn('The tenant-scoped service worker could not be registered.', error);
      });
    });
  }

  function initialise() {
    state.tenantSlug = String(document.body.dataset.tenantSlug || '').trim();
    if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(state.tenantSlug)) {
      warn('Portal analytics and PWA are disabled because the tenant slug is invalid.');
      return;
    }
    state.sessionId = anonymousSessionId(state.tenantSlug);
    registerPortalPwa(state.tenantSlug);
    track('page_view');

    document.addEventListener('click', function (event) {
      var target = event.target.closest('[data-analytics-event="cta_click"]');
      if (!target || target.closest('#my')) return;
      track('cta_click', { label: target.dataset.analyticsLabel || target.textContent.trim() });
    });
    var form = document.getElementById('joinForm');
    if (form) form.addEventListener('input', function () {
      if (state.started) return;
      state.started = true;
      track('registration_started');
    });
  }

  window.StudioSaaSAnalytics = { track: track };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialise);
  else initialise();
}());
