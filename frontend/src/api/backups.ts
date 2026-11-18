import { apiRequest } from '@/api/client'

export interface BackupItem {
  id: string
  filename: string
  created_at: string | null
  sha256: string | null
  size_bytes: number
}

export function listBackups() {
  return apiRequest<{ items: BackupItem[] }>('/api/admin/backups')
}

export function createBackup() {
  return apiRequest<{ filename: string }>('/api/admin/backups', { method: 'POST' })
}

export function restoreBackup(id: string) {
  return apiRequest<{ restored: string }>(`/api/admin/backups/${id}/restore`, {
    method: 'POST',
    body: JSON.stringify({ confirm: 'RESTORE' }),
  })
}
