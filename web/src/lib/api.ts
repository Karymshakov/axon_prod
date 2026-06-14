const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export const SOURCE_OPTIONS = [
  { value: 'telegram', label: 'Telegram' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'whatsapp', label: 'WhatsApp' },
]

export const CONTACT_CHANNEL_OPTIONS = [
  { value: 'telegram', label: 'Telegram' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'manual', label: 'Ручной ввод' },
]

export const DISCOVERY_SOURCE_OPTIONS = [
  { value: 'friends', label: 'Друзья / рекомендация' },
  { value: 'ads', label: 'Реклама' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'google', label: 'Google / поиск' },
  { value: 'website', label: 'Сайт' },
  { value: 'partner', label: 'Партнер' },
  { value: 'repeat_guest', label: 'Уже был гостем' },
  { value: 'other', label: 'Другое' },
]

export type ContactChannel = 'telegram' | 'instagram' | 'whatsapp' | 'manual' | ''
export type DiscoverySource = string

export const DEFAULT_LEAD_STATUS_LABELS: Record<string, string> = {
  new: 'Новый',
  attempted: 'Попытка связи',
  contacted: 'Связались',
  nurturing: 'В работе',
  converted: 'Готовый',
  won: 'Готовый',
  lost: 'Потерян',
  unqualified: 'Не подходит',
  manual: 'Ручной',
  active: 'Активен',
  pending: 'Ожидает',
}

export function getLeadStatusLabel(
  status: string | null | undefined,
  stages?: Array<{ key: string; name: string }>,
): string {
  if (!status) return 'Не указан'
  const normalizedStatus = status.trim().toLowerCase()
  const stageName = stages?.find((stage) => stage.key === status)?.name?.trim()
  const normalizedStageName = stageName?.toLowerCase()
  if (normalizedStageName && DEFAULT_LEAD_STATUS_LABELS[normalizedStageName]) {
    return DEFAULT_LEAD_STATUS_LABELS[normalizedStageName]
  }
  return stageName || DEFAULT_LEAD_STATUS_LABELS[normalizedStatus] || status
}

export function getContactChannelLabel(value: string | null | undefined): string {
  if (!value) return 'Не указан'
  const normalized = value.toLowerCase()
  return CONTACT_CHANNEL_OPTIONS.find((option) => option.value === normalized)?.label ?? value
}

export function getDiscoverySourceLabel(value: string | null | undefined): string {
  if (!value) return 'Не указан'
  const normalized = value.toLowerCase()
  return DISCOVERY_SOURCE_OPTIONS.find((option) => option.value === normalized)?.label ?? value
}

export function resolveLeadContactChannel(lead: Pick<Lead, 'contact_channel' | 'telegram_chat_id' | 'telegram_user_id' | 'instagram_user_id' | 'whatsapp_phone' | 'source'>): ContactChannel {
  const channel = (lead.contact_channel || '').toLowerCase()
  if (channel === 'telegram' || channel === 'instagram' || channel === 'whatsapp' || channel === 'manual') {
    return channel
  }
  if (lead.telegram_chat_id || lead.telegram_user_id || lead.source?.toLowerCase() === 'telegram') return 'telegram'
  if (lead.instagram_user_id || lead.source?.toLowerCase() === 'instagram') return 'instagram'
  if (lead.whatsapp_phone || lead.source?.toLowerCase() === 'whatsapp') return 'whatsapp'
  return ''
}

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

// Token management
export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, access)
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

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

// Shared refresh promise so concurrent 401s wait on the same refresh call
let isRefreshing = false
let refreshPromise: Promise<string | null> | null = null

// Try to refresh the access token; returns new access token or null on failure
async function tryRefreshToken(): Promise<string | null> {
  // Concurrent callers piggyback on the in-flight refresh
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }
  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const refresh = getRefreshToken()
      if (!refresh) return null
      const res = await fetch(`${API_BASE}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      })
      if (!res.ok) {
        clearTokens()
        return null
      }
      const data = await res.json()
      // Save both tokens — ROTATE_REFRESH_TOKENS=True returns a new refresh token
      setTokens(data.access, data.refresh)
      return data.access
    } catch {
      clearTokens()
      return null
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()
  return refreshPromise
}

// Centralized API fetch wrapper with auto-refresh
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) }

  // Ensure DRF returns JSON, not the browsable API HTML
  headers['Accept'] = 'application/json'

  // Set Content-Type for non-FormData requests
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  // Add auth token if available
  const token = getAccessToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  let response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })

  // Auto-refresh on 401 when a refresh token is available
  if (response.status === 401 && getRefreshToken()) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`
      response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
      })
    } else {
      // Refresh failed — signal auth context to log the user out
      window.dispatchEvent(new Event('auth:session-expired'))
    }
  }

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

// Lead types
export interface Lead {
  id: number
  // Contact Details
  contact_person: string
  job_title: string
  email: string
  secondary_email: string
  phone: string
  mobile_phone: string
  office_phone: string
  website: string
  linkedin_url: string
  // Location/Geography
  address: string
  city: string
  state_province: string
  postal_code: string
  country: string
  timezone: string
  // Lead Management
  segment: string
  segment_display: string
  status: string
  source: string
  contact_channel: ContactChannel
  discovery_source: DiscoverySource
  discovery_source_detail: string
  estimated_value: string | null
  notes: string
  last_contacted: string | null
  // Hotel Booking Details
  check_in_date: string | null
  check_out_date: string | null
  guest_count: number | null
  room_type_preference: string
  meal_plan: 'none' | 'breakfast' | 'lunch' | 'dinner' | 'half_board_bl' | 'half_board_bd' | 'full_board' | ''
  // Summary & Next Steps
  problem_description: string
  next_steps: string
  // Communication Tracking
  preferred_contact_method: string
  preferred_contact_time: string
  language: string
  do_not_contact: boolean
  email_bounced: boolean
  unsubscribed_at: string | null
  // Sales Process
  next_follow_up_date: string | null
  expected_close_date: string | null
  lost_reason: string
  competitor: string
  referral_source: string
  campaign_source: string
  // Source-specific identifiers
  telegram_user_id: string
  telegram_username: string
  telegram_chat_id: string
  instagram_user_id: string
  instagram_username: string
  whatsapp_phone: string
  // Instagram intent classification
  instagram_intent_tier: 'booking_intent' | 'soft_interest' | 'not_relevant' | null
  // Manual takeover
  ai_paused: boolean
  ai_paused_at: string | null
  ai_paused_by: string
  // Assignment
  assigned_to: number | null
  assigned_to_name: string | null
  // AI Agent tracking
  ai_followup_count: number
  last_ai_followup_at: string | null
  // Objection tracking
  current_objection: 'price' | 'timing' | 'competitor' | 'authority' | 'need' | 'other' | ''
  current_objection_display: string
  last_objection_at: string | null
  objection_count: number
  // Timestamps
  created_at: string
  updated_at: string
  // Computed fields
  latest_note: string
  active_goals_count: number
  agent_context?: Record<string, any>
  last_contact_channel?: { channel: string; contact: string } | null
}

export interface LeadStats {
  [key: string]: number
  total: number
}

export interface CreateLeadData {
  contact_person: string
  email: string
  phone?: string
  segment?: string
  status?: string
  source?: string
  contact_channel?: string
  discovery_source?: string
  discovery_source_detail?: string
  check_in_date?: string | null
  check_out_date?: string | null
  guest_count?: number | null
  room_type_preference?: string
  meal_plan?: Lead['meal_plan']
  estimated_value?: string | null
  notes?: string
  last_contacted?: string | null
  instagram_intent_tier?: 'booking_intent' | 'soft_interest' | 'not_relevant' | null
}

export interface AssignableUser {
  id: number
  name: string
  email: string
}

// Lead API endpoints
export function fetchAssignableUsers() {
  return api.get<AssignableUser[]>('/leads/assignable_users/')
}

export interface FetchLeadsParams {
  status?: string
  segment?: string
  source?: string
  contact_channel?: string
  discovery_source?: string
  assigned_to?: string
  search?: string
}

export function fetchLeads(params?: FetchLeadsParams) {
  const qs = new URLSearchParams()
  if (params?.status) qs.append('status', params.status)
  if (params?.segment) qs.append('segment', params.segment)
  if (params?.source) qs.append('source', params.source)
  if (params?.contact_channel) qs.append('contact_channel', params.contact_channel)
  if (params?.discovery_source) qs.append('discovery_source', params.discovery_source)
  if (params?.assigned_to) qs.append('assigned_to', params.assigned_to)
  if (params?.search) qs.append('search', params.search)
  const queryString = qs.toString()
  return api.get<Lead[]>(`/leads/${queryString ? `?${queryString}` : ''}`)
}

export function fetchLeadStats() {
  return api.get<LeadStats>(`/leads/stats/`)
}

export function fetchLead(id: number) {
  return api.get<Lead>(`/leads/${id}/`)
}

export function fetchLeadSourceStats() {
  return api.get<Array<{ source: string; count: number }>>('/leads/source_stats/')
}

export function createLead(data: CreateLeadData) {
  return api.post<Lead>('/leads/', data)
}

export function updateLead(id: number, data: Partial<Lead>) {
  return api.patch<Lead>(`/leads/${id}/`, data)
}

export function deleteLead(id: number) {
  return api.delete(`/leads/${id}/`)
}

export function convertLeadToCustomer(id: number) {
  return api.post<Customer>(`/leads/${id}/convert_to_customer/`, {})
}

export function sendTelegramMessage(id: number, message: string) {
  return api.post<{ message: string; data: unknown }>(`/leads/${id}/send_telegram/`, { message })
}

// Integration types
export interface TelegramIntegrationStatus {
  configured: boolean
  bot_username: string | null
  bot_first_name?: string | null
  connected_at: string | null
  error?: string
}

// Integration API endpoints
export function fetchTelegramIntegrationStatus() {
  return api.get<TelegramIntegrationStatus>('/integrations/telegram/status/')
}

export interface SaveTelegramTokenResponse {
  success: boolean
  bot_username?: string
  bot_first_name?: string
  error?: string
}

export function saveTelegramToken(botToken: string) {
  return api.post<SaveTelegramTokenResponse>('/integrations/telegram/save-token/', { bot_token: botToken })
}

export interface DisconnectTelegramResponse {
  success: boolean
  message?: string
  error?: string
}

export function disconnectTelegram() {
  return api.post<DisconnectTelegramResponse>('/integrations/telegram/disconnect/', {})
}

export interface RegisterTelegramWebhookResponse {
  success: boolean
  webhook_url?: string
  error?: string
}

export function registerTelegramWebhook(baseUrl?: string) {
  return api.post<RegisterTelegramWebhookResponse>('/integrations/telegram/register-webhook/', baseUrl ? { base_url: baseUrl } : {})
}

export interface SendTelegramMessageResponse {
  success: boolean
  message_id?: number
  error?: string
}

export function sendTelegramMessageFromComms(leadId: number, message: string) {
  return api.post<SendTelegramMessageResponse>('/communications/telegram/send/', { lead_id: leadId, message })
}

// Instagram Integration types
export interface InstagramStatus {
  connected: boolean
  instagram_username?: string
  profile_picture_url?: string
  token_expired?: boolean
  token_expiring_soon?: boolean
  token_expiry?: string | null
  connected_at?: string | null
  webhook_url?: string
  embed_url?: string
  callback_url?: string
  configured_callback_url?: string
  callback_warning?: string
  oauth_last_started_at?: string | null
  oauth_last_callback_at?: string | null
  oauth_last_status?: string
  oauth_last_error?: string
  app_secret_set?: boolean
  app_id?: string
  verify_token?: string
}

export interface InstagramRefreshTokenResponse {
  status: string
  token_expiry: string
}

export interface SendInstagramMessageResponse {
  success: boolean
  message_id?: string
  error?: string
}

// Instagram API endpoints
export function fetchInstagramStatus() {
  return api.get<InstagramStatus>('/integrations/instagram/status/')
}

export function disconnectInstagram() {
  return api.post<{ status: string }>('/integrations/instagram/disconnect/', {})
}

export function refreshInstagramToken() {
  return api.post<InstagramRefreshTokenResponse>('/integrations/instagram/refresh-token/', {})
}

export function saveInstagramAppCredentials(data: { app_id?: string; app_secret: string; webhook_verify_token?: string }) {
  return api.post<{ success: boolean }>('/integrations/instagram/save-app-credentials/', data)
}

export function resubscribeInstagramWebhook() {
  return api.post<{ success: boolean }>('/integrations/instagram/resubscribe-webhook/', {})
}

export function sendInstagramMessageFromComms(leadId: number, message: string) {
  return api.post<SendInstagramMessageResponse>('/communications/instagram/send/', { lead_id: leadId, message })
}

// WhatsApp Integration types
export interface WhatsAppIntegrationStatus {
  connected: boolean
  phone_number_id?: string | null
  display_phone_number?: string | null
  verified_name?: string | null
  waba_id?: string | null
  token_expired?: boolean
  token_expiring_soon?: boolean
  token_expires_at?: string | null
  webhook_subscribed?: boolean
  connected_at?: string | null
  app_id?: string | null
  app_secret_set?: boolean
  verify_token?: string | null
  webhook_url?: string | null
}

export interface DisconnectWhatsAppResponse {
  status: string
}

export interface SendWhatsAppMessageResponse {
  success: boolean
  message_id?: string
  error?: string
}

