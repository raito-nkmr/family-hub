import { expect, test, type Page } from '@playwright/test'

const media = [
  { id: 'portrait', original_filename: 'portrait.jpg', content_type: 'image/jpeg', width: 4032, height: 3024 },
  { id: 'landscape', original_filename: 'landscape.jpg', content_type: 'image/jpeg', width: 4032, height: 2268 },
  { id: 'square', original_filename: 'square.jpg', content_type: 'image/jpeg', width: 1200, height: 1200 },
  {
    id: 'unsupported-video',
    original_filename: 'unsupported.mov',
    content_type: 'video/quicktime',
    width: 1080,
    height: 1920,
  },
].map((item) => ({
  ...item,
  uploaded_by_user_id: 'user-1',
  uploaded_by_username: 'family-member',
  visibility: 'private',
  is_favorite: false,
  captured_at_original: '2026-08-20T00:00:00Z',
  captured_at_override: null,
  uploaded_at: '2026-08-20T00:00:00Z',
  effective_captured_at: '2026-08-20T00:00:00Z',
}))

const details = Object.fromEntries(
  media.map((item) => [
    item.id,
    {
      ...item,
      sharing: { group_ids: [] },
      memo: null,
      memo_updated_by_user_id: 'user-1',
      memo_updated_by_username: 'family-member',
      memo_updated_at: '2026-08-20T00:00:00Z',
      metadata_version: 1,
      storage_key: `originals/${item.id}`,
      size_bytes: 1_234_567,
      sha256: 'a'.repeat(64),
      lifecycle_state: 'active',
      trashed_at: null,
      purge_after: null,
      purge_requested_at: null,
    },
  ]),
)

async function mockPhotoApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const json = (value: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })
    const mediaRequest = url.pathname.match(
      /^\/api\/v1\/photos\/(portrait|landscape|square|unsupported-video)\/(thumbnail|content)$/,
    )
    if (mediaRequest) {
      const [, id, source] = mediaRequest
      if (id === 'unsupported-video' && source === 'content') {
        await route.fulfill({ status: 415, contentType: 'text/plain', body: 'Unsupported video' })
        return
      }
      const item = details[id]
      const renderedWidth = id === 'portrait' ? 3024 : item.width
      const renderedHeight = id === 'portrait' ? 4032 : item.height
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${renderedWidth}" height="${renderedHeight}" viewBox="0 0 ${renderedWidth} ${renderedHeight}"><rect width="100%" height="100%" fill="#315f8c" /></svg>`
      await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: svg })
      return
    }
    if (url.pathname === '/api/v1/auth/me') {
      await json({
        user: { id: 'user-1', username: 'family-member', system_role: 'user' },
        csrf_token: 'csrf-token',
        must_change_password: false,
      })
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
    if (url.pathname === '/api/v1/photos/search-options') {
      await json({ uploaders: [], groups: [] })
      return
    }
    if (url.pathname === '/api/v1/photos/timeline') {
      await json({ year: Number(url.searchParams.get('year')), months: [{ month: '2026-08', count: media.length }] })
      return
    }
    if (url.pathname === '/api/v1/photos') {
      await json({ items: media, next_cursor: null, total_count: media.length })
      return
    }
    const detailRequest = url.pathname.match(/^\/api\/v1\/photos\/(portrait|landscape|square|unsupported-video)$/)
    if (detailRequest) {
      await json(details[detailRequest[1]])
      return
    }
    await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })
}

async function openPhoto(page: Page, filename: string) {
  await page.getByRole('button', { name: `Open ${filename}` }).click()
  await expect(page.getByRole('heading', { name: filename })).toBeVisible()
}

async function expectContainedMedia(page: Page) {
  const layout = await page.evaluate(() => {
    const wrap = document.querySelector<HTMLElement>('.modal__image-wrap')!
    const mediaElement = document.querySelector<HTMLElement>('.modal__image')!
    const detail = document.querySelector<HTMLElement>('.modal__details')!
    const wrapRect = wrap.getBoundingClientRect()
    const mediaRect = mediaElement.getBoundingClientRect()
    const detailRect = detail.getBoundingClientRect()
    return {
      viewportWidth: window.innerWidth,
      minimumHeight:
        window.innerWidth <= 900
          ? Math.min(16 * 16, window.innerHeight * 0.35)
          : Math.min(22 * 16, window.innerHeight * 0.4),
      wrap: {
        left: wrapRect.left,
        top: wrapRect.top,
        right: wrapRect.right,
        bottom: wrapRect.bottom,
        height: wrapRect.height,
      },
      media: { left: mediaRect.left, top: mediaRect.top, right: mediaRect.right, bottom: mediaRect.bottom },
      detailTop: detailRect.top,
      objectFit: getComputedStyle(mediaElement).objectFit,
      documentWidth: document.documentElement.scrollWidth,
    }
  })
  const tolerance = 1

  expect(layout.wrap.height).toBeGreaterThanOrEqual(layout.minimumHeight - tolerance)
  expect(layout.media.left).toBeGreaterThanOrEqual(layout.wrap.left - tolerance)
  expect(layout.media.top).toBeGreaterThanOrEqual(layout.wrap.top - tolerance)
  expect(layout.media.right).toBeLessThanOrEqual(layout.wrap.right + tolerance)
  expect(layout.media.bottom).toBeLessThanOrEqual(layout.wrap.bottom + tolerance)
  expect(layout.detailTop).toBeGreaterThanOrEqual(layout.wrap.bottom - tolerance)
  expect(layout.objectFit).toBe('contain')
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth)
}

