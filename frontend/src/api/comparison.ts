import { apiRequest } from '@/api/client'

export interface CandidateUser {
  id: number
  username: string
  display_name: string
  is_self: boolean
}

export interface RankItem {
  user_id: number
  display_name: string
  value: number | null
  rank?: number
  label?: string
}

export function listCandidates(scope: string) {
  return apiRequest<{ items: CandidateUser[] }>(`/api/comparison/users?scope=${scope}`)
}

export function getRankings(metric: string, from: string, to: string) {
  return apiRequest<{ items: RankItem[]; unranked: RankItem[] }>(
    `/api/comparison/rankings?metric=${metric}&from=${from}&to=${to}`,
  )
}

export function getMetrics(userIds: number[], metric: string, from: string, to: string) {
  return apiRequest<{ items: { user_id: number; display_name: string; value?: number | null; delta_kg?: number | null; delta_percent?: number | null }[] }>(
    `/api/comparison/metrics?user_ids=${userIds.join(',')}&metric=${metric}&from=${from}&to=${to}`,
  )
}

export function getWeightTrends(userIds: number[], from: string, to: string) {
  return apiRequest<{ series: { user_id: number; display_name: string; points: { date: string; weight_kg: number | null }[] }[]; note: string }>(
    `/api/comparison/weight-trends?user_ids=${userIds.join(',')}&from=${from}&to=${to}`,
  )
}
