export interface AuthUser {
  id: number
  username: string
  display_name: string
  role: 'ADMIN' | 'USER'
  status?: string
}

export interface AuthPayload {
  user: AuthUser
  csrf_token: string
  session_expires_at?: string
}

export interface ExerciseItem {
  id: number
  owner_user_id: number | null
  name: string
  category: 'STRENGTH' | 'CARDIO' | 'STRETCH'
  description: string | null
  is_active: boolean
  is_system: boolean
}

export interface SharingSettings {
  share_training_stats: boolean
  share_weight_change: boolean
  share_weight_values: boolean
}

export interface AdminUserItem {
  id: number
  username: string
  display_name: string
  role: string
  status: string
  created_at?: string
}
