/**
 * TerraRaksha offline service worker.
 *
 * Provides offline caching for field workers during flood and disaster events
 * when cell connectivity degrades or drops. Stale-while-revalidate for data snapshot.
 */
'use strict';

const CACHE_NAME = 'terraraksha-v1';
const STATIC_ASSETS = [
  './',
  './index.html',
  './app.js',
  './logic.js',
  './style.css',
  './favicon.svg',
  './i18n.js',
  './manifest.json',
  './lab-status.html',
  './lab-status.css',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Snapshot data: network first, fallback to cached snapshot if offline
  if (url.pathname.endsWith('snapshot.json')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Static assets: cache-first with network fallback
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
