const CACHE_NAME = 'cascade-mountain-weather-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/style.css',
  '/posts/post-style.css',
  '/assets/header.js',
  '/assets/images/favicon.svg',
  '/about.html',
  '/model-tools.html'
];

// Install event - cache core assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn('Cache addAll failed for some assets:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event - always try network first, minimal caching
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Skip cross-origin requests
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    // Skip external resources like analytics and donations
    if (url.hostname.includes('buymeacoffee.com') || 
        url.hostname.includes('googletagmanager.com')) {
      return;
    }
  }

  const isHTMLRequest = event.request.headers.get('accept')?.includes('text/html');

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Only cache static assets (CSS, JS, images), NOT HTML pages
        if (response && response.status === 200 && !isHTMLRequest) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // Network failed, try cache for static assets only
        if (!isHTMLRequest) {
          return caches.match(event.request);
        }
        // For HTML pages when offline, return cached version with warning
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // Return a basic offline page
          return new Response(
            '<html><body><h1>Offline</h1><p>You are currently offline. Please check your connection for the latest forecast data.</p></body></html>',
            { headers: { 'Content-Type': 'text/html' } }
          );
        });
      })
  );
});