// WhatsApp Integration API endpoints
export function fetchWhatsAppIntegrationStatus() {
  return api.get<WhatsAppIntegrationStatus>('/integrations/whatsapp/status/')
}

export function disconnectWhatsApp() {
  return api.post<DisconnectWhatsAppResponse>('/integrations/whatsapp/disconnect/', {})
}

export function connectWhatsAppManual(data: { phone_number_id: string; waba_id: string; access_token: string; app_id?: string; app_secret?: string; verify_token?: string }) {
  return api.post<{ success: boolean; display_phone_number?: string; verified_name?: string; verify_token?: string }>('/integrations/whatsapp/connect/', data)
}

export function saveWhatsAppAppCredentials(data: { app_id?: string; app_secret: string }) {
  return api.post<{ success: boolean }>('/integrations/whatsapp/save-app-credentials/', data)
}

export function sendWhatsAppMessageFromComms(leadId: number, message: string) {
  return api.post<SendWhatsAppMessageResponse>('/communications/whatsapp/send/', { lead_id: leadId, message })
}

// Pipeline Stage types
export interface PipelineStage {
  id: number
  name: string
  key: string
  description: string
  order: number
  is_final: boolean
  created_at: string
  updated_at: string
}

export interface CreatePipelineStageData {
  name: string
  key: string
  description?: string
  order?: number
  is_final?: boolean
}

// Pipeline Stage API endpoints
export function fetchPipelineStages() {
  return api.get<PipelineStage[]>(`/pipeline-stages/`)
}

// Segment types
export interface Segment {
  id: number
  name: string
  key: string
  order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateSegmentData {
  name: string
  key: string
  order?: number
  is_active?: boolean
}

// Segment API endpoints
export function fetchSegments() {
  return api.get<Segment[]>('/segments/')
}

export function createSegment(data: CreateSegmentData) {
  return api.post<Segment>('/segments/', data)
}

export function updateSegment(id: number, data: Partial<CreateSegmentData>) {
  return api.patch<Segment>(`/segments/${id}/`, data)
}

export function deleteSegment(id: number) {
  return api.delete(`/segments/${id}/`)
}

export function createPipelineStage(data: CreatePipelineStageData) {
  return api.post<PipelineStage>('/pipeline-stages/', data)
}

export function updatePipelineStage(id: number, data: Partial<CreatePipelineStageData>) {
  return api.patch<PipelineStage>(`/pipeline-stages/${id}/`, data)
}

export function deletePipelineStage(id: number) {
  return api.delete(`/pipeline-stages/${id}/`)
}

// Customer types
export interface Customer {
  id: number
  lead: number | null
  lead_id: number | null
  contact_person: string
  email: string
  phone: string
  // Business info
  segment: string
  segment_display: string
  source: string
  customer_status: 'active' | 'inactive'
  customer_status_display: string
  notes: string
  // Communication channels
  telegram_chat_id: string
  telegram_username: string
  instagram_user_id: string
  instagram_username: string
  whatsapp_phone: string
  // Computed fields
  has_telegram: boolean
  has_instagram: boolean
  has_whatsapp: boolean
  created_at: string
  updated_at: string
}

export interface CreateCustomerData {
  contact_person: string
  email: string
  phone?: string
  segment?: string
  source?: string
  customer_status?: 'active' | 'inactive'
  notes?: string
}

// Customer API endpoints
export function fetchCustomers() {
  return api.get<Customer[]>('/customers/')
}

export function fetchCustomer(id: number) {
  return api.get<Customer>(`/customers/${id}/`)
}

export function createCustomer(data: CreateCustomerData) {
  return api.post<Customer>('/customers/', data)
}

export function updateCustomer(id: number, data: Partial<CreateCustomerData>) {
  return api.patch<Customer>(`/customers/${id}/`, data)
}

export function deleteCustomer(id: number) {
  return api.delete(`/customers/${id}/`)
}

// Customer messaging endpoints (using lead's communication channels)
export function sendTelegramToCustomer(customerId: number, message: string) {
  return api.post<SendTelegramMessageResponse>('/communications/telegram/send-customer/', { customer_id: customerId, message })
}

export function sendInstagramToCustomer(customerId: number, message: string) {
  return api.post<SendInstagramMessageResponse>('/communications/instagram/send-customer/', { customer_id: customerId, message })
}

export function sendWhatsAppToCustomer(customerId: number, message: string) {
  return api.post<SendWhatsAppMessageResponse>('/communications/whatsapp/send-customer/', { customer_id: customerId, message })
}

// Hotel Media types
export interface HotelMediaPhoto {
  id: number
  file_url: string | null
  order: number
  created_at: string
}

export type RoomCategory = 'standard_queen' | 'standard_twin' | 'comfort' | 'family' | 'other'

export interface HotelMediaItem {
  id: number
  title: string
  description: string
  tags: string[]
  category: string
  category_display: string
  room_category: RoomCategory | null
  media_type: 'photo' | 'video' | 'document'
  media_type_display: string
  file: string | null
  file_url: string | null
  video_url: string
  ai_send_count: number
  is_active: boolean
  photos: HotelMediaPhoto[]
  created_at: string
  updated_at: string
}

export interface CreateHotelMediaItemData {
  title: string
  description?: string
  tags?: string[]
  category?: string
  room_category?: RoomCategory | null
  media_type: 'photo' | 'video' | 'document'
  video_url?: string
}

export function fetchHotelMediaItems(params?: { media_type?: string; category?: string; search?: string }) {
  const query = new URLSearchParams()
  if (params?.media_type) query.set('media_type', params.media_type)
  if (params?.category) query.set('category', params.category)
  if (params?.search) query.set('search', params.search)
  const qs = query.toString()
  return api.get<HotelMediaItem[]>(`/hotel-media/${qs ? `?${qs}` : ''}`)
}

export function uploadHotelMediaItem(data: CreateHotelMediaItemData, file?: File) {
  const formData = new FormData()
  formData.append('title', data.title)
  formData.append('media_type', data.media_type)
  if (data.description) formData.append('description', data.description)
  if (data.tags) formData.append('tags', JSON.stringify(data.tags))
  if (data.category) formData.append('category', data.category)
  if (data.room_category) formData.append('room_category', data.room_category)
  if (data.video_url) formData.append('video_url', data.video_url)
  if (file) formData.append('file', file)

  return apiFetch<HotelMediaItem>('/hotel-media/', {
    method: 'POST',
    body: formData,
  })
}

export function updateHotelMediaItem(id: number, data: Partial<CreateHotelMediaItemData>, file?: File) {
  const formData = new FormData()
  if (data.title !== undefined) formData.append('title', data.title)
  if (data.media_type !== undefined) formData.append('media_type', data.media_type)
  if (data.description !== undefined) formData.append('description', data.description)
  if (data.tags !== undefined) formData.append('tags', JSON.stringify(data.tags))
  if (data.category !== undefined) formData.append('category', data.category)
  if (data.room_category !== undefined) formData.append('room_category', data.room_category ?? '')
  if (data.video_url !== undefined) formData.append('video_url', data.video_url)
  if (file) formData.append('file', file)

  return apiFetch<HotelMediaItem>(`/hotel-media/${id}/`, {
    method: 'PATCH',
    body: formData,
  })
}

export function deleteHotelMediaItem(id: number) {
  return api.delete(`/hotel-media/${id}/`)
}

export async function addPhotosToAlbum(id: number, files: File[]): Promise<HotelMediaItem> {
  // Upload one file at a time to avoid hitting proxy size limits
  let result!: HotelMediaItem
  for (const file of files) {
    const formData = new FormData()
    formData.append('files', file)
    result = await apiFetch<HotelMediaItem>(`/hotel-media/${id}/add-photos/`, {
      method: 'POST',
      body: formData,
    })
  }
  return result
}

export function deleteHotelMediaPhoto(photoId: number) {
  return api.delete(`/hotel-media/photos/${photoId}/`)
}

export function incrementHotelMediaAiSends(id: number) {
  return api.post<{ ai_send_count: number }>(`/hotel-media/${id}/increment_ai_sends/`, {})
}

// Lead Note types
export interface LeadNote {
  id: number
  lead: number
  content: string
  created_at: string
  updated_at: string
}

export interface CreateLeadNoteData {
  lead: number
  content: string
}

// Lead Note API endpoints
export function fetchLeadNotes(leadId: number) {
  return api.get<LeadNote[]>(`/lead-notes/?lead=${leadId}`)
}

export function createLeadNote(data: CreateLeadNoteData) {
  return api.post<LeadNote>('/lead-notes/', data)
}

export function updateLeadNote(id: number, data: Partial<CreateLeadNoteData>) {
  return api.patch<LeadNote>(`/lead-notes/${id}/`, data)
}

export function deleteLeadNote(id: number) {
  return api.delete(`/lead-notes/${id}/`)
}

// Lead Activity types
export interface LeadActivity {
  id: number
  lead: number
  activity_type: string
  activity_type_display: string
  description: string
  metadata: Record<string, unknown> | null
  is_read: boolean
  created_at: string
}

// Lead Activity API endpoints
export function fetchLeadActivities(leadId: number) {
  return api.get<LeadActivity[]>(`/lead-activities/?lead=${leadId}`)
}

export interface UnreadCountsResponse {
  counts: Record<string, Record<string, number>>  // { lead_id: { channel: count } }
  total: number
}

export function fetchCommunicationsUnreadCounts() {
  return api.get<UnreadCountsResponse>('/communications/unread-counts/')
}

export function markCommunicationsRead(leadId: number, channel: string) {
  return api.post<{ marked_read: number }>('/communications/mark-read/', { lead_id: leadId, channel })
}

// Task types
export interface Task {
  id: number
  lead: number
  title: string
  description: string
  task_type: 'call' | 'email' | 'meeting' | 'follow_up' | 'send_info' | 'send_proposal' | 'other'
  task_type_display: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  status_display: string
  due_date: string
  completed_at: string | null
  // Auto-execution fields
  is_auto_executable: boolean
  execution_type: 'send_message' | 'send_document' | 'update_status' | 'schedule_followup' | 'none'
  execution_type_display: string
  execution_content: string
  executed_at: string | null
  execution_result: string
  is_ai_generated: boolean
  is_overdue: boolean
  created_at: string
  updated_at: string
}

// Lead Goal types
export interface LeadGoal {
  id: number
  lead: number
  goal_type: 'collect_email' | 'collect_phone' | 'schedule_call' | 'schedule_meeting' | 'send_proposal' | 'send_info' | 'handle_objection' | 'close_deal' | 'qualify_lead' | 'get_decision_maker'
  goal_type_display: string
  status: 'active' | 'completed' | 'abandoned'
  status_display: string
  priority: 1 | 2 | 3
  priority_display: string
  description: string
  target_value: string
  achieved_value: string
  attempts: number
  is_ai_generated: boolean
  completed_at: string | null
  created_at: string
}

export interface CreateTaskData {
  lead: number
  title: string
  description?: string
  task_type?: 'call' | 'email' | 'meeting' | 'follow_up' | 'other'
  status?: 'pending' | 'completed' | 'cancelled'
  due_date: string
}

// Task API endpoints
export function fetchTasks(leadId?: number, status?: string) {
  const params = new URLSearchParams()
  if (leadId) params.append('lead', leadId.toString())
  if (status) params.append('status', status)
  const queryString = params.toString()
  return api.get<Task[]>(`/tasks/${queryString ? `?${queryString}` : ''}`)
}

export function createTask(data: CreateTaskData) {
  return api.post<Task>('/tasks/', data)
}

export function updateTask(id: number, data: Partial<CreateTaskData>) {
  return api.patch<Task>(`/tasks/${id}/`, data)
}

export function deleteTask(id: number) {
  return api.delete(`/tasks/${id}/`)
}

export function completeTask(id: number) {
  return api.post<Task>(`/tasks/${id}/complete/`, {})
}

// Lead Goal API endpoints
export function fetchLeadGoals(leadId?: number, status?: string) {
  const params = new URLSearchParams()
  if (leadId) params.append('lead', leadId.toString())
  if (status) params.append('status', status)
  const queryString = params.toString()
  return api.get<LeadGoal[]>(`/lead-goals/${queryString ? `?${queryString}` : ''}`)
}

export function fetchGoalsForLead(leadId: number) {
  return api.get<LeadGoal[]>(`/leads/${leadId}/goals/`)
}

export function createLeadGoal(data: { lead: number; goal_type: string; priority?: number; target_value?: string; notes?: string }) {
  return api.post<LeadGoal>('/lead-goals/', data)
}

export function updateLeadGoal(id: number, data: Partial<{ goal_type: string; status: string; priority: number; target_value: string; current_value: string; notes: string }>) {
  return api.patch<LeadGoal>(`/lead-goals/${id}/`, data)
}

export function completeLeadGoal(id: number, currentValue?: string) {
  return api.post<LeadGoal>(`/lead-goals/${id}/complete/`, { current_value: currentValue })
}

export function initializeGoalsForLead(leadId: number) {
  return api.post<{ created: number; goals: LeadGoal[] }>(`/leads/${leadId}/initialize_goals/`, {})
}

export function triggerInstagramAiResponse(leadId: number) {
  return api.post<{ status: string }>(`/leads/${leadId}/trigger_instagram_ai_response/`, {})
}

export function handbackToAI(leadId: number) {
  return api.post<{ status: string }>(`/leads/${leadId}/handback/`, {})
}

export function toggleAiPause(leadId: number) {
  return api.post<Lead>(`/leads/${leadId}/toggle-ai-pause/`, {})
}

export interface ResetLeadAiMemoryResponse {
  lead: Lead
  reset_summary: {
    cleared_fields: string[]
    flow_state_cleared: boolean
    ai_goals_deleted: number
    ai_tasks_deleted: number
    ai_activities_deleted: number
  }
}

export function resetLeadAiMemory(leadId: number) {
  return api.post<ResetLeadAiMemoryResponse>(`/leads/${leadId}/reset-ai-memory/`, {})
}

export interface CopilotSuggestionResponse {
  suggestion: string
}

export function generateCopilotSuggestion(leadId: number) {
  return api.post<CopilotSuggestionResponse>(`/leads/${leadId}/generate-copilot-suggestion/`, {})
}

// AI Configuration types
export interface AIConfig {
  id: number
  // Auto-Response (Reactive)
  ai_auto_response: boolean
  auto_extract_data: boolean
  response_delay: number
  telegram_ai_paused: boolean
  instagram_ai_paused: boolean
  whatsapp_ai_paused: boolean
  system_prompt: string
  company_profile: string
  // Proactive Outreach
  proactive_outreach_enabled: boolean
  check_frequency_hours: number
  inactivity_threshold_days: number
  max_followup_attempts: number
  // Autonomy Settings
  auto_status_progression: boolean
  smart_objection_handling: boolean
  auto_execute_tasks: boolean
  conversation_goals_enabled: boolean
  created_at: string
  updated_at: string
}

export interface UpdateAIConfigData {
  ai_auto_response?: boolean
  auto_extract_data?: boolean
  response_delay?: number
  telegram_ai_paused?: boolean
  instagram_ai_paused?: boolean
  whatsapp_ai_paused?: boolean
  system_prompt?: string
  company_profile?: string
  proactive_outreach_enabled?: boolean
  check_frequency_hours?: number
  inactivity_threshold_days?: number
  max_followup_attempts?: number
  auto_status_progression?: boolean
  smart_objection_handling?: boolean
  auto_execute_tasks?: boolean
  conversation_goals_enabled?: boolean
}

// AI Agent types
export interface RunAgentResponse {
  success: boolean
  results?: {
    processed: number
    messaged: number
    skipped: number
    errors: number
    disabled?: boolean
    ai_not_configured?: boolean
  }
  error?: string
}

export function runAgentNow() {
  return api.post<RunAgentResponse>('/ai-agent/run/', {})
}

// AI Configuration API endpoints
export function fetchAIConfig() {
  return api.get<AIConfig>('/ai-config/')
}

export function updateAIConfig(data: UpdateAIConfigData) {
  return api.patch<AIConfig>('/ai-config/update/', data)
}

// Auth types
export type UserRole = 'admin' | 'manager'
export type OrganizationRole = 'owner' | 'admin' | 'member'

export const USER_ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Администратор',
  manager: 'Менеджер',
}

