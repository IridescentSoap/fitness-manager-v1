export interface ApiSuccess<T> {
  data: T
}

export interface HealthData {
  status: string
  version: string
  timezone: string
  database: {
    status: string
    integrity_check: string
  }
}