async function renderedImageWidth(page: Page) {
  return page.evaluate(() => {
    const wrapRect = document.querySelector<HTMLElement>('.modal__image-wrap')!.getBoundingClientRect()
    const image = document.querySelector<HTMLImageElement>('img.modal__image')!
    const scale = Math.min(wrapRect.width / image.naturalWidth, wrapRect.height / image.naturalHeight)
    return image.naturalWidth * scale
  })
}

async function expectCaptureDateWithinDetails(page: Page) {
  const layout = await page.evaluate(() => {
    const detailsRect = document.querySelector<HTMLElement>('.modal__details')!.getBoundingClientRect()
    const fieldRect = document.querySelector<HTMLElement>('.photo-memo__datetime-field')!.getBoundingClientRect()
    const input = document.querySelector<HTMLInputElement>(".photo-memo input[type='datetime-local']")!
    const inputRect = input.getBoundingClientRect()
    const inputStyle = getComputedStyle(input)
    return {
      viewportWidth: window.innerWidth,
      details: { left: detailsRect.left, right: detailsRect.right },
      field: { left: fieldRect.left, right: fieldRect.right },
      input: { left: inputRect.left, right: inputRect.right },
      inputPadding: { left: inputStyle.paddingLeft, right: inputStyle.paddingRight },
    }
  })
  const tolerance = 1

  expect(layout.field.left).toBeGreaterThanOrEqual(layout.details.left - tolerance)
  expect(layout.field.right).toBeLessThanOrEqual(layout.details.right + tolerance)
  expect(layout.input.left).toBeGreaterThanOrEqual(layout.details.left - tolerance)
  expect(layout.input.right).toBeLessThanOrEqual(layout.details.right + tolerance)
  expect(layout.input.right).toBeLessThanOrEqual(layout.viewportWidth + tolerance)
  expect(layout.inputPadding).toEqual({ left: '0px', right: '0px' })
}

for (const viewport of [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'iphone', width: 393, height: 852 },
  { name: 'compact-mobile', width: 360, height: 640 },
]) {
  test(`contains common photo aspect ratios on ${viewport.name} WebKit`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await mockPhotoApi(page)
    await page.goto('/photos/library')

    for (const filename of ['portrait.jpg', 'landscape.jpg', 'square.jpg']) {
      await openPhoto(page, filename)
      await expect(page.locator('.modal__image')).toHaveJSProperty('complete', true)
      await expectCaptureDateWithinDetails(page)
      await expectContainedMedia(page)
      if (filename === 'portrait.jpg') {
        expect(await renderedImageWidth(page)).toBeGreaterThanOrEqual(
          viewport.name === 'desktop' ? 540 : viewport.width - 3,
        )
      }
      await page.getByRole('button', { name: 'Close photo preview' }).click()
    }
  })
}

test('keeps a bounded fallback stage when MOV playback fails', async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 })
  await mockPhotoApi(page)
  await page.goto('/photos/library')
  await openPhoto(page, 'unsupported.mov')

  const fallback = page.locator('.modal__image.image-fallback')
  await expect(fallback).toBeVisible()
  await expect(fallback).toHaveCSS('display', 'flex')
  await expectContainedMedia(page)
})

test('keeps the Japanese capture date control inside a compact mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 })
  await page.addInitScript(() => window.localStorage.setItem('family-hub-language', 'ja'))
  await mockPhotoApi(page)
  await page.goto('/photos/library')
  await page.locator('.photo-card').first().click()

  await expect(page.locator('html')).toHaveAttribute('lang', 'ja')
  await expect(page.getByLabel('撮影日時を補正')).toBeVisible()
  await expectCaptureDateWithinDetails(page)
  await expect(page.locator('html')).toHaveJSProperty('scrollWidth', 360)
})

test('changes photos when tapping the edge navigation on iPad WebKit', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'ipad-webkit', 'This regression test targets iPad WebKit.')
  await mockPhotoApi(page)
  await page.goto('/photos/library')
  await openPhoto(page, 'portrait.jpg')

  await page.getByRole('button', { name: 'Next photo' }).tap()

  await expect(page.getByRole('heading', { name: 'landscape.jpg' })).toBeVisible()
})
