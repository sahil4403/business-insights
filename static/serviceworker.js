/**
 * Business Insights Service Worker
 * Caching Strategies:
 * - Cache-First: Static assets (CSS, JS, fonts, icons, manifest)
 * - Network-First: Dynamic pages (HTML, API responses)
 * - Stale-While-Revalidate: Media files (/media/)
 * Version: 20261018.1 - Update this when changing caching logic
 */

const CACHE_VERSION = 'bizinsights-v20261018.1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;
const MEDIA_CACHE = `${CACHE_VERSION}-media`;
const OFFLINE_CACHE = `${CACHE_VERSION}-offline`;

// Assets to pre-cache on install
const PRECACHE_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/css/app.css',
  '/static/css/liquid-glass.css',
  '/static/css/dark-glass.css',
  '/static/icons/icon-192.svg',
  '/static/icons/icon-512.svg',
  '/static/js/liquid-tabbar.js',
  '/static/js/vendor-motion.js',
  'https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700;800&family=Fira+Code:wght@500;600;700&display=swap',
];

// Pages to cache for offline access
const OFFLINE_PAGES = [
  '/',
  '/offline/',
];

// Install event - pre-cache critical assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE).then((cache) => {
        console.log('[SW] Pre-caching static assets');
        return cache.addAll(PRECACHE_ASSETS.map(url => new Request(url, { credentials: 'same-origin' })));
      }),
      caches.open(OFFLINE_CACHE).then((cache) => {
        console.log('[SW] Caching offline pages');
        return cache.addAll(OFFLINE_PAGES.map(url => new Request(url, { credentials: 'same-origin' })));
      }),
    ]).then(() => {
      console.log('[SW] Install complete');
      return self.skipWaiting();
    })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            return name.startsWith('bizinsights-') && name !== CACHE_VERSION;
          })
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => {
      console.log('[SW] Activate complete');
      return self.clients.claim();
    })
  );
});

// Helper: Check if request is for static assets
function isStaticAsset(request) {
  const url = new URL(request.url);
  return (
    url.pathname.startsWith('/static/') ||
    url.pathname.startsWith('/static/icons/') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.jpg') ||
    url.pathname.endsWith('.jpeg') ||
    url.pathname.endsWith('.woff') ||
    url.pathname.endsWith('.woff2') ||
    url.pathname.endsWith('.ttf') ||
    url.pathname.endsWith('.eot') ||
    url.pathname === '/manifest.json'
  );
}

// Helper: Check if request is for media files
function isMediaRequest(request) {
  const url = new URL(request.url);
  return url.pathname.startsWith('/media/');
}

// Helper: Check if request is for API or dynamic pages
function isDynamicRequest(request) {
  const url = new URL(request.url);
  return (
    !isStaticAsset(request) &&
    !isMediaRequest(request) &&
    (url.pathname === '/' || url.pathname.startsWith('/customers/') ||
     url.pathname.startsWith('/trips/') || url.pathname.startsWith('/labour/') ||
     url.pathname.startsWith('/vehicles/') || url.pathname.startsWith('/expenses/') ||
     url.pathname.startsWith('/core/') || url.pathname.startsWith('/authentication/'))
  );
}

// Fetch event - implement caching strategies
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  // Strategy 1: Cache-First for static assets
  if (isStaticAsset(request)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // Strategy 2: Stale-While-Revalidate for media files
  if (isMediaRequest(request)) {
    event.respondWith(staleWhileRevalidate(request, MEDIA_CACHE));
    return;
  }

  // Strategy 3: Network-First for dynamic pages
  if (isDynamicRequest(request)) {
    event.respondWith(networkFirst(request, DYNAMIC_CACHE));
    return;
  }

  // Default: Network-First for everything else
  event.respondWith(networkFirst(request, DYNAMIC_CACHE));
});

// Cache-First Strategy: Serve from cache, fallback to network
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request);

  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[SW] Cache-first failed for:', request.url, error);
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      const offlineCache = await caches.open(OFFLINE_CACHE);
      return offlineCache.match('/offline/') || new Response('Offline', { status: 503 });
    }
    throw error;
  }
}

// Network-First Strategy: Try network first, fallback to cache
async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[SW] Network-first failed for:', request.url, error);
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      const offlineCache = await caches.open(OFFLINE_CACHE);
      return offlineCache.match('/offline/') || new Response('Offline', { status: 503 });
    }
    throw error;
  }
}

// Stale-While-Revalidate Strategy: Serve stale content while fetching fresh
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request);

  // Fetch fresh version in background
  const fetchPromise = fetch(request).then((networkResponse) => {
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  }).catch(() => null); // Silently fail background fetch

  // Return cached version immediately if available
  if (cachedResponse) {
    return cachedResponse;
  }

  // If no cache, wait for network
  return fetchPromise;
}

// Handle messages from clients (e.g., skip waiting)
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[SW] Service Worker loaded:', CACHE_VERSION);