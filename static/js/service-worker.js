/* Genius Chess Academy — Service Worker (PWA v4) */
const CACHE_NAME = 'gca-pwa-v4';
const PRECACHE_ASSETS = [
  '/static/css/gca-style.css',
  '/static/img/logo.png',
  '/static/img/icons/icon-192.png',
  '/static/img/icons/icon-512.png',
  '/static/fonts/Amiri-Regular.ttf',
  '/static/fonts/Amiri-Bold.ttf'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('Pre-caching warning:', err);
      });
    })
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

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Bypass absolu pour manifest, scripts racine, media, Django admin, APIs et scan
  if (
    url.pathname === '/manifest.webmanifest' || 
    url.pathname === '/manifest.json' || 
    url.pathname.endsWith('service-worker.js') ||
    url.pathname.startsWith('/admin/') ||
    url.pathname.includes('/scan/') ||
    url.pathname.startsWith('/media/')
  ) {
    return; // Laisser le navigateur gérer nativement sans interception
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
          return new Response('', { status: 404, statusText: 'Not Found' });
        });
      })
    );
    return;
  }

  // 2. Pour toute autre requête (pages HTML, endpoints dynamiques) :
  // Pas d'interception Service Worker afin d'éviter tout échec réseau résiduel.
  return;
});