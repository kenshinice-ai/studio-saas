/* Let's Paint CMS — Service Worker
 * Network-only for app/API data; icon/logo cache only.
 * Bump CACHE_VERSION whenever PWA assets or icons change.
 */
const CACHE_VERSION = 'v4.3.3-aws';
const ICON_CACHE = `lpcms-assets-${CACHE_VERSION}`;
const ASSETS = [
  '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png',
  '/logo.png', '/logo-light.png', '/manifest.json', '/manifest-student.json'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(ICON_CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
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
  const url = new URL(e.request.url);
  if (ASSETS.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
    return;
  }
  e.respondWith(fetch(e.request));
});