export interface User {
  id: number
  email: string
  name: string
  is_admin: boolean
  is_superadmin: boolean
  is_active: boolean
  role: UserRole
  role_display: string
  language: 'en' | 'ru'
  current_organization_id: number | null
  current_organization_slug: string | null
  current_organization_name: string | null
  current_organization_role: OrganizationRole | null
  created_at: string
  updated_at: string
}

// Admin portal types
export interface AdminUser {
  id: number
  email: string
  name: string
  role: UserRole
  role_display: string
  is_active: boolean
  is_admin: boolean
  organization_id: number | null
  organization_slug: string | null
  organization_name: string | null
  organization_role: OrganizationRole | null
  last_login: string | null
  created_at: string
}

export interface AdminStats {
  total_users: number
  active_users: number
  new_this_month: number
  role_breakdown: Partial<Record<UserRole, number>>
}

export interface AdminUsersParams {
  search?: string
  role?: string
  status?: string
  ordering?: string
}

export interface AdminUserCreateData {
  email: string
  name: string
  role: UserRole
  is_active: boolean
  password: string
}

export interface AdminUserUpdateData {
  name?: string
  email?: string
  role?: UserRole
  is_active?: boolean
}

export interface LoginResponse {
  access: string
  refresh: string
  user: User
}

// Auth API endpoints
export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, data)
  }

  const data = await response.json()
  setTokens(data.access, data.refresh)
  return data
}

export async function logout(): Promise<void> {
  const refresh = getRefreshToken()
  if (refresh) {
    try {
      await apiFetch('/auth/logout/', {
        method: 'POST',
        body: JSON.stringify({ refresh }),
      })
    } catch {
      // Ignore logout errors - clear tokens anyway
    }
  }
  clearTokens()
}

export function getMe(): Promise<User> {
  return api.get<User>('/auth/me/')
}

export function updateUserLanguage(language: 'en' | 'ru'): Promise<User> {
  return api.patch<User>('/auth/profile/', { language })
}

export async function exportDevDatabase(): Promise<{ filename: string }> {
  const makeRequest = async (token: string | null) => fetch(`${API_BASE}/auth/dev-database-export/`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })

  let response = await makeRequest(getAccessToken())

  if (response.status === 401 && getRefreshToken()) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      response = await makeRequest(newToken)
    } else {
      window.dispatchEvent(new Event('auth:session-expired'))
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, data)
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const disposition = response.headers.get('Content-Disposition')
  const filename = disposition?.match(/filename="([^"]+)"/)?.[1] ?? 'omnios-dev-snapshot.zip'

  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(objectUrl)

  return { filename }
}

// Admin portal API
export function getAdminStats() {
  return api.get<AdminStats>('/auth/admin/stats/')
}

export function getAdminUsers(params: AdminUsersParams = {}) {
  const qs = new URLSearchParams()
  if (params.search) qs.set('search', params.search)
  if (params.role) qs.set('role', params.role)
  if (params.status) qs.set('status', params.status)
  if (params.ordering) qs.set('ordering', params.ordering)
  const query = qs.toString()
  return api.get<AdminUser[]>(`/auth/admin/users/${query ? `?${query}` : ''}`)
}

export function getAdminUser(id: number) {
  return api.get<AdminUser>(`/auth/admin/users/${id}/`)
}

export function createAdminUser(data: AdminUserCreateData) {
  return api.post<AdminUser>('/auth/admin/users/', data)
}

export function updateAdminUser(id: number, data: AdminUserUpdateData) {
  return api.patch<AdminUser>(`/auth/admin/users/${id}/`, data)
}

export function deleteAdminUser(id: number) {
  return api.delete(`/auth/admin/users/${id}/`)
}

// Paginated response
export interface PaginatedResponse<T> {
  count: number
  total_pages: number
  current_page: number
  page_size: number
  next: string | null
  previous: string | null
  results: T[]
}

