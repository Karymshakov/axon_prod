import { Platform } from 'react-native'

const LOCAL_IP = process.env.EXPO_PUBLIC_LOCAL_IP || '192.168.1.2'
// API URL for Cayu sandbox - set by VPS environment
const SANDBOX_API_URL = process.env.EXPO_PUBLIC_API_URL

function getApiUrl(): string {
  // Priority 1: Explicit API URL from environment (for Expo Go on VPS)
  if (SANDBOX_API_URL) {
    return SANDBOX_API_URL
  }

  // Priority 2: Check if running in Cayu sandbox web (mobile-*.sandbox.cayu.app)
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    const hostname = window.location.hostname
    if (hostname.includes('.sandbox.cayu.app') && hostname.startsWith('mobile-')) {
      // In Cayu sandbox: use main domain's /api/ route
      // mobile-foo.sandbox.cayu.app -> foo.sandbox.cayu.app/api
      const mainDomain = hostname.replace('mobile-', '')
      return `https://${mainDomain}/api`
    }
  }

  // Priority 3: Local development - Use localhost for web, network IP for native
  return Platform.OS === 'web'
    ? 'http://localhost:8000/api'
    : `http://${LOCAL_IP}:8000/api`
}

const API_URL = getApiUrl()

// Structured API error for consistent error handling
export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown
  ) {
    super(`Request failed with status ${status}`)
    this.name = 'ApiError'
  }
}

// Centralized API fetch wrapper
// When auth is added, token injection happens here automatically
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: HeadersInit = { ...options.headers }

  // Set Content-Type for non-FormData requests
  if (!(options.body instanceof FormData)) {
    ;(headers as Record<string, string>)['Content-Type'] = 'application/json'
  }

  // Auth token injection will be added here when authentication is implemented
  // const token = await getAccessToken()  // async for SecureStore
  // if (token) {
  //   (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`
  // }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, data)
  }

  // Handle 204 No Content (common for DELETE operations)
  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

// API helper methods
export const api = {
  get: <T>(endpoint: string) => apiFetch<T>(endpoint),
  post: <T>(endpoint: string, data: unknown) =>
    apiFetch<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  put: <T>(endpoint: string, data: unknown) =>
    apiFetch<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  patch: <T>(endpoint: string, data: unknown) =>
    apiFetch<T>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: <T>(endpoint: string) =>
    apiFetch<T>(endpoint, { method: 'DELETE' }),
}

// Health check endpoint
export function fetchHealth() {
  return api.get<{ status: string; message: string }>('/health/')
}
