/* StudioSaaS tenant CMS — Service Worker
 * Icon/manifest cache only; everything else goes straight to the network.
 * /manifest.json is precached, so a changed start_url — or a changed icon —
 * reaches installed clients only when CACHE_VERSION changes.
 *
 * This is `v` + the contents of /VERSION, with nothing else in it, and
 * release.sh rewrites it as part of the bump ledger. It used to carry a
 * hand-written label ('v10.18.0-pwe-house'), which meant the value had to be
 * remembered by a human on every release and the test that guarded it pinned
 * the literal: green for as long as you forgot, red the moment you got it
 * right. Deriving it deletes the failure mode instead of detecting it.
 */
const CACHE_VERSION = 'v10.19.0';
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
