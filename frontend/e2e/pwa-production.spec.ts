import { expect, test } from '@playwright/test'

test('registers the production Service Worker and installs the app shell cache', async ({ page }) => {
  await page.goto('/privacy')
  const state = await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready
    await new Promise<void>((resolve) => {
      if (registration.active) resolve()
      else navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), { once: true })
    })
    return {
      scope: registration.scope,
      caches: await caches.keys(),
    }
  })

  expect(state.scope).toBe('http://127.0.0.1:4174/')
  expect(state.caches).toContain('family-hub-shell-v2')
})
