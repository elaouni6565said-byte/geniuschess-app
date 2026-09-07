/* Genius Chess Academy — Service Worker (PWA) */
const CACHE_NAME = 'gca-pwa-v3';
const PRECACHE_ASSETS = [
  '/static/css/gca-style.css',
  '/static/img/logo.png',
  '/static/img/icons/icon-192.png',
  '/static/img/icons/icon-512.png',
  '/static/fonts/Amiri-Regular.ttf',
  '/static/fonts/Amiri-Bold.ttf'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('Pre-caching warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Bypass service worker for manifest and service worker itself
  if (url.pathname === '/manifest.webmanifest' || 
      url.pathname === '/manifest.json' || 
      url.pathname === '/service-worker.js') {
    return;
  }

  // 1. Static assets: Cache-First strategy
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((response) => {
          if (response && response.status === 200) {
            const respClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, respClone));
          }
          return response;
        }).catch(() => {
          return new Response('', { status: 408, statusText: 'Request Timeout' });
        });
      })
    );
    return;
  }

  // 2. Navigation / HTML pages: Network-First strategy (always fresh data)
  if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(req)
        .then((response) => {
          return response;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('/')))
    );
    return;
  }

  // 3. Other requests: Network with Cache fallback
  event.respondWith(
    fetch(req).catch(() => caches.match(req))
  );
});