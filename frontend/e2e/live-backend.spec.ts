import { expect, test } from '@playwright/test'

const username = process.env.FAMILY_HUB_E2E_USERNAME
const password = process.env.FAMILY_HUB_E2E_PASSWORD
const smokePngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='

interface SessionResponse {
  csrf_token: string
  must_change_password: boolean
}

interface UploadBatchResponse {
  id: string
  items: Array<{ id: string; size_bytes: number }>
}

test('authenticates, enforces CSRF, and accepts a same-origin upload chunk', async ({ page }) => {
  test.skip(!username || !password, 'Live E2E credentials are configured by the live Playwright config')

  await page.goto('/')
  await page.getByLabel('Username').fill(username ?? '')
  await page.getByLabel('Password').fill(password ?? '')
  await page.getByRole('button', { name: 'Sign in' }).click()

  const session = await page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/me', { credentials: 'include' })
    if (!response.ok) throw new Error(`Session restore failed with ${response.status}`)
    return (await response.json()) as SessionResponse
  })
  expect(session.must_change_password).toBe(false)
  expect(session.csrf_token).toBeTruthy()

  const csrfStatus = await page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' })
    return response.status
  })
  expect(csrfStatus).toBe(403)

  const clientId = `live-e2e-${Date.now()}`
  let batch: { status: number; body: UploadBatchResponse } | undefined
  try {
    batch = await page.evaluate(
      async ({ csrfToken, clientId, sizeBytes }) => {
        const response = await fetch('/api/v1/upload-batches', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
          body: JSON.stringify({
            files: [
              { client_id: clientId, filename: 'live-e2e.png', content_type: 'image/png', size_bytes: sizeBytes },
            ],
            sharing: { type: 'private', group_ids: [] },
          }),
        })
        return { status: response.status, body: (await response.json()) as UploadBatchResponse }
      },
      {
        csrfToken: session.csrf_token,
        clientId,
        sizeBytes: Uint8Array.from(atob(smokePngBase64), (value) => value.charCodeAt(0)).length,
      },
    )
    expect(batch.status).toBe(201)
    expect(batch.body.items).toHaveLength(1)
    const item = batch.body.items[0]
    if (!item) throw new Error('Live upload batch did not return an item')

    const upload = await page.evaluate(
      async ({ csrfToken, itemId, contentBase64 }) => {
        const content = Uint8Array.from(atob(contentBase64), (value) => value.charCodeAt(0))
        const response = await fetch(`/api/v1/upload-batches/items/${itemId}/content`, {
          method: 'PATCH',
          credentials: 'include',
          body: content,
          headers: {
            'Content-Type': 'application/offset+octet-stream',
            'Upload-Offset': '0',
            'X-CSRF-Token': csrfToken,
            'X-Upload-Attempt-ID': crypto.randomUUID(),
            'X-Upload-Route': 'same-origin',
          },
        })
        return { status: response.status, offset: response.headers.get('Upload-Offset') }
      },
      { csrfToken: session.csrf_token, itemId: item.id, contentBase64: smokePngBase64 },
    )
    expect(upload).toEqual({ status: 200, offset: String(item.size_bytes) })
  } finally {
    if (batch?.body.id) {
      const cancelStatus = await page.evaluate(
        async ({ csrfToken, batchId }) => {
          const response = await fetch(`/api/v1/upload-batches/${batchId}`, {
            method: 'DELETE',
            credentials: 'include',
            headers: { 'X-CSRF-Token': csrfToken },
          })
          return response.status
        },
        { csrfToken: session.csrf_token, batchId: batch.body.id },
      )
      expect(cancelStatus).toBe(204)
    }
  }
})
