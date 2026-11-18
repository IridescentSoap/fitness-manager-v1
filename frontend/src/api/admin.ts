import { apiRequest } from '@/api/client'
import type { AdminUserItem } from '@/types/auth'

export function listUsers() {
  return apiRequest<{ items: AdminUserItem[] }>('/api/admin/users')
}

export function createUser(body: { username: string; display_name: string; password: string }) {
  return apiRequest<AdminUserItem>('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function updateUser(id: number, body: { display_name?: string; status?: string }) {
  return apiRequest<AdminUserItem>(`/api/admin/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function resetUserPassword(id: number, new_password: string) {
  return apiRequest<{ id: number; username: string; status: string }>(
    `/api/admin/users/${id}/reset-password`,
    {
      method: 'POST',
      body: JSON.stringify({ new_password }),
    },
  )
}
