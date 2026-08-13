const CACHE_NAME = 'alex-pwa-v1';
const STATIC_ASSETS = ['/', '/index.html', '/css/style.css', '/js/app.js', '/manifest.json'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(names => Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/chat') || url.pathname.startsWith('/health') || url.pathname.startsWith('/models') || url.pathname.startsWith('/memory') || url.pathname.startsWith('/vocal') || url.pathname.startsWith('/voices') || url.pathname.startsWith('/ws')) {
    e.respondWith(fetch(e.request).catch(() => new Response(JSON.stringify({ error: 'Offline' }), { headers: { 'Content-Type': 'application/json' } })));
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
    if (!resp || resp.status !== 200) return resp;
    const clone = resp.clone();
    caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
    return resp;
  })));
});

self.addEventListener('push', (e) => {
  const data = e.data ? e.data.json() : {};
  e.waitUntil(self.registration.showNotification(data.title || 'Alex', { body: data.body || 'Nouveau message', icon: 'icons/icon-192.png', vibrate: [200, 100, 200], data: data.url || '/' }));
});

self.addEventListener('notificationclick', (e) => { e.notification.close(); e.waitUntil(clients.openWindow(e.notification.data)); });