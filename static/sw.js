// Cache only content-hashed public assets. Learning/account/API state is network-only.
const CACHE_NAME = 'english-course-static-v3';

self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith('english-course-') && name !== CACHE_NAME) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const immutableAsset = url.origin === self.location.origin &&
    /^\/static\/.+\.[a-f0-9]{8,64}\.(css|js|png|jpe?g|webp|svg|woff2?)$/i.test(url.pathname);
  // Let the browser perform normal navigation/fetch; never reuse another user's
  // dashboard, progress, questions, token, chat response, or private media.
  if (event.request.method !== 'GET' || !immutableAsset) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(event.request);
    if (cached) return cached;
    const response = await fetch(event.request);
    if (response.ok && response.type === 'basic' && !/no-store|private/i.test(response.headers.get('Cache-Control') || '')) {
      await cache.put(event.request, response.clone());
    }
    return response;
  })());
});

// Background sync for offline actions (optional)
self.addEventListener('sync', event => {
  console.log('[SW] Background sync:', event.tag);
  if (event.tag === 'sync-data') {
    event.waitUntil(syncData());
  }
});

function syncData() {
  // Implement your background sync logic here
  return Promise.resolve();
}

// Push notification support (optional)
self.addEventListener('push', event => {
  console.log('[SW] Push received:', event);
  const options = {
    body: event.data ? event.data.text() : 'New notification',
    icon: '/static/images/icon-192x192.png',
    badge: '/static/images/icon-72x72.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    }
  };

  event.waitUntil(
    self.registration.showNotification('English Course', options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', event => {
  console.log('[SW] Notification clicked:', event);
  event.notification.close();

  event.waitUntil(
    clients.openWindow('/')
  );
});
