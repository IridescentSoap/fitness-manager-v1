import { apiRequest } from '@/api/client'

export interface PlanSet {
  set_index?: number
  reps?: number | null
  weight_kg?: number | null
  duration_min?: number | null
  distance_km?: number | null
  completed?: boolean
  completed_at?: string | null
}

export interface PlanExercise {
  exercise_id: number
  sort_order: number
  target_sets?: number | null
  target_reps?: number | null
  target_weight_kg?: number | null
  target_duration_min?: number | null
  target_distance_km?: number | null
  capacity?: string | null
  sets?: PlanSet[]
  note?: string
}

export interface PlanDay {
  weekday: number
  title: string
  is_rest: boolean
  exercises: PlanExercise[]
}

export interface PlanItem {
  id: number
  name: string
  status: string
  start_date: string
  end_date: string | null
  days: PlanDay[]
}

export interface ScheduleItem {
  occurrence_id: number
  workout_date: string
  slot: string
  source: string
  title: string
  status: string
  actions_count: number
  exercises: PlanExercise[]
  record_status: string | null
  completion_result: string | null
}

export function listPlans() {
  return apiRequest<{ items: PlanItem[] }>('/api/plans')
}

export function createPlan(body: { name: string; start_date: string; end_date?: string | null; days: PlanDay[] }) {
  return apiRequest<PlanItem>('/api/plans', { method: 'POST', body: JSON.stringify(body) })
}

export function updatePlan(id: number, body: Partial<{ name: string; start_date: string; end_date: string | null; days: PlanDay[] }>) {
  return apiRequest<PlanItem>(`/api/plans/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

export function activatePlan(id: number) {
  return apiRequest<PlanItem>(`/api/plans/${id}/activate`, { method: 'POST' })
}

export function deactivatePlan(id: number) {
  return apiRequest<PlanItem>(`/api/plans/${id}/deactivate`, { method: 'POST' })
}

export function duplicatePlan(id: number) {
  return apiRequest<PlanItem>(`/api/plans/${id}/duplicate`, { method: 'POST' })
}

export function getSchedule(from: string, to: string) {
  return apiRequest<{ items: ScheduleItem[] }>(`/api/schedule?from=${from}&to=${to}`)
}

export function putOverride(date: string, body: { mode: 'REST' | 'REPLACE' | 'ADD'; title?: string; exercises: PlanExercise[] }) {
  return apiRequest(`/api/schedule/overrides/${date}`, { method: 'PUT', body: JSON.stringify(body) })
}

export function deleteOverride(date: string) {
  return apiRequest<void>(`/api/schedule/overrides/${date}`, { method: 'DELETE' })
}
