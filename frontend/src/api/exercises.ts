import { apiRequest } from '@/api/client'
import type { ExerciseItem } from '@/types/auth'

export function listExercises() {
  return apiRequest<{ items: ExerciseItem[]; total: number }>('/api/exercises')
}

export function createExercise(body: {
  name: string
  category: string
  description?: string
}) {
  return apiRequest<ExerciseItem>('/api/exercises', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function updateExercise(
  id: number,
  body: Partial<{ name: string; category: string; description: string; is_active: boolean }>,
) {
  return apiRequest<ExerciseItem>(`/api/exercises/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function deactivateExercise(id: number) {
  return apiRequest<void>(`/api/exercises/${id}`, { method: 'DELETE' })
}
