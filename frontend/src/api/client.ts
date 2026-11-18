import type { ApiSuccess } from '@/types/api'

export class ApiError extends Error {
  code: string
  details: Record<string, unknown>

  constructor(code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = details
  }
}

let csrfToken = ''

export function setCsrfToken(token: string) {
  csrfToken = token
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }

  if (method !== 'GET' && method !== 'HEAD') {
    if (!headers.has('Content-Type') && init.body) {
      headers.set('Content-Type', 'application/json')
    }
    if (csrfToken) {
      headers.set('X-CSRF-Token', csrfToken)
    }
  }

  const response = await fetch(path, {
    ...init,
    method,
    headers,
    credentials: 'include',
  })

  if (response.status === 204) {
    return undefined as T
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    const error = payload?.error
    throw new ApiError(
      error?.code ?? 'HTTP_ERROR',
      error?.message ?? `Request failed (${response.status})`,
      error?.details ?? {},
    )
  }

  return (payload as ApiSuccess<T>).data
}
