import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const json = (value: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname === '/api/v1/auth/me') {
      await json({ user: { id: 'user-1', username: 'family-member', system_role: 'user' }, csrf_token: 'csrf-token' })
      return
    }
    if (url.pathname === '/api/v1/groups') {
      await json({ items: [] })
      return
    }
    if (url.pathname === '/api/v1/photos/activity') {
      await json({ items: [], next_cursor: null, unseen_count: 0 })
      return
    }
    if (url.pathname === '/api/v1/photos/storage-status') {
      await json({
        status: 'available',
        available: true,
        writable: true,
        free_bytes: 1_000_000,
        minimum_free_bytes: 100_000,
        total_bytes: 2_000_000,
      })
      return
    }
    if (url.pathname === '/api/v1/photos/timeline') {
      await json({ year: Number(url.searchParams.get('year')), months: [] })
      return
    }
    if (url.pathname === '/api/v1/photos') {
      await json({ items: [], next_cursor: null, total_count: 0 })
      return
    }
    await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })
})

test('navigates the authenticated household apps on iPhone WebKit', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Recent updates' })).toBeVisible()
  await page.getByRole('link', { name: 'Cleaning', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Cleaning', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Shopping', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Shopping List' })).toBeVisible()
  await page.getByRole('link', { name: 'Photos', exact: true }).click()
  await expect(page).toHaveURL(/\/photos\/library$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Photos', exact: true })).toBeVisible()
})
