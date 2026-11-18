import { apiRequest } from '@/api/client'

export interface Overview {
  from: string
  to: string
  timezone: string
  completed_sessions: number
  training_days: number
  planned_due: number
  planned_full: number
  plan_completion_rate: number | null
  action_completion_rate: number | null
  latest_weight: { weight_kg: number; record_date: string; recorded_at: string } | null
}

export interface TrainingSeries {
  series: { period: string; sessions: number; training_days: number }[]
  exercise_frequency: { exercise_id: number; name: string; count: number }[]
  calendar: { date: string; sessions: number }[]
}

export interface WeightSummary {
  latest: { weight_kg: number; record_date: string } | null
  target_weight_kg: number | null
  delta_kg: number | null
  delta_percent: number | null
  points: { date: string; weight_kg: number | null }[]
}

export interface WeightItem {
  id: number
  record_date: string
  recorded_at: string
  weight_kg: number
  note: string
}

export function getOverview(from: string, to: string) {
  return apiRequest<Overview>(`/api/statistics/overview?from=${from}&to=${to}`)
}

export function getTraining(from: string, to: string, groupBy = 'week') {
  return apiRequest<TrainingSeries>(`/api/statistics/training?from=${from}&to=${to}&group_by=${groupBy}`)
}

export function getWeightSummary(from: string, to: string) {
  return apiRequest<WeightSummary>(`/api/statistics/weight?from=${from}&to=${to}`)
}

export function listWeights(from: string, to: string) {
  return apiRequest<{ items: WeightItem[] }>(`/api/weights?from=${from}&to=${to}`)
}

export function createWeight(body: { record_date: string; recorded_at: string; weight_kg: number; note?: string }) {
  return apiRequest<WeightItem>('/api/weights', { method: 'POST', body: JSON.stringify(body) })
}

export function deleteWeight(id: number) {
  return apiRequest<void>(`/api/weights/${id}`, { method: 'DELETE' })
}