// Audit log types
export interface AuditLogActor {
  id: number
  email: string
  name: string
}

export interface AuditLog {
  id: number
  timestamp: string
  action: 'create' | 'update' | 'delete'
  actor: AuditLogActor | null
  object_type: string | null
  object_repr: string
  changes: Record<string, [unknown, unknown]>
}

export interface AuditLogParams {
  page?: number
  page_size?: number
  search?: string
  actor?: string
  action?: 'create' | 'update' | 'delete'
  date_from?: string
  date_to?: string
  ordering?: string
}

export async function getAuditLogs(params?: AuditLogParams): Promise<PaginatedResponse<AuditLog>> {
  const searchParams = new URLSearchParams()
  if (params?.page) searchParams.set('page', String(params.page))
  if (params?.page_size) searchParams.set('page_size', String(params.page_size))
  if (params?.search) searchParams.set('search', params.search)
  if (params?.actor) searchParams.set('actor', params.actor)
  if (params?.action) searchParams.set('action', params.action)
  if (params?.date_from) searchParams.set('date_from', params.date_from)
  if (params?.date_to) searchParams.set('date_to', params.date_to)
  if (params?.ordering) searchParams.set('ordering', params.ordering)
  const qs = searchParams.toString()
  return api.get<PaginatedResponse<AuditLog>>(`/admin/audit-logs/${qs ? `?${qs}` : ''}`)
}


// ── Hotel Profile ─────────────────────────────────────────────────────────────

export interface HotelProfileLink {
  id: number
  label: string
  url: string
  order: number
}

export interface HotelProfile {
  hotel_name: string
  website: string
  description: string
  address: string
  directions: string
  links: HotelProfileLink[]
  updated_at: string
}

export function fetchHotelProfile() {
  return api.get<HotelProfile>('/hotel-profile/')
}

export function updateHotelProfile(data: Partial<Omit<HotelProfile, 'links' | 'updated_at'>>) {
  return api.patch<HotelProfile>('/hotel-profile/', data)
}

export function createHotelProfileLink(data: { label: string; url: string }) {
  return api.post<HotelProfileLink>('/hotel-profile-links/', data)
}

export function updateHotelProfileLink(id: number, data: Partial<{ label: string; url: string; order: number }>) {
  return api.patch<HotelProfileLink>(`/hotel-profile-links/${id}/`, data)
}

export function deleteHotelProfileLink(id: number) {
  return api.delete(`/hotel-profile-links/${id}/`)
}

// ── Hotel Policies ────────────────────────────────────────────────────────────

export interface HotelPolicy {
  id: number
  label: string
  emoji: string
  value: string
  description: string
  order: number
}

export function fetchHotelPolicies() {
  return api.get<HotelPolicy[]>('/hotel-policies/')
}

export function createHotelPolicy(data: { label: string; emoji?: string; value: string; description?: string }) {
  return api.post<HotelPolicy>('/hotel-policies/', data)
}

export function updateHotelPolicy(id: number, data: Partial<Omit<HotelPolicy, 'id'>>) {
  return api.patch<HotelPolicy>(`/hotel-policies/${id}/`, data)
}

export function deleteHotelPolicy(id: number) {
  return api.delete(`/hotel-policies/${id}/`)
}

// ── Hotel FAQs ────────────────────────────────────────────────────────────────

export interface HotelFAQ {
  id: number
  question: string
  answer: string
  order: number
}

export function fetchHotelFAQs() {
  return api.get<HotelFAQ[]>('/hotel-faqs/')
}

export function createHotelFAQ(data: { question: string; answer: string }) {
  return api.post<HotelFAQ>('/hotel-faqs/', data)
}

export function updateHotelFAQ(id: number, data: Partial<{ question: string; answer: string }>) {
  return api.patch<HotelFAQ>(`/hotel-faqs/${id}/`, data)
}

export function deleteHotelFAQ(id: number) {
  return api.delete(`/hotel-faqs/${id}/`)
}

// ── Handover Contacts ─────────────────────────────────────────────────────────

export interface HandoverContact {
  id: number
  name: string
  phone: string
  escalate_when: string
  order: number
}

export function fetchHandoverContacts() {
  return api.get<HandoverContact[]>('/handover-contacts/')
}

export function createHandoverContact(data: { name: string; phone: string; escalate_when?: string }) {
  return api.post<HandoverContact>('/handover-contacts/', data)
}

export function updateHandoverContact(id: number, data: Partial<Omit<HandoverContact, 'id'>>) {
  return api.patch<HandoverContact>(`/handover-contacts/${id}/`, data)
}

export function deleteHandoverContact(id: number) {
  return api.delete(`/handover-contacts/${id}/`)
}

// ── Playbooks ──────────────────────────────────────────────────────────────────

export interface Playbook {
  id: number
  name: string
  trigger_description: string
  instructions: string
  content: string
  is_active: boolean
  expires_at: string | null
  order: number
  created_at: string
  updated_at: string
}

export function fetchPlaybooks() {
  return api.get<Playbook[]>('/playbooks/')
}

export function createPlaybook(data: { name: string; trigger_description?: string; instructions?: string; content?: string; is_active?: boolean; expires_at?: string | null }) {
  return api.post<Playbook>('/playbooks/', data)
}

export function updatePlaybook(id: number, data: Partial<Omit<Playbook, 'id' | 'created_at' | 'updated_at'>>) {
  return api.patch<Playbook>(`/playbooks/${id}/`, data)
}

export function deletePlaybook(id: number) {
  return api.delete(`/playbooks/${id}/`)
}

// ── Reply Templates ───────────────────────────────────────────────────────────

export type ReplyTemplateChannel = 'all' | 'telegram' | 'instagram' | 'whatsapp'

