export interface SetDraft {
  reps: number | null
  weight_kg: number | null
  duration_min: number | null
  distance_km: number | null
  completed?: boolean
  completed_at?: string | null
}

export function emptySet(): SetDraft {
  return { reps: null, weight_kg: null, duration_min: null, distance_km: null }
}

export function defaultSetsForCategory(category: string): SetDraft[] {
  if (category === 'CARDIO') return [{ ...emptySet(), duration_min: 30 }]
  if (category === 'STRETCH') return [{ ...emptySet(), duration_min: 10 }]
  return [
    { ...emptySet(), reps: 10, weight_kg: 20 },
    { ...emptySet(), reps: 10, weight_kg: 20 },
    { ...emptySet(), reps: 10, weight_kg: 20 },
    { ...emptySet(), reps: 10, weight_kg: 20 },
  ]
}

export function cloneSet(set: SetDraft): SetDraft {
  return {
    reps: set.reps,
    weight_kg: set.weight_kg,
    duration_min: set.duration_min,
    distance_km: set.distance_km,
  }
}

export function setsFromPlanExercise(item: {
  sets?: Array<{
    reps?: number | null
    weight_kg?: number | null
    duration_min?: number | null
    distance_km?: number | null
  }> | null
  target_sets?: number | null
  target_reps?: number | null
  target_weight_kg?: number | null
  target_duration_min?: number | null
  target_distance_km?: number | null
  category?: string
}): SetDraft[] {
  if (item.sets?.length) {
    return item.sets.map((set) => ({
      reps: set.reps ?? null,
      weight_kg: set.weight_kg ?? null,
      duration_min: set.duration_min ?? null,
      distance_km: set.distance_km ?? null,
    }))
  }
  const count = Math.max(1, Number(item.target_sets || 1))
  return Array.from({ length: count }, () => ({
    reps: item.target_reps ?? null,
    weight_kg: item.target_weight_kg ?? null,
    duration_min: item.target_duration_min ?? null,
    distance_km: item.target_distance_km ?? null,
  }))
}

export function formatSetsSummary(sets: SetDraft[] | null | undefined, category?: string): string {
  if (!sets?.length) return '—'
  if (category === 'CARDIO' || category === 'STRETCH') {
    return sets
      .map((set, index) => {
        const parts = [`第${index + 1}组`]
        if (set.duration_min != null) parts.push(`${set.duration_min}分钟`)
        if (set.distance_km != null) parts.push(`${set.distance_km}km`)
        return parts.join(' ')
      })
      .join('；')
  }
  return sets
    .map((set, index) => {
      const parts = [`第${index + 1}组`]
      if (set.reps != null) parts.push(`${set.reps}次`)
      if (set.weight_kg != null) parts.push(`${set.weight_kg}kg`)
      return parts.join(' ')
    })
    .join('；')
}

export function toNumberOrNull(value: string | number | null | undefined): number | null {
  if (value === '' || value == null) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}
