/* StudioSaaS tenant CMS — Service Worker
 * Icon/manifest cache only; everything else goes straight to the network.
 * Bump CACHE_VERSION whenever PWA assets or icons change.
 */
const CACHE_VERSION = 'v7.3.1-tenant-pwa';
const ICON_CACHE = `lpcms-assets-${CACHE_VERSION}`;
const ASSETS = [
  '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png', '/manifest.json'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(ICON_CACHE).then(c => c.addAll(ASSETS)).catch((error) => {
    console.error('[StudioSaaS SW] Icon cache installation failed.', error);
    throw error;
  }));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      // This CMS should never serve stale HTML/JS/API data.
      // Keep only the current icon/logo cache; clear all previous PWA caches.
      keys.filter(k => k !== ICON_CACHE).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'CLEAR_LPCMS_CACHE') {
    e.waitUntil(caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))));
  }
});

self.addEventListener('fetch', (e) => {
  /* S1 (LetsPaintCMS v4.4 U7): only intercept GET requests for cached
   * static assets. Everything else — especially multipart POST uploads —
   * must NOT go through respondWith(fetch(...)): iOS WebKit drops the
   * request body when the SW forwards it, breaking all mobile uploads. */
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (ASSETS.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
  // Non-asset GETs fall through to the network without SW involvement.
});