export interface ReplyTemplate {
  id: number
  category: number
  category_name: string
  title: string
  text: string
  channel: ReplyTemplateChannel
  tags: string[]
  order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ReplyTemplateCategory {
  id: number
  name: string
  order: number
  is_active: boolean
  templates: ReplyTemplate[]
  created_at: string
  updated_at: string
}

export type ReplyTemplateInput = Partial<Pick<ReplyTemplate, 'category' | 'title' | 'text' | 'channel' | 'tags' | 'order' | 'is_active'>>

export function fetchReplyTemplateCategories() {
  return api.get<ReplyTemplateCategory[]>('/reply-template-categories/')
}

export function createReplyTemplateCategory(data: { name: string; order?: number; is_active?: boolean }) {
  return api.post<ReplyTemplateCategory>('/reply-template-categories/', data)
}

export function updateReplyTemplateCategory(id: number, data: Partial<Pick<ReplyTemplateCategory, 'name' | 'order' | 'is_active'>>) {
  return api.patch<ReplyTemplateCategory>(`/reply-template-categories/${id}/`, data)
}

export function deleteReplyTemplateCategory(id: number) {
  return api.delete(`/reply-template-categories/${id}/`)
}

export function fetchReplyTemplates(channel?: ReplyTemplateChannel | 'all') {
  const qs = channel ? `?channel=${channel}` : ''
  return api.get<ReplyTemplate[]>(`/reply-templates/${qs}`)
}

export function createReplyTemplate(data: Required<Pick<ReplyTemplate, 'category' | 'title' | 'text'>> & Partial<Pick<ReplyTemplate, 'channel' | 'tags' | 'order' | 'is_active'>>) {
  return api.post<ReplyTemplate>('/reply-templates/', data)
}

export function updateReplyTemplate(id: number, data: ReplyTemplateInput) {
  return api.patch<ReplyTemplate>(`/reply-templates/${id}/`, data)
}

export function deleteReplyTemplate(id: number) {
  return api.delete(`/reply-templates/${id}/`)
}

// Must use raw fetch — api.post() calls JSON.stringify which corrupts FormData
export async function processPlaybookFile(id: number, file: File): Promise<{ content: string }> {
  const token = getAccessToken()
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/playbooks/${id}/process-file/`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error || 'Failed to process file')
  }
  return res.json()
}

// ── Room Pricing ───────────────────────────────────────────────────────────────

export interface RoomPricing {
  id: number
  kategoria_nomera: string
  kolichestvo_chelovek: number
  guest_type: 'any' | 'family'
  deystvitelno_s: string | null
  deystvitelno_do: string | null
  dni_nedeli: string[]
  standartny_tarif: string | null
  s_zavtrakom: string | null
  polupansion: string | null
  polny_pansion: string | null
  created_at: string
  updated_at: string
}

export type RoomPricingFormData = Omit<RoomPricing, 'id' | 'created_at' | 'updated_at'>

export function fetchRoomPricing() {
  return api.get<RoomPricing[]>('/room-pricing/')
}

export function createRoomPricing(data: RoomPricingFormData) {
  return api.post<RoomPricing>('/room-pricing/', data)
}

export function updateRoomPricing(id: number, data: RoomPricingFormData) {
  return api.put<RoomPricing>(`/room-pricing/${id}/`, data)
}

export function deleteRoomPricing(id: number) {
  return api.delete(`/room-pricing/${id}/`)
}

export function fetchPromptPreview() {
  return api.get<{ prompt: string }>('/ai/prompt-preview/')
}

// ── AI Flows ───────────────────────────────────────────────────────────────────

export interface FlowConnection {
  id: number
  flow: number
  source_card: number
  target_card: number
  condition_label: string
  condition_keywords: string
  created_at: string
}

export interface FlowCard {
  id: number
  flow: number
  card_type: 'entry' | 'normal' | 'escalation'
  title: string
  message_template: string
  playbooks: number[]
  playbook_names: string[]
  position_x: number
  position_y: number
  created_at: string
  outgoing_connections: FlowConnection[]
}

export interface ConversationFlow {
  id: number
  name: string
  description: string
  is_active: boolean
  global_prompt: string
  card_count?: number
  cards?: FlowCard[]
  connections?: FlowConnection[]
  created_at: string
  updated_at: string
}

export interface AIFlowMode {
  mode: 'freeform' | 'flow_guided'
  updated_at: string
}

export function fetchFlows() {
  return api.get<ConversationFlow[]>('/flows/')
}

export function fetchFlow(id: number) {
  return api.get<ConversationFlow>(`/flows/${id}/`)
}

export function createFlow(data: { name: string; description?: string }) {
  return api.post<ConversationFlow>('/flows/', data)
}

export function updateFlow(id: number, data: Partial<{ name: string; description: string; is_active: boolean; global_prompt: string }>) {
  return api.patch<ConversationFlow>(`/flows/${id}/`, data)
}

export function deleteFlow(id: number) {
  return api.delete(`/flows/${id}/`)
}

export function activateFlow(id: number) {
  return api.post<{ status: string; id: number }>(`/flows/${id}/activate/`, {})
}

export function createFlowCard(flowId: number, data: Partial<FlowCard>) {
  return api.post<FlowCard>(`/flows/${flowId}/cards/`, data)
}

export function updateFlowCard(id: number, data: Partial<FlowCard>) {
  return api.patch<FlowCard>(`/flow-cards/${id}/`, data)
}

export function deleteFlowCard(id: number) {
  return api.delete(`/flow-cards/${id}/`)
}

export function createFlowConnection(flowId: number, data: { source_card: number; target_card: number; condition_label?: string; condition_keywords?: string }) {
  return api.post<FlowConnection>(`/flows/${flowId}/connections/`, data)
}

export function deleteFlowConnection(id: number) {
  return api.delete(`/flow-connections/${id}/`)
}

export function fetchAIFlowMode() {
  return api.get<AIFlowMode>('/flows/mode/')
}

export function updateAIFlowMode(mode: 'freeform' | 'flow_guided') {
  return api.put<AIFlowMode>('/flows/mode/', { mode })
}

export interface AITool {
  id: number
  name: string
  display_name: string
  description: string
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export function fetchAITools() {
  return api.get<AITool[]>('/ai-tools/')
}

export function updateAITool(id: number, data: Partial<Pick<AITool, 'display_name' | 'description' | 'is_enabled'>>) {
  return api.patch<AITool>(`/ai-tools/${id}/`, data)
}

export function createAITool(data: Pick<AITool, 'name' | 'display_name' | 'description'>) {
  return api.post<AITool>('/ai-tools/', data)
}

export function deleteAITool(id: number) {
  return api.delete(`/ai-tools/${id}/`)
}

// ── AI Model Config ────────────────────────────────────────────────────────────

export interface AIModelConfig {
  temperature: number
  max_tokens: number
  updated_at: string
}

export function fetchAIModelConfig() {
  return api.get<AIModelConfig>('/ai-model-config/')
}

export function updateAIModelConfig(data: Partial<Pick<AIModelConfig, 'temperature' | 'max_tokens'>>) {
  return api.put<AIModelConfig>('/ai-model-config/', data)
}

// ── Manager Transfer Config ────────────────────────────────────────────────────

export interface ManagerTransferConfig {
  channel: 'telegram' | 'whatsapp'
  recipient_id: string
  manager_name: string
  notification_template: string
  updated_at: string
}

export function fetchTransferConfig() {
  return api.get<ManagerTransferConfig>('/transfer-config/')
}

export function updateTransferConfig(data: Partial<Omit<ManagerTransferConfig, 'updated_at'>>) {
  return api.put<ManagerTransferConfig>('/transfer-config/', data)
}

// ── Agent Configs ──────────────────────────────────────────────────────────────

export interface AgentConfig {
  id: number
  name: 'booking' | 'cs' | 'consultant' | 'router'
  display_name: string
  system_prompt: string
  playbooks: number[]
  playbook_names: string[]
  tools: string[]
  is_editable: boolean
  created_at: string
  updated_at: string
}

export interface AgentContext {
  lead_id: number
  agent_context: {
    current_agent: string
    booking_step: string | null
    resume_card_id: string | null
    collected: {
      room_type: string | null
      guest_count: number | null
      checkin_date: string | null
      checkout_date: string | null
      meal_plan: string | null
    }
    handoff_context: string
    last_intent: string
  }
}

export function fetchAgents() {
  return api.get<AgentConfig[]>('/agents/')
}

export function updateAgent(id: number, data: Partial<Pick<AgentConfig, 'system_prompt' | 'playbooks' | 'tools'>>) {
  return api.patch<AgentConfig>(`/agents/${id}/`, data)
}

export function fetchAgentContext(agentId: number, leadId: number) {
  return api.get<AgentContext>(`/agents/${agentId}/context/${leadId}/`)
}

// ── Room Combinations ─────────────────────────────────────────────────────────

export interface RoomCombinationPrices {
  standard: number | null
  with_breakfast: number | null
  half_board: number | null
  full_board: number | null
}

export interface RoomCombination {
  index: number
  rooms: string[]
  room_count: number
  type: 'Основной' | 'Альтернатива' | 'Семейный'
  available: boolean
  prices: RoomCombinationPrices | null
  note: string
  is_custom: boolean
  id: number | null
}

export interface RoomCombinationGroup {
  guest_count: number
  combinations: RoomCombination[]
}

export function fetchRoomCombinations(guestCount?: number) {
  const url = guestCount != null
    ? `/room-combinations/?guest_count=${guestCount}`
    : '/room-combinations/'
  return api.get<{ results: RoomCombinationGroup[] }>(url)
}

export function fetchRoomCombinationRoomTypes() {
  return api.get<{ results: string[] }>('/room-combinations/room-types/')
}

export function createCustomCombination(data: {
  guest_count: number
  rooms: string[]
  combination_type: 'Основной' | 'Альтернатива' | 'Семейный'
  note: string
}) {
  return api.post<RoomCombination>('/room-combinations/custom/', data)
}

export function deleteCustomCombination(id: number) {
  return api.delete(`/room-combinations/custom/${id}/`)
}

export function hideAutoCombination(guestCount: number, combinationIndex: number) {
  return api.delete(`/room-combinations/hide/${guestCount}/${combinationIndex}/`)
}

export function saveRoomCombinationNote(
  guestCount: number,
  combinationIndex: number,
  note: string,
) {
  return api.put(`/room-combinations/notes/${guestCount}/${combinationIndex}/`, { note })
}

export function saveCombinationType(
  guestCount: number,
  combinationIndex: number,
  combinationType: 'Основной' | 'Альтернатива' | 'Семейный',
) {
  return api.patch(`/room-combinations/notes/${guestCount}/${combinationIndex}/`, { combination_type: combinationType })
}

export async function uploadRoomPricingExcel(
  file: File
): Promise<{ deleted: number; created: number; updated: number; skipped: number; skipped_details: { row: number; reason: string }[] }> {
  const token = getAccessToken()
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/room-pricing/upload-excel/`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error || 'Failed to upload file')
  }
  return res.json()
}

