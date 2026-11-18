import { apiRequest } from '@/api/client'
import type { PlanExercise } from '@/api/plans'

export interface RecordExercise {
  id: number
  exercise_id: number | null
  name: string
  category: string
  sort_order: number
  completed: boolean
  completed_at: string | null
  target: Record<string, unknown>
}

export interface WorkoutRecord {
  id: number
  occurrence_id: number | null
  workout_date: string
  title: string
  origin: string
  status: string
  version: number
  submitted_at: string | null
  completed_count: number
  total_count: number
  completion_result: string | null
  exercises: RecordExercise[]
}

export interface ActionSave {
  record_id: number
  version: number
  action_id: number
  completed: boolean
  completed_at: string | null
  save_state: string
  record: WorkoutRecord
}

export function listRecords(from: string, to: string, page = 1, pageSize = 20) {
  return apiRequest<{ items: WorkoutRecord[]; total: number; page: number; page_size: number }>(
    `/api/records?from=${from}&to=${to}&page=${page}&page_size=${pageSize}`,
  )
}

export function createDraft(body: { occurrence_id?: number; workout_date?: string; title?: string; exercises?: PlanExercise[] }) {
  return apiRequest<WorkoutRecord>('/api/records/drafts', { method: 'POST', body: JSON.stringify(body) })
}

export function patchAction(
  recordId: number,
  actionId: number,
  expectedVersion: number,
  patch: {
    completed?: boolean
    capacity?: string
    exercise_id?: number
    sets?: Array<{
      reps?: number | null
      weight_kg?: number | null
      duration_min?: number | null
      distance_km?: number | null
    }>
    set_index?: number
    reps?: number | null
    weight_kg?: number | null
    duration_min?: number | null
    distance_km?: number | null
    set_completed?: boolean
  },
) {
  return apiRequest<ActionSave>(`/api/records/${recordId}/actions/${actionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ expected_version: expectedVersion, ...patch }),
  })
}

export function appendExercises(
  recordId: number,
  expectedVersion: number,
  exercises: PlanExercise[],
) {
  return apiRequest<WorkoutRecord>(`/api/records/${recordId}/exercises`, {
    method: 'POST',
    body: JSON.stringify({ expected_version: expectedVersion, exercises }),
  })
}

export function submitRecord(recordId: number, expectedVersion: number) {
  return apiRequest<{
    id: number
    status: string
    completion_result: string
    completed_count: number
    total_count: number
    submitted_at: string
    version: number
  }>(`/api/records/${recordId}/submit`, {
    method: 'POST',
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export function reopenRecord(recordId: number, expectedVersion: number) {
  return apiRequest<WorkoutRecord>(`/api/records/${recordId}/reopen`, {
    method: 'POST',
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export function deleteRecord(recordId: number) {
  return apiRequest<void>(`/api/records/${recordId}`, { method: 'DELETE' })
}
