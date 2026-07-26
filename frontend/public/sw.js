const CACHE_NAME = 'family-hub-shell-v2'
const BADGE_CACHE_NAME = 'family-hub-badge-v1'
const BADGE_COUNT_URL = '/__family-hub/badge-count'
const SHELL = [
  '/',
  '/manifest.webmanifest',
  '/app-icon.svg',
  '/app-icon-180.png',
  '/app-icon-192.png',
  '/app-icon-512.png',
  '/favicon.svg',
]

importScripts('/notification-target.js')
importScripts('/badge-count.js')

async function incrementAppBadge() {
  const cache = await caches.open(BADGE_CACHE_NAME)
  const stored = await cache.match(BADGE_COUNT_URL)
  const count = self.nextBadgeCount(stored ? await stored.text() : 0)
  await cache.put(BADGE_COUNT_URL, new Response(String(count)))
  if ('setAppBadge' in self.navigator) await self.navigator.setAppBadge(count)
}

async function clearAppBadge() {
  const operations = [caches.open(BADGE_CACHE_NAME).then((cache) => cache.delete(BADGE_COUNT_URL))]
  if ('clearAppBadge' in self.navigator) operations.push(self.navigator.clearAppBadge())
  await Promise.allSettled(operations)
}

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME && key !== BADGE_CACHE_NAME).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
    return
  }
  if (event.data?.type === 'CLEAR_BADGE') event.waitUntil(clearAppBadge())
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone()
          void caches.open(CACHE_NAME).then((cache) => cache.put('/', copy))
          return response
        })
        .catch(() => caches.match('/')),
    )
    return
  }

  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ??
          fetch(request).then((response) => {
            const copy = response.clone()
            void caches.open(CACHE_NAME).then((cache) => cache.put(request, copy))
            return response
          }),
      ),
    )
  }
})

self.addEventListener('push', (event) => {
  const data = event.data?.json() ?? {}
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title ?? 'Family Hub', {
        body: data.body ?? 'Family Hub has an update.',
        icon: '/app-icon-192.png',
        badge: '/app-icon-192.png',
        tag: data.tag,
        data: { url: data.url ?? '/' },
      }),
      incrementAppBadge().catch(() => undefined),
    ]),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = self.getSafeNotificationTarget(event.notification.data?.url, self.location.origin)
  const openApp = self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (clients) => {
    const existing = clients.find((client) => client.url.startsWith(self.location.origin))
    if (existing) {
      await existing.navigate(target)
      return existing.focus()
    }
    return self.clients.openWindow(target)
  })
  event.waitUntil(Promise.all([clearAppBadge(), openApp]))
})
