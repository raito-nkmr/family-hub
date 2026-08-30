import { expect, test, type Page } from '@playwright/test'

const coverPhoto = {
  id: 'cover-photo',
  uploaded_by_user_id: 'user-1',
  uploaded_by_username: 'family-member',
  visibility: 'shared',
  sharing: { group_ids: ['group-1'] },
  is_favorite: false,
  memo: null,
  memo_updated_by_user_id: null,
  memo_updated_by_username: null,
  memo_updated_at: null,
  metadata_version: 1,
  original_filename: 'portrait-cover.jpg',
  storage_key: 'originals/2026/08/cover-photo.jpg',
  content_type: 'image/jpeg',
  size_bytes: 1_234_567,
  sha256: 'a'.repeat(64),
  width: 360,
  height: 640,
  captured_at_original: '2026-08-30T00:00:00Z',
  captured_at_override: null,
  uploaded_at: '2026-08-30T00:00:00Z',
  effective_captured_at: '2026-08-30T00:00:00Z',
  lifecycle_state: 'active',
  trashed_at: null,
  purge_after: null,
  purge_requested_at: null,
}

const album = {
  id: 'album-1',
  title: 'Wedding',
  description: null,
  created_by_user_id: 'user-1',
  created_by_username: 'family-member',
  created_at: '2026-08-30T00:00:00Z',
  updated_at: '2026-08-30T00:00:00Z',
  photo_count: 1,
  group_ids: ['group-1'],
  group_names: ['Family'],
  cover_photo_id: coverPhoto.id,
}

async function mockAlbumApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const json = (value: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })

    if (url.pathname === `/api/v1/photos/${coverPhoto.id}/thumbnail`) {
      const svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640" viewBox="0 0 360 640">',
        '<rect width="360" height="640" fill="#315f8c"/>',
        '<rect width="360" height="160" y="480" fill="#d77a45"/>',
        '</svg>',
      ].join('')
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
    if (url.pathname === '/api/v1/albums') {
      await json({ items: [album] })
      return
    }
    if (url.pathname === `/api/v1/albums/${album.id}`) {
      await json({ ...album, photos: [coverPhoto], next_cursor: null })
      return
    }
    await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })
}

test('uses the same crop for the album header and cover card', async ({ page }) => {
  await mockAlbumApi(page)
  await page.goto(`/photos/albums?album=${album.id}`)

  const coverFrame = page.locator(`.album-detail-header__cover[data-photo-id="${coverPhoto.id}"]`)
  const cardFrame = page.locator(`.album-photo-card__image-wrap[data-photo-id="${coverPhoto.id}"]`)
  await expect(coverFrame).toBeVisible()
  await expect(cardFrame).toBeVisible()
  await expect(coverFrame.locator('img')).toHaveJSProperty('complete', true)
  await expect(cardFrame.locator('img')).toHaveJSProperty('complete', true)

  const layout = await page.evaluate((photoId) => {
    const readThumbnail = (selector: string) => {
      const frame = document.querySelector<HTMLElement>(`${selector}[data-photo-id="${photoId}"]`)!
      const image = frame.querySelector<HTMLImageElement>('img')!
      const frameRect = frame.getBoundingClientRect()
      const imageStyle = getComputedStyle(image)
      return {
        photoId: frame.dataset.photoId,
        source: new URL(image.currentSrc || image.src).pathname,
        naturalSize: [image.naturalWidth, image.naturalHeight],
        frameAspectRatio: frameRect.width / frameRect.height,
        objectFit: imageStyle.objectFit,
        objectPosition: imageStyle.objectPosition,
        transform: imageStyle.transform,
      }
    }

    return {
      cover: readThumbnail('.album-detail-header__cover'),
      card: readThumbnail('.album-photo-card__image-wrap'),
    }
  }, coverPhoto.id)

  expect(layout.cover.photoId).toBe(coverPhoto.id)
  expect(layout.card.photoId).toBe(layout.cover.photoId)
  expect(layout.cover.source).toBe(`/api/v1/photos/${coverPhoto.id}/thumbnail`)
  expect(layout.card.source).toBe(layout.cover.source)
  expect(layout.cover.naturalSize).toEqual([360, 640])
  expect(layout.card.naturalSize).toEqual(layout.cover.naturalSize)
  expect(layout.cover.objectFit).toBe('cover')
  expect(layout.card.objectFit).toBe(layout.cover.objectFit)
  expect(layout.cover.objectPosition).toBe('50% 50%')
  expect(layout.card.objectPosition).toBe(layout.cover.objectPosition)
  expect(layout.cover.transform).toBe('none')
  expect(layout.card.transform).toBe(layout.cover.transform)
  expect(layout.cover.frameAspectRatio).toBeCloseTo(4 / 3, 2)
  expect(layout.card.frameAspectRatio).toBeCloseTo(layout.cover.frameAspectRatio, 2)
})
