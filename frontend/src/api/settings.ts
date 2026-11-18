import { apiRequest } from '@/api/client'
import type { SharingSettings } from '@/types/auth'

export function getSharing() {
  return apiRequest<SharingSettings>('/api/settings/sharing')
}

export function updateSharing(body: SharingSettings) {
  return apiRequest<SharingSettings>('/api/settings/sharing', {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function updateProfile(body: { display_name?: string; target_weight_kg?: number | null }) {
  return apiRequest<{
    id: number
    username: string
    display_name: string
    role: string
    target_weight_kg: number | null
  }>('/api/settings/profile', {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}
