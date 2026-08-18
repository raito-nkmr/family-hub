import { afterEach, describe, expect, it, vi } from 'vitest'
import type { UploadItem } from './api'
import {
  addBulkPhotoSharing,
  getPhotoExportUrl,
  getPhotoActivity,
  getPhotos,
  markPhotoActivitySeen,
  uploadItemContent,
} from './api'

const item: UploadItem = {
  id: '00000000-0000-4000-8000-000000000001',
  client_id: 'client-photo',
  filename: 'photo.jpeg',
  content_type: 'image/jpeg',
  size_bytes: 5,
  received_bytes: 0,
  status: 'queued',
  error_code: null,
  photo_id: null,
}

type MockUploadResponse = { status: number; offset: string } | { kind: 'error' } | { kind: 'timeout' }

function stubUploadFetch(responses: MockUploadResponse[]) {
  const fallback = responses[responses.length - 1]
  const requests: Array<{
    method: string
    body: BodyInit | null | undefined
    requestHeaders: Record<string, string>
  }> = []

  const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    const response = responses.shift() ?? fallback
    if (!response) throw new Error('Missing mocked fetch response')
    requests.push({
      method: init?.method ?? 'GET',
      body: init?.body,
      requestHeaders: Object.fromEntries(new Headers(init?.headers).entries()),
    })
    if ('kind' in response && response.kind === 'timeout') {
      await new Promise<never>((_, reject) => {
        const abort = () => reject(new DOMException('The operation was aborted', 'AbortError'))
        init?.signal?.addEventListener('abort', abort, { once: true })
      })
    }
    if ('kind' in response) throw new Error('Upload request failed')
    return new Response(null, {
      status: response.status,
      headers: { 'Upload-Offset': response.offset },
    })
  })

  vi.stubGlobal('fetch', fetchMock)
  return requests
}

describe('getPhotos', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends pagination and server-side search filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], next_cursor: null, total_count: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await getPhotos(
      {
        q: '北海道 旅行',
        dateFrom: '2026-07-01',
        dateTo: '2026-07-31',
        mineOnly: true,
        visibility: 'shared',
        capturedAtKnown: false,
        excludeAlbumId: 'album-1',
      },
      'next-page',
    )

    const url = new URL((fetchMock.mock.calls[0][0] as Request).url)
    expect(url.pathname).toBe('/api/v1/photos')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      limit: '50',
      cursor: 'next-page',
      q: '北海道 旅行',
      date_from: '2026-07-01',
      date_to: '2026-07-31',
      mine_only: 'true',
      visibility: 'shared',
      captured_at_known: 'false',
      exclude_album_id: 'album-1',
    })
  })
})

describe('photo activity', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads a cursor page and marks an event as seen', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null, unseen_count: 0 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await getPhotoActivity('next-page')
    await markPhotoActivitySeen('event-1')

    const url = new URL((fetchMock.mock.calls[0][0] as Request).url)
    expect(Object.fromEntries(url.searchParams)).toEqual({ limit: '30', cursor: 'next-page' })
    const markRequest = fetchMock.mock.calls[1][0] as Request
    expect(markRequest.method).toBe('POST')
    await expect(markRequest.clone().json()).resolves.toEqual({ event_id: 'event-1' })
  })
})

describe('bulk photo sharing', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('adds groups to the selected photos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ operation_id: 'operation-1', updated_count: 2, unchanged_count: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await addBulkPhotoSharing(['photo-1', 'photo-2'], ['group-1'])

    const request = fetchMock.mock.calls[0][0] as Request
    expect(new URL(request.url).pathname).toBe('/api/v1/photos/bulk-sharing')
    expect(request.method).toBe('POST')
    await expect(request.clone().json()).resolves.toEqual({
      photo_ids: ['photo-1', 'photo-2'],
      add_group_ids: ['group-1'],
    })
  })
})

describe('photo export', () => {
  it('builds a direct download URL for selected originals', () => {
    expect(getPhotoExportUrl(['photo-1', 'photo-2'])).toBe('/api/v1/photos/export?photo_ids=photo-1&photo_ids=photo-2')
  })
})

describe('uploadItemContent', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uploads a selected file with fetch and reports the completed offset', async () => {
    const requests = stubUploadFetch([
      { status: 200, offset: '0' },
      { status: 204, offset: '5' },
    ])
    const onProgress = vi.fn()

    await uploadItemContent(
      item,
      new File(['photo'], 'photo.jpeg', { type: 'image/jpeg' }),
      new AbortController().signal,
      onProgress,
    )

    expect(requests).toHaveLength(2)
    expect(requests[1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        body: expect.any(Blob),
        requestHeaders: expect.objectContaining({ 'upload-offset': '0' }),
      }),
    )
    expect(onProgress).toHaveBeenLastCalledWith(5)
  })

  it('uses the returned offset when starting the next chunk', async () => {
    const chunkSize = 8 * 1024 * 1024
    const file = new File([new Uint8Array(chunkSize + 1)], 'video.mov', { type: 'video/quicktime' })
    const requests = stubUploadFetch([
      { status: 200, offset: '0' },
      { status: 204, offset: String(chunkSize) },
      { status: 204, offset: String(chunkSize + 1) },
    ])
    const onProgress = vi.fn()

    await uploadItemContent(item, file, new AbortController().signal, onProgress)

    expect(requests).toHaveLength(3)
    expect(requests[2].requestHeaders['upload-offset']).toBe(String(chunkSize))
    expect(onProgress).toHaveBeenLastCalledWith(chunkSize + 1)
  })

  it('rejects a chunk response that does not advance the offset', async () => {
    stubUploadFetch([
      { status: 200, offset: '0' },
      { status: 204, offset: '0' },
    ])

    await expect(
      uploadItemContent(
        item,
        new File(['photo'], 'photo.jpeg', { type: 'image/jpeg' }),
        new AbortController().signal,
        vi.fn(),
      ),
    ).rejects.toMatchObject({ status: 409 })
  })

  it('retries a transient chunk failure at the same offset', async () => {
    stubUploadFetch([{ status: 200, offset: '0' }, { kind: 'error' }, { status: 204, offset: '5' }])
    const onProgress = vi.fn()

    await uploadItemContent(
      item,
      new File(['photo'], 'photo.jpeg', { type: 'image/jpeg' }),
      new AbortController().signal,
      onProgress,
    )

    expect(onProgress).toHaveBeenLastCalledWith(5)
  })

  it('retries when a chunk request remains pending until its timeout', async () => {
    vi.useFakeTimers()
    try {
      stubUploadFetch([{ status: 200, offset: '0' }, { kind: 'timeout' }, { status: 204, offset: '5' }])

      const upload = uploadItemContent(
        item,
        new File(['photo'], 'photo.jpeg', { type: 'image/jpeg' }),
        new AbortController().signal,
        vi.fn(),
      )
      await vi.advanceTimersByTimeAsync(5_250)
      await upload
    } finally {
      vi.useRealTimers()
    }
  })
})