// Organization types
export interface Organization {
  id: number
  name: string
  slug: string
  logo: string | null
  plan: 'free' | 'starter' | 'pro' | 'enterprise'
  is_active: boolean
  owner_email: string
  trial_ends_at: string | null
  org_settings: Record<string, unknown>
  member_count: number
  current_user_role: 'owner' | 'admin' | 'member' | null
  created_at: string
  updated_at: string
}

export type OrganizationUpdateData = Partial<Pick<Organization, 'name' | 'plan' | 'is_active' | 'org_settings'>>

export interface OrgMember {
  id: number
  user_id: number
  user_email: string
  user_name: string
  role: 'owner' | 'admin' | 'member'
  joined_at: string
  is_active: boolean
}

export interface RegisterData {
  email: string
  password: string
  name: string
  organization_name: string
}

export interface RegisterResponse {
  access: string
  refresh: string
  user: User
  organization: Organization
}

// Organization API functions
export function fetchOrganizations() {
  return api.get<Organization[]>('/organizations/')
}

export function createOrganization(data: { name: string; plan?: string }) {
  return api.post<Organization>('/organizations/', data)
}

export function fetchOrganization(slug: string) {
  return api.get<Organization>(`/organizations/${slug}/`)
}

export function updateOrganization(slug: string, data: OrganizationUpdateData) {
  return api.patch<Organization>(`/organizations/${slug}/`, data)
}

export function switchOrganization(slug: string) {
  return api.post<{ success: boolean; organization: Organization }>(`/organizations/${slug}/switch/`, {})
}

export function fetchOrgMembers(slug: string) {
  return api.get<OrgMember[]>(`/organizations/${slug}/members/`)
}

export function inviteOrgMember(slug: string, data: { email: string; role: string }) {
  return api.post<{ success: boolean; created: boolean; member: OrgMember }>(`/organizations/${slug}/invite/`, data)
}

export function updateOrgMemberRole(slug: string, userId: number, role: string) {
  return api.patch<OrgMember>(`/organizations/${slug}/members/${userId}/`, { role })
}

export function removeOrgMember(slug: string, userId: number) {
  return api.delete<{ success: boolean }>(`/organizations/${slug}/members/${userId}/`)
}

export function deleteOrganization(slug: string) {
  return api.delete<{ success: boolean }>(`/organizations/${slug}/delete/`)
}

export async function register(data: RegisterData): Promise<RegisterResponse> {
  const response = await fetch(`${API_BASE}/auth/register/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => null)
    throw new ApiError(response.status, err)
  }
  const result = await response.json()
  setTokens(result.access, result.refresh)
  return result
}

// Superadmin API
export interface SuperAdminOrg extends Organization {
  stats?: { lead_count: number; member_count: number }
}

export function superAdminListOrgs() {
  return api.get<SuperAdminOrg[]>('/organizations/__superadmin/orgs/')
}

export function superAdminGetOrg(slug: string) {
  return api.get<SuperAdminOrg>(`/organizations/__superadmin/orgs/${slug}/`)
}

export function superAdminUpdateOrg(slug: string, data: Partial<Pick<Organization, 'plan' | 'is_active' | 'name'>>) {
  return api.patch<Organization>(`/organizations/__superadmin/orgs/${slug}/`, data)
}

export function superAdminImpersonate(userId: number) {
  return api.post<{ access: string; refresh: string; user_id: number; email: string }>(
    `/organizations/__superadmin/impersonate/${userId}/`, {}
  )
}
