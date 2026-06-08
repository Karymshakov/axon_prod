// API Error response shape (what the server returns)
export interface ApiErrorResponse {
  detail?: string
  message?: string
  [key: string]: unknown
}

// API Endpoints (full paths for reference)
export const API_ENDPOINTS = {
  HEALTH: '/api/health/',
} as const

// Helper type for endpoint keys
export type ApiEndpoint = (typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS]
