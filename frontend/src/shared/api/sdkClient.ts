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

export async function sdkData<T>(request: Promise<SdkResult<T>>): Promise<T> {
  const result = await request
  if (result.response?.ok) return result.data as T
  const status = result.response?.status ?? 0
  if (status === 401) clearCsrfToken()
  if (status > 0) throw new ApiError(status, `API request failed with status ${status}`)
  throw result.error instanceof Error ? result.error : new Error('API request failed before receiving a response')
}
