import { apiRequest } from '@/api/client'
import type { HealthData } from '@/types/api'

export function fetchHealth() {
  return apiRequest<HealthData>('/api/health')
}
