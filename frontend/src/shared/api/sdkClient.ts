import { client } from './generated/client.gen'
import { ApiError, clearCsrfToken, csrfHeaders } from './client'

client.setConfig({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  responseStyle: 'fields',
  throwOnError: false,
})

client.interceptors.request.use((request) => {
  const csrf = csrfHeaders()['X-CSRF-Token']
  if (!csrf || ['GET', 'HEAD', 'OPTIONS'].includes(request.method.toUpperCase())) return request
  const headers = new Headers(request.headers)
  headers.set('X-CSRF-Token', csrf)
  return new Request(request, { headers })
})

interface SdkResult<T> {
  data?: T
  error?: unknown
  response?: Response
}

function readErrorCode(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('detail' in error)) return undefined
  const detail = error.detail
  if (typeof detail !== 'object' || detail === null || !('code' in detail)) return undefined
  return typeof detail.code === 'string' ? detail.code : undefined
}

export async function sdkData<T>(request: Promise<SdkResult<T>>): Promise<T> {
  const result = await request
  if (result.response?.ok) return result.data as T
  const status = result.response?.status ?? 0
  if (status === 401) clearCsrfToken()
  if (status > 0) {
    throw new ApiError(status, `API request failed with status ${status}`, readErrorCode(result.error))
  }
  throw result.error instanceof Error ? result.error : new Error('API request failed before receiving a response')
}
