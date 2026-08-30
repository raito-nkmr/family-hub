import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('family-hub-language', 'ja'))
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': {
        user: { id: 'user-1', username: 'family-member', system_role: 'user' },
        csrf_token: 'csrf-token',
      },
      '/api/v1/groups': { items: [] },
      '/api/v1/photos/activity': { items: [], next_cursor: null, unseen_count: 0 },
      '/api/v1/photos/search-options': { uploaders: [], groups: [] },
      '/api/v1/photos/storage-status': {
        status: 'available',
        available: true,
        writable: true,
        free_bytes: 1_000_000,
        minimum_free_bytes: 100_000,
        total_bytes: 2_000_000,
      },
      '/api/v1/photos/timeline': { year: Number(new URL(route.request().url()).searchParams.get('year')), months: [] },
      '/api/v1/photos': { items: [], next_cursor: null, total_count: 0 },
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(responses[path] ?? {}),
    })
  })
})

async function readLayout(page: Page) {
  return page.evaluate(() => {
    const panel = document.querySelector<HTMLElement>('.photo-search')!
    const form = document.querySelector<HTMLElement>('.photo-search__form')!
    const rect = (element: Element) => {
      const bounds = element.getBoundingClientRect()
      return { left: bounds.left, right: bounds.right, width: bounds.width, height: bounds.height }
    }

    return {
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      panel: rect(panel),
      form: rect(form),
      controls: [...form.querySelectorAll('.form-control')].map(rect),
      actions: rect(form.querySelector('.photo-search__actions')!),
    }
  })
}

test('keeps the search form inside the photo content on a landscape tablet', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/photos/library')
  await expect(page.locator('.photo-search__form')).toBeVisible()

  const layout = await readLayout(page)
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth)
  expect(layout.form.right).toBeLessThanOrEqual(layout.panel.right + 1)
  for (const control of layout.controls) {
    expect(control.right).toBeLessThanOrEqual(layout.panel.right + 1)
    expect(control.height).toBe(42)
  }
})

test('keeps the expanded search form inside a compact mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 })
  await page.goto('/photos/library')
  await page.locator('.photo-search__toggle').click()

  const layout = await readLayout(page)
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth)
  expect(layout.form.right).toBeLessThanOrEqual(layout.panel.right + 1)
  expect(layout.actions.right).toBeLessThanOrEqual(layout.panel.right + 1)
  for (const control of layout.controls) {
    expect(control.right).toBeLessThanOrEqual(layout.panel.right + 1)
    expect(control.height).toBe(42)
  }
})
