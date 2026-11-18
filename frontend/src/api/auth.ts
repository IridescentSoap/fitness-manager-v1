import { apiRequest, setCsrfToken } from '@/api/client'
import type { AuthPayload } from '@/types/auth'

export async function fetchSetupStatus() {
  return apiRequest<{ initialized: boolean }>('/api/setup/status')
}

export async function initializeAdmin(body: {
  username: string
  display_name: string
  password: string
}) {
  const data = await apiRequest<AuthPayload>('/api/setup/initialize', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  setCsrfToken(data.csrf_token)
  return data
}

export async function login(body: { username: string; password: string }) {
  const data = await apiRequest<AuthPayload>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  setCsrfToken(data.csrf_token)
  return data
}

export async function fetchMe() {
  const data = await apiRequest<AuthPayload>('/api/auth/me')
  setCsrfToken(data.csrf_token)
  return data
}

export async function logout() {
  await apiRequest<void>('/api/auth/logout', { method: 'POST' })
  setCsrfToken('')
}

export async function changePassword(body: { old_password: string; new_password: string }) {
  const data = await apiRequest<AuthPayload>('/api/auth/password', {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  setCsrfToken(data.csrf_token)
  return data
}
