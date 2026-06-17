// Settings page — Instagram integration + AI config + pipeline stages
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useRef, useCallback, useEffect } from 'react'
import { PlusIcon, PencilIcon, TrashIcon, GripVerticalIcon, PlugIcon, CheckCircleIcon, BrainCircuitIcon, SparklesIcon, Building2Icon, EyeIcon, EyeOffIcon, Loader2Icon, UsersIcon, BuildingIcon, CrownIcon, ShieldCheckIcon, UserCircleIcon, AlertTriangleIcon, PauseCircleIcon, PlayCircleIcon } from 'lucide-react'
import { ApiError } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  fetchPipelineStages,
  createPipelineStage,
  updatePipelineStage,
  deletePipelineStage,
  fetchSegments,
  createSegment,
  updateSegment,
  deleteSegment,
  fetchTelegramIntegrationStatus,
  saveTelegramToken,
  disconnectTelegram,
  fetchInstagramStatus,
  disconnectInstagram,
  saveInstagramAppCredentials,
  fetchWhatsAppIntegrationStatus,
  disconnectWhatsApp,
  connectWhatsAppManual,
  fetchAIConfig,
  updateAIConfig,
  runAgentNow,
  registerTelegramWebhook,
  fetchOrganizations,
  fetchOrgMembers,
  inviteOrgMember,
  updateOrgMemberRole,
  removeOrgMember,
  updateOrganization,
  deleteOrganization,
  type PipelineStage,
  type Segment,
  type UpdateAIConfigData,
} from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { toast } from 'sonner'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { useLanguage } from '@/contexts/language-context'
import { type Language } from '@/lib/translations'
import { useAuth } from '@/contexts/auth-context'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  buildLeadDiscoverySourcesOrgSettings,
  createLeadDiscoverySourceValue,
  getDefaultLeadDiscoverySourceOptions,
  getLeadDiscoverySourceOptions,
  type LeadDiscoverySourceOption,
} from '@/lib/org-settings'

const INSTAGRAM_OAUTH_RESULT_STORAGE_KEY = 'cayu.instagram.oauth.result'
const INSTAGRAM_OAUTH_RESULT_MAX_AGE_MS = 5 * 60 * 1000
const INSTAGRAM_OAUTH_RESULT_SYNC_RETRY_DELAY_MS = 1000
const INSTAGRAM_OAUTH_POPUP_CLOSE_GRACE_MS = 1500
const INSTAGRAM_POST_CLOSE_SYNC_TIMEOUT_MS = 20000

type InstagramConnectStage =
  | 'idle'
  | 'waiting_for_login'
  | 'authorization_in_progress'
  | 'connected'
  | 'failed'
  | 'cancelled'

type InstagramOAuthResult = {
  event?: 'instagram_connected' | 'instagram_error'
  instagram_username?: string
  error?: string
  created_at?: number
}

type InstagramSyncSource = 'popup_open' | 'popup_closed' | 'message' | 'storage' | 'visibility'

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const data = error.data
    if (data && typeof data === 'object') {
      const detail = (data as Record<string, unknown>).detail ?? (data as Record<string, unknown>).error
      if (typeof detail === 'string') return detail
      const firstValue = Object.values(data as Record<string, unknown>)[0]
      if (Array.isArray(firstValue) && typeof firstValue[0] === 'string') return firstValue[0]
    }
  }
  return fallback
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

// Settings page
export const Route = createFileRoute('/_app/settings')({
  validateSearch: (search: Record<string, unknown>) => ({
    tab: (search.tab as string) ?? 'general',
  }),
  component: SettingsPage,
})

function SettingsPage() {
  const navigate = useNavigate()
  const { tab } = Route.useSearch()
  const { language, setLanguage, t } = useLanguage()
  const [stageDialogOpen, setStageDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteDialogType, setDeleteDialogType] = useState<'stage' | 'segment'>('stage')
  const [editingStage, setEditingStage] = useState<PipelineStage | null>(null)
  const [deletingStageId, setDeletingStageId] = useState<number | null>(null)
  const [stageName, setStageName] = useState('')
  const [stageKey, setStageKey] = useState('')
  const [isKeyManuallyEdited, setIsKeyManuallyEdited] = useState(false)
  const [stageDescription, setStageDescription] = useState('')
  const [stageIsFinal, setStageIsFinal] = useState(false)
  // Segment CRUD state
  const [segmentDialogOpen, setSegmentDialogOpen] = useState(false)
  const [editingSegment, setEditingSegment] = useState<Segment | null>(null)
  const [deletingSegmentId, setDeletingSegmentId] = useState<number | null>(null)
  const [segmentName, setSegmentName] = useState('')
  const [segmentKey, setSegmentKey] = useState('')
  const [isSegmentKeyManuallyEdited, setIsSegmentKeyManuallyEdited] = useState(false)
  const [telegramToken, setTelegramToken] = useState('')
  const [isSavingToken, setIsSavingToken] = useState(false)
  const [webhookBaseUrl, setWebhookBaseUrl] = useState('')
  const [isDisconnectingInstagram, setIsDisconnectingInstagram] = useState(false)
  const [igAppId, setIgAppId] = useState('')
  const [igAppSecret, setIgAppSecret] = useState('')
  const [igVerifyToken, setIgVerifyToken] = useState('')
  const [showIgAppSecret, setShowIgAppSecret] = useState(false)
  const [isSavingInstagramCredentials, setIsSavingInstagramCredentials] = useState(false)
  // When the OAuth popup is open, poll status every 2s so the UI updates even
  // if postMessage fails (cross-origin iframe timing, CSP, or popup dismissed)
  const [isInstagramConnecting, setIsInstagramConnecting] = useState(false)
  const [instagramConnectStage, setInstagramConnectStage] = useState<InstagramConnectStage>('idle')
  const [instagramConnectionNotice, setInstagramConnectionNotice] = useState<string | null>(null)
  const instagramPopupCleanupRef = useRef<(() => void) | null>(null)
  const instagramOauthSyncInFlightRef = useRef(false)
  const instagramConnectStartedAtRef = useRef(0)
  const [waPhoneNumberId, setWaPhoneNumberId] = useState('')
  const [waWabaId, setWaWabaId] = useState('')
  const [waAccessToken, setWaAccessToken] = useState('')
  const [waAppId, setWaAppId] = useState('')
  const [waAppSecret, setWaAppSecret] = useState('')
  const [showWaToken, setShowWaToken] = useState(false)
  const [showWaAppSecret, setShowWaAppSecret] = useState(false)
  const [isConnectingWhatsApp, setIsConnectingWhatsApp] = useState(false)
  // Local state for large text fields to prevent cursor-jump on every keystroke
  const queryClient = useQueryClient()

  // Team + Org state
  const { user } = useAuth()
  const orgSlug = user?.current_organization_slug ?? ''
  const currentOrgRole = user?.current_organization_role
  const isOwnerOrAdmin = Boolean(user?.is_superadmin || user?.is_admin || currentOrgRole === 'owner' || currentOrgRole === 'admin')
  const isOwner = Boolean(user?.is_superadmin || currentOrgRole === 'owner')
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'member' | 'admin'>('member')
  const [inviteLoading, setInviteLoading] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [orgName, setOrgName] = useState('')
  const [orgNameSaving, setOrgNameSaving] = useState(false)
  const [leadDiscoverySources, setLeadDiscoverySources] = useState<LeadDiscoverySourceOption[]>(
    getDefaultLeadDiscoverySourceOptions,
  )
  const [discoverySourceName, setDiscoverySourceName] = useState('')
  const [editingDiscoverySourceValue, setEditingDiscoverySourceValue] = useState<string | null>(null)
  const [discoverySourceError, setDiscoverySourceError] = useState('')


  const { data: stages = [], isLoading } = useQuery({
    queryKey: ['pipeline-stages'],
    queryFn: fetchPipelineStages,
    enabled: isOwnerOrAdmin,
  })

  const { data: segments = [], isLoading: isLoadingSegments } = useQuery({
    queryKey: ['segments'],
    queryFn: fetchSegments,
    enabled: isOwnerOrAdmin,
  })

  const { data: telegramStatus } = useQuery({
    queryKey: ['telegram-integration-status'],
    queryFn: fetchTelegramIntegrationStatus,
    enabled: isOwnerOrAdmin,
  })

  const { data: instagramStatus, refetch: refetchInstagramStatus } = useQuery({
    queryKey: ['instagram-status', orgSlug],
    queryFn: fetchInstagramStatus,
    // Poll every 2s while the OAuth popup is open — guarantees the UI catches
    // the connected state even if postMessage/popup.closed detection fails
    // (cross-origin iframe timing or CSP can silently drop postMessage).
    // Stops automatically once isInstagramConnecting is false.
    refetchInterval: isInstagramConnecting ? 2000 : false,
    enabled: !!user && isOwnerOrAdmin,
  })

  useEffect(() => {
    if (instagramStatus?.app_id) {
      setIgAppId((current) => current || instagramStatus.app_id || '')
    }
    if (instagramStatus?.verify_token) {
      setIgVerifyToken((current) => current || instagramStatus.verify_token || '')
    }
  }, [instagramStatus?.app_id, instagramStatus?.verify_token])

  const clearInstagramOAuthResult = useCallback(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.removeItem(INSTAGRAM_OAUTH_RESULT_STORAGE_KEY)
  }, [])

  const consumeInstagramOAuthResult = useCallback((): InstagramOAuthResult | null => {
    if (typeof window === 'undefined') {
      return null
    }

    const raw = window.localStorage.getItem(INSTAGRAM_OAUTH_RESULT_STORAGE_KEY)
    if (!raw) {
      return null
    }

    window.localStorage.removeItem(INSTAGRAM_OAUTH_RESULT_STORAGE_KEY)

    try {
      const parsed = JSON.parse(raw) as InstagramOAuthResult
      if (!parsed.created_at || Date.now() - parsed.created_at > INSTAGRAM_OAUTH_RESULT_MAX_AGE_MS) {
        return null
      }
      if (parsed.created_at < instagramConnectStartedAtRef.current) {
        return null
      }
      return parsed
    } catch {
      return null
    }
  }, [])

  const updateInstagramConnectStage = useCallback((stage: InstagramConnectStage, message?: string | null) => {
    setInstagramConnectStage(stage)
    if (typeof message !== 'undefined') {
      setInstagramConnectionNotice(message)
    }
  }, [])

  const finishInstagramConnect = useCallback(() => {
    setIsInstagramConnecting(false)
    instagramPopupCleanupRef.current = null
  }, [])

  const syncInstagramStatusAfterOAuth = useCallback(async (
    result?: InstagramOAuthResult | null,
    source: InstagramSyncSource = 'visibility',
  ) => {
    if (instagramOauthSyncInFlightRef.current) {
      return false
    }

    instagramOauthSyncInFlightRef.current = true
    setIsInstagramConnecting(true)
    const syncStartedAt = Date.now()
    let latestStatusResponse: Awaited<ReturnType<typeof refetchInstagramStatus>> | null = null

    try {
      while (Date.now() - syncStartedAt < INSTAGRAM_POST_CLOSE_SYNC_TIMEOUT_MS) {
        latestStatusResponse = await refetchInstagramStatus()
        const latestAttemptStartedAt = latestStatusResponse.data?.oauth_last_started_at
          ? new Date(latestStatusResponse.data.oauth_last_started_at).getTime()
          : 0
        const isCurrentAttempt = latestAttemptStartedAt >= instagramConnectStartedAtRef.current - 2000
        const latestAttemptStatus = isCurrentAttempt ? latestStatusResponse.data?.oauth_last_status : ''
        const latestAttemptError = isCurrentAttempt ? latestStatusResponse.data?.oauth_last_error : ''
        const callbackReached = isCurrentAttempt && Boolean(latestStatusResponse.data?.oauth_last_callback_at)

        if (latestStatusResponse.data?.connected) {
          updateInstagramConnectStage('connected', null)
          toast.success(
            latestStatusResponse.data.instagram_username
              ? `\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d @${latestStatusResponse.data.instagram_username}`
              : 'Instagram connected',
          )
          finishInstagramConnect()
          return true
        }

        if (latestAttemptStatus === 'error' && latestAttemptError) {
          const exactReason = latestAttemptError
          updateInstagramConnectStage('failed', exactReason)
          toast.error(exactReason)
          finishInstagramConnect()
          return false
        }

        if (source === 'popup_open') {
          updateInstagramConnectStage(
            'waiting_for_login',
            'Instagram sign-in is still open. Finish logging in and approve access in the Instagram window.',
          )
        } else {
          const statusForAttempt = latestAttemptStatus === 'pending'

          if (callbackReached || result?.event === 'instagram_connected') {
            updateInstagramConnectStage(
              'authorization_in_progress',
              'Instagram approved the request. Saving the connection and waiting for the CRM to confirm it.',
            )
          } else if (statusForAttempt) {
            updateInstagramConnectStage(
              'authorization_in_progress',
              'The Instagram window closed, but the authorization is still being checked. Please wait a few seconds for confirmation.',
            )
          } else {
            updateInstagramConnectStage(
              'authorization_in_progress',
              'Checking whether the Instagram authorization finished successfully…',
            )
          }
        }

        await wait(INSTAGRAM_OAUTH_RESULT_SYNC_RETRY_DELAY_MS)
      }

      const latestAttemptStartedAt = latestStatusResponse?.data?.oauth_last_started_at
        ? new Date(latestStatusResponse.data.oauth_last_started_at).getTime()
        : 0
      const isCurrentAttempt = latestAttemptStartedAt >= instagramConnectStartedAtRef.current - 2000
      const callbackReached = isCurrentAttempt && Boolean(latestStatusResponse?.data?.oauth_last_callback_at)
      const fallbackMessage = result?.error
        || latestStatusResponse?.data?.callback_warning
        || (isCurrentAttempt ? latestStatusResponse?.data?.oauth_last_error : '')
        || (source === 'popup_closed' && !callbackReached
          ? 'The Instagram window was closed before authorization finished, so no connection was saved. Reopen Connect Instagram and complete the login and Allow steps.'
          : result?.event === 'instagram_connected'
            ? 'Instagram approved the request, but the CRM could not confirm the saved connection. Please try again and complete the approval in one session.'
            : 'Instagram authorization did not complete. Please try again.')

      updateInstagramConnectStage(
        source === 'popup_closed' && !callbackReached ? 'cancelled' : 'failed',
        fallbackMessage,
      )
      toast.error(fallbackMessage)
      finishInstagramConnect()
      return false
    } finally {
      instagramOauthSyncInFlightRef.current = false
    }
  }, [finishInstagramConnect, refetchInstagramStatus, updateInstagramConnectStage])

  useEffect(() => {
    if (instagramStatus?.connected) {
      updateInstagramConnectStage('connected', null)
    } else if (!isInstagramConnecting && instagramConnectStage === 'connected') {
      updateInstagramConnectStage('idle')
    }
  }, [instagramConnectStage, instagramStatus?.connected, isInstagramConnecting, updateInstagramConnectStage])

  useEffect(() => {
    if (!isInstagramConnecting) {
      return
    }

    const refreshInstagramStatus = () => {
      if (document.visibilityState === 'visible') {
        const oauthResult = consumeInstagramOAuthResult()
        if (oauthResult) {
          void syncInstagramStatusAfterOAuth(oauthResult, 'visibility')
          return
        }
        void queryClient.refetchQueries({ queryKey: ['instagram-status', orgSlug] })
      }
    }

    window.addEventListener('focus', refreshInstagramStatus)
    document.addEventListener('visibilitychange', refreshInstagramStatus)

    return () => {
      window.removeEventListener('focus', refreshInstagramStatus)
      document.removeEventListener('visibilitychange', refreshInstagramStatus)
    }
  }, [consumeInstagramOAuthResult, isInstagramConnecting, orgSlug, queryClient, syncInstagramStatusAfterOAuth])

  useEffect(() => {
    if (!isInstagramConnecting) {
      return
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.key !== INSTAGRAM_OAUTH_RESULT_STORAGE_KEY || !event.newValue) {
        return
      }

      const oauthResult = consumeInstagramOAuthResult()
      if (!oauthResult) {
        return
      }

      if (oauthResult.event === 'instagram_error') {
        const message = oauthResult.error || 'Instagram authorization failed.'
        updateInstagramConnectStage('failed', message)
        toast.error(message)
        finishInstagramConnect()
        return
      }

      void syncInstagramStatusAfterOAuth(oauthResult, 'storage')
    }

    window.addEventListener('storage', handleStorage)

    return () => {
      window.removeEventListener('storage', handleStorage)
    }
  }, [consumeInstagramOAuthResult, finishInstagramConnect, isInstagramConnecting, syncInstagramStatusAfterOAuth, updateInstagramConnectStage])

  useEffect(() => {
    const oauthResult = consumeInstagramOAuthResult()
    if (!oauthResult) {
      return
    }

    if (oauthResult.event === 'instagram_error') {
      const message = oauthResult.error || 'Instagram authorization failed.'
      updateInstagramConnectStage('failed', message)
      toast.error(message)
      finishInstagramConnect()
      return
    }

    void syncInstagramStatusAfterOAuth(oauthResult, 'storage')
  }, [consumeInstagramOAuthResult, finishInstagramConnect, syncInstagramStatusAfterOAuth, updateInstagramConnectStage])

  const { data: whatsappStatus } = useQuery({
    queryKey: ['whatsapp-integration-status'],
    queryFn: fetchWhatsAppIntegrationStatus,
    enabled: isOwnerOrAdmin,
  })


  const { data: aiConfig } = useQuery({
    queryKey: ['ai-config'],
    queryFn: fetchAIConfig,
    enabled: isOwnerOrAdmin,
  })

  const updateAIConfigMutation = useMutation({
    mutationFn: updateAIConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-config'] })
      toast.success('Настройки AI обновлены')
    },
    onError: () => {
      toast.error('Не удалось обновить настройки AI')
    },
  })

  const handleAIConfigChange = (data: UpdateAIConfigData) => {
    updateAIConfigMutation.mutate(data)
  }

  const renderChannelAiControl = (
    channelKey: 'telegram_ai_paused' | 'instagram_ai_paused' | 'whatsapp_ai_paused',
    channelLabel: 'Telegram' | 'Instagram' | 'WhatsApp',
  ) => {
    const isPaused = aiConfig?.[channelKey] ?? false
    const isUpdatingThisChannel = updateAIConfigMutation.isPending && channelKey in (updateAIConfigMutation.variables ?? {})

    return (
      <div className={`rounded-xl border p-4 ${isPaused ? 'border-amber-300 bg-amber-50/80 dark:border-amber-800 dark:bg-amber-950/20' : 'border-emerald-200 bg-emerald-50/70 dark:border-emerald-900 dark:bg-emerald-950/20'}`}>
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">Управление ИИ-ответами</span>
              <Badge className={isPaused ? 'bg-amber-500 text-white hover:bg-amber-500' : 'bg-emerald-600 text-white hover:bg-emerald-600'}>
                {isPaused ? (
                  <><AlertTriangleIcon className="mr-1 h-3 w-3" />На паузе</>
                ) : (
                  <><CheckCircleIcon className="mr-1 h-3 w-3" />Активен</>
                )}
              </Badge>
            </div>
            <p className={`text-sm ${isPaused ? 'text-amber-900 dark:text-amber-100' : 'text-emerald-900 dark:text-emerald-100'}`}>
              {isPaused
                ? `${channelLabel}: ИИ не отправляет ответы и не запускает активные автоматизации, пока вы не включите канал.`
                : `${channelLabel}: AI отвечает и запускает автоматизации для подходящих диалогов.`}
            </p>
            <p className="text-xs text-muted-foreground">
              Сообщения команды продолжают отправляться вручную даже при паузе AI.
            </p>
          </div>
          <Button
            type="button"
            variant={isPaused ? 'default' : 'outline'}
            className={isPaused ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'border-amber-300 text-amber-800 hover:bg-amber-50 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-950/30'}
            disabled={isUpdatingThisChannel}
            onClick={() => handleAIConfigChange({ [channelKey]: !isPaused })}
          >
            {isUpdatingThisChannel ? (
              <><Loader2Icon className="mr-2 h-4 w-4 animate-spin" />Обновление...</>
            ) : isPaused ? (
              <><PlayCircleIcon className="mr-2 h-4 w-4" />Включить AI</>
            ) : (
              <><PauseCircleIcon className="mr-2 h-4 w-4" />Поставить на паузу</>
            )}
          </Button>
        </div>
      </div>
    )
  }

  // Team + Org queries
  const { data: orgMembers = [], isLoading: membersLoading } = useQuery({
    queryKey: ['org-members', orgSlug],
    queryFn: () => fetchOrgMembers(orgSlug),
    enabled: !!orgSlug && isOwnerOrAdmin,
  })

  const { data: orgs = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: fetchOrganizations,
    enabled: !!user,
  })
  const currentOrg = orgs.find(o => o.slug === orgSlug)

  useEffect(() => {
    if (currentOrg?.name) setOrgName(currentOrg.name)
  }, [currentOrg?.name])

  useEffect(() => {
    setLeadDiscoverySources(getLeadDiscoverySourceOptions(currentOrg?.org_settings))
  }, [currentOrg?.org_settings])

  const activeTab = !isOwnerOrAdmin
    ? 'preferences'
    : tab === 'team'
      ? 'general'
    : tab === 'dev-database-export'
      ? 'general'
      : tab

  const updateLeadDiscoverySourcesMutation = useMutation({
    mutationFn: async (nextSources: LeadDiscoverySourceOption[]) => {
      if (!orgSlug) {
        throw new Error('Organization is required')
      }

      return updateOrganization(orgSlug, {
        org_settings: buildLeadDiscoverySourcesOrgSettings(currentOrg?.org_settings, nextSources),
      })
    },
    onSuccess: (updatedOrganization) => {
      queryClient.setQueryData(['organizations'], (existing: typeof orgs | undefined) => {
        if (!existing) {
          return [updatedOrganization]
        }

        const nextOrganizations = existing.map((organization) => (
          organization.slug === updatedOrganization.slug ? updatedOrganization : organization
        ))
        return nextOrganizations.some((organization) => organization.slug === updatedOrganization.slug)
          ? nextOrganizations
          : [...nextOrganizations, updatedOrganization]
      })
      setLeadDiscoverySources(getLeadDiscoverySourceOptions(updatedOrganization.org_settings))
      setDiscoverySourceError('')
      toast.success('Источники лидов сохранены')
    },
    onError: (error) => {
      const message = getApiErrorMessage(error, 'Не удалось сохранить источники лидов')
      setLeadDiscoverySources(getLeadDiscoverySourceOptions(currentOrg?.org_settings))
      setDiscoverySourceError(message)
      toast.error(message)
    },
  })

  const handleInvite = async () => {
    if (!inviteEmail || !orgSlug) return
    setInviteLoading(true)
    setInviteError('')
    try {
      await inviteOrgMember(orgSlug, { email: inviteEmail, role: inviteRole })
      await queryClient.invalidateQueries({ queryKey: ['org-members', orgSlug] })
      setInviteOpen(false)
      setInviteEmail('')
      setInviteRole('member')
    } catch (e: unknown) {
      const err = e as { data?: { error?: string } }
      setInviteError(err?.data?.error || 'Не удалось пригласить участника')
    } finally {
      setInviteLoading(false)
    }
  }

  const handleRoleChange = async (userId: number, role: string) => {
    if (!orgSlug) return
    await updateOrgMemberRole(orgSlug, userId, role)
    queryClient.invalidateQueries({ queryKey: ['org-members', orgSlug] })
  }

  const handleRemoveMember = async (userId: number) => {
    if (!orgSlug) return
    await removeOrgMember(orgSlug, userId)
    queryClient.invalidateQueries({ queryKey: ['org-members', orgSlug] })
  }

  const handleSaveOrgName = async () => {
    if (!orgSlug || !orgName.trim()) return
    setOrgNameSaving(true)
    try {
      await updateOrganization(orgSlug, { name: orgName })
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
    } finally {
      setOrgNameSaving(false)
    }
  }

  const handleDeleteOrg = async () => {
    if (!orgSlug) return
    await deleteOrganization(orgSlug)
    navigate({ to: '/login' })
  }

  const saveLeadDiscoverySources = (nextSources: LeadDiscoverySourceOption[]) => {
    setLeadDiscoverySources(nextSources)
    updateLeadDiscoverySourcesMutation.mutate(nextSources)
  }

  const handleSaveDiscoverySource = () => {
    const label = discoverySourceName.trim()
    setDiscoverySourceError('')
    if (!label) {
      const message = 'Введите название источника'
      setDiscoverySourceError(message)
      toast.error(message)
      return
    }

    if (editingDiscoverySourceValue) {
      saveLeadDiscoverySources(
        leadDiscoverySources.map((source) => (
          source.value === editingDiscoverySourceValue ? { ...source, label } : source
        )),
      )
    } else {
      const value = createLeadDiscoverySourceValue(label, leadDiscoverySources)
      saveLeadDiscoverySources([...leadDiscoverySources, { value, label }])
    }

    setDiscoverySourceName('')
    setEditingDiscoverySourceValue(null)
  }

  const handleEditDiscoverySource = (source: LeadDiscoverySourceOption) => {
    setDiscoverySourceName(source.label)
    setEditingDiscoverySourceValue(source.value)
  }

  const handleDeleteDiscoverySource = (sourceValue: string) => {
    const nextSources = leadDiscoverySources.filter((source) => source.value !== sourceValue)
    if (nextSources.length === 0) {
      toast.error('Оставьте хотя бы один источник')
      return
    }
    saveLeadDiscoverySources(nextSources)
    setDiscoverySourceError('')
    if (editingDiscoverySourceValue === sourceValue) {
      setDiscoverySourceName('')
      setEditingDiscoverySourceValue(null)
    }
  }

  const handleResetDiscoverySources = () => {
    setDiscoverySourceName('')
    setEditingDiscoverySourceValue(null)
    setDiscoverySourceError('')
    saveLeadDiscoverySources(getDefaultLeadDiscoverySourceOptions())
  }

  function RoleBadge({ role }: { role: string }) {
    const config: Record<string, { icon: import('react').ReactNode; label: string; className: string }> = {
      owner: { icon: <CrownIcon className="h-3 w-3" />, label: 'Владелец', className: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' },
      admin: { icon: <ShieldCheckIcon className="h-3 w-3" />, label: 'Администратор', className: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' },
      member: { icon: <UserCircleIcon className="h-3 w-3" />, label: 'Участник', className: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300' },
    }
    const c = config[role] || config.member
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${c.className}`}>
        {c.icon}{c.label}
      </span>
    )
  }

  const createMutation = useMutation({
    mutationFn: createPipelineStage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-stages'] })
      toast.success('Этап воронки создан')
      handleCloseStageDialog()
    },
    onError: () => {
      toast.error('Не удалось создать этап воронки')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { name?: string; key?: string; description?: string; is_final?: boolean } }) =>
      updatePipelineStage(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-stages'] })
      toast.success('Этап воронки обновлен')
      handleCloseStageDialog()
    },
    onError: () => {
      toast.error('Не удалось обновить этап воронки')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deletePipelineStage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-stages'] })
      toast.success('Этап воронки удален')
    },
    onError: () => {
      toast.error('Не удалось удалить этап воронки')
    },
  })

  // Segment mutations
  const createSegmentMutation = useMutation({
    mutationFn: createSegment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] })
      toast.success('Сегмент создан')
      handleCloseSegmentDialog()
    },
    onError: () => {
      toast.error('Не удалось создать сегмент')
    },
  })

  const updateSegmentMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { name?: string; key?: string; order?: number } }) =>
      updateSegment(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] })
      toast.success('Сегмент обновлен')
      handleCloseSegmentDialog()
    },
    onError: () => {
      toast.error('Не удалось обновить сегмент')
    },
  })

  const deleteSegmentMutation = useMutation({
    mutationFn: deleteSegment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] })
      toast.success('Сегмент удален')
    },
    onError: () => {
      toast.error('Не удалось удалить сегмент')
    },
  })

  const slugify = (value: string) =>
    value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')

  const handleAddStage = () => {
    setEditingStage(null)
    setStageName('')
    setStageKey('')
    setIsKeyManuallyEdited(false)
    setStageDescription('')
    setStageIsFinal(false)
    setStageDialogOpen(true)
  }

  const handleEditStage = (stage: PipelineStage) => {
    setEditingStage(stage)
    setStageName(stage.name)
    setStageKey(stage.key)
    setStageDescription(stage.description)
    setStageIsFinal(stage.is_final)
    setStageDialogOpen(true)
  }

  const handleCloseStageDialog = () => {
    setStageDialogOpen(false)
    setEditingStage(null)
    setStageName('')
    setStageKey('')
    setIsKeyManuallyEdited(false)
    setStageDescription('')
    setStageIsFinal(false)
  }

  const handleSaveStage = () => {
    if (!stageName.trim() || !stageKey.trim()) {
      toast.error('Имя и ключ обязательны')
      return
    }

    if (editingStage) {
      updateMutation.mutate({
        id: editingStage.id,
        data: {
          name: stageName,
          key: stageKey,
          description: stageDescription,
          is_final: stageIsFinal,
        },
      })
    } else {
      createMutation.mutate({
        name: stageName,
        key: stageKey,
        description: stageDescription,
        order: stages.length + 1,
        is_final: stageIsFinal,
      })
    }
  }

  const handleDeleteStage = (id: number) => {
    setDeletingStageId(id)
    setDeleteDialogType('stage')
    setDeleteDialogOpen(true)
  }

  const confirmDelete = () => {
    if (deleteDialogType === 'stage' && deletingStageId !== null) {
      deleteMutation.mutate(deletingStageId)
    } else if (deleteDialogType === 'segment' && deletingSegmentId !== null) {
      deleteSegmentMutation.mutate(deletingSegmentId)
    }
    setDeleteDialogOpen(false)
    setDeletingStageId(null)
    setDeletingSegmentId(null)
  }

  // Segment handlers
  const handleAddSegment = () => {
    setEditingSegment(null)
    setSegmentName('')
    setSegmentKey('')
    setIsSegmentKeyManuallyEdited(false)
    setSegmentDialogOpen(true)
  }

  const handleEditSegment = (segment: Segment) => {
    setEditingSegment(segment)
    setSegmentName(segment.name)
    setSegmentKey(segment.key)
    setSegmentDialogOpen(true)
  }

  const handleCloseSegmentDialog = () => {
    setSegmentDialogOpen(false)
    setEditingSegment(null)
    setSegmentName('')
    setSegmentKey('')
    setIsSegmentKeyManuallyEdited(false)
  }

  const handleSaveSegment = () => {
    if (!segmentName.trim() || !segmentKey.trim()) {
      toast.error('Имя и ключ обязательны')
      return
    }

    if (editingSegment) {
      updateSegmentMutation.mutate({
        id: editingSegment.id,
        data: { name: segmentName, key: segmentKey },
      })
    } else {
      createSegmentMutation.mutate({
        name: segmentName,
        key: segmentKey,
        order: segments.length + 1,
      })
    }
  }

  const handleDeleteSegment = (id: number) => {
    setDeletingSegmentId(id)
    setDeleteDialogType('segment')
    setDeleteDialogOpen(true)
  }

  const handleSaveTelegramToken = async () => {
    if (!telegramToken.trim()) {
      toast.error('Пожалуйста, введите токен бота')
      return
    }

    setIsSavingToken(true)
    try {
      const response = await saveTelegramToken(telegramToken)
      if (response.success) {
        toast.success(`Bot connected: @${response.bot_username}`)
        setTelegramToken('')
        queryClient.invalidateQueries({ queryKey: ['telegram-integration-status'] })
      } else {
        toast.error(response.error || 'Failed to save bot token')
      }
    } catch (error) {
      if (error instanceof ApiError) {
        const errorData = error.data as any
        toast.error(errorData?.error || 'Failed to save bot token. Please try again.')
      } else {
        toast.error('Не удалось сохранить токен бота. Пожалуйста, попробуйте снова.')
      }
    } finally {
      setIsSavingToken(false)
    }
  }

  const handleDisconnectTelegram = async () => {
    try {
      const response = await disconnectTelegram()
      if (response.success) {
        toast.success('Бот Telegram отключен')
        queryClient.invalidateQueries({ queryKey: ['telegram-integration-status'] })
      } else {
        toast.error(response.error || 'Failed to disconnect')
      }
    } catch (error) {
      toast.error('Не удалось отключиться. Пожалуйста, попробуйте снова.')
    }
  }

  const handleSaveInstagramCredentials = async () => {
    if (!igAppId.trim()) {
      toast.error('Введите App ID приложения Meta')
      return
    }
    if (!igAppSecret.trim() && !instagramStatus?.app_secret_set) {
      toast.error('Введите App Secret приложения Meta')
      return
    }

    setIsSavingInstagramCredentials(true)
    try {
      await saveInstagramAppCredentials({
        app_id: igAppId.trim(),
        app_secret: igAppSecret.trim(),
        webhook_verify_token: igVerifyToken.trim() || undefined,
      })
      toast.success('Данные приложения Meta сохранены')
      setIgAppSecret('')
      await refetchInstagramStatus()
    } catch (error: any) {
      const message = error?.data?.error ?? error?.message ?? 'Не удалось сохранить данные приложения Meta'
      toast.error(message)
    } finally {
      setIsSavingInstagramCredentials(false)
    }
  }

  const handleConnectInstagram = useCallback(() => {
    if (!instagramStatus?.app_id) {
      toast.error('Сначала сохраните App ID приложения Meta')
      updateInstagramConnectStage('failed', 'Meta App ID is missing. Save your Instagram app credentials first.')
      return
    }
    if (!instagramStatus?.app_secret_set) {
      toast.error('Сначала сохраните App Secret приложения Meta')
      updateInstagramConnectStage('failed', 'Meta App Secret is missing. Save your Instagram app credentials first.')
      return
    }

    // Clean up any previous popup/listeners before opening a new one
    if (instagramPopupCleanupRef.current) {
      instagramPopupCleanupRef.current()
      instagramPopupCleanupRef.current = null
    }

    const authorizeUrl = instagramStatus?.embed_url
    if (!authorizeUrl) {
      toast.error('Настройка Instagram все еще загружается. Пожалуйста, подождите.')
      updateInstagramConnectStage('failed', 'Instagram setup is still loading. Please wait a moment and try again.')
      return
    }

    updateInstagramConnectStage(
      'waiting_for_login',
      'Instagram sign-in is ready. Complete login and approval in the popup window to finish connecting this account.',
    )
    instagramOauthSyncInFlightRef.current = false
    instagramConnectStartedAtRef.current = Date.now()
    clearInstagramOAuthResult()

    const popup = window.open(authorizeUrl, 'instagram_connect', 'width=600,height=700,scrollbars=yes')
    if (!popup) {
      toast.error('Всплывающее окно заблокировано. Пожалуйста, разрешите всплывающие окна для этого сайта.')
      updateInstagramConnectStage('failed', 'The Instagram window was blocked by your browser. Allow popups for this page and try again.')
      return
    }

    // Start polling — refetchInterval activates now
    setIsInstagramConnecting(true)

    const readResult = () => consumeInstagramOAuthResult()

    // Poll every 500ms: if popup closed without sending a message, continue syncing
    // because Meta can close the window before the parent receives postMessage.
    const pollInterval = setInterval(() => {
      if (popup.closed) {
        clearInterval(pollInterval)
        window.removeEventListener('message', handler)
        updateInstagramConnectStage(
          'authorization_in_progress',
          'Instagram window closed. Checking whether the authorization completed or was cancelled…',
        )
        window.setTimeout(() => {
          void syncInstagramStatusAfterOAuth(readResult(), 'popup_closed')
        }, INSTAGRAM_OAUTH_POPUP_CLOSE_GRACE_MS)
      }
    }, 500)

    const handler = (event: MessageEvent) => {
      if (event.data?.event === 'instagram_connected') {
        clearInterval(pollInterval)
        window.removeEventListener('message', handler)
        void queryClient.refetchQueries({ queryKey: ['instagram-status', orgSlug] })
        updateInstagramConnectStage(
          'authorization_in_progress',
          'Instagram approved the request. Finalizing the connection in the CRM…',
        )
        popup.close()
        void syncInstagramStatusAfterOAuth({
          event: 'instagram_connected',
          instagram_username: event.data.instagram_username,
          created_at: event.data.created_at ?? Date.now(),
        }, 'message')
      } else if (event.data?.event === 'instagram_error') {
        clearInterval(pollInterval)
        window.removeEventListener('message', handler)
        const message = event.data.error || 'Failed to connect Instagram'
        updateInstagramConnectStage('failed', message)
        toast.error(message)
        finishInstagramConnect()
        popup.close()
      }
    }
    window.addEventListener('message', handler)

    // Store cleanup so re-clicking Connect tears down the old popup
    instagramPopupCleanupRef.current = () => {
      clearInterval(pollInterval)
      window.removeEventListener('message', handler)
      finishInstagramConnect()
      popup.close()
    }
  }, [clearInstagramOAuthResult, consumeInstagramOAuthResult, finishInstagramConnect, instagramStatus?.app_id, instagramStatus?.app_secret_set, instagramStatus?.embed_url, orgSlug, queryClient, syncInstagramStatusAfterOAuth, updateInstagramConnectStage])

  const handleDisconnectInstagram = async () => {
    setIsDisconnectingInstagram(true)
    try {
      await disconnectInstagram()
      toast.success('Instagram отключен')
      updateInstagramConnectStage('idle', null)
      refetchInstagramStatus()
    } catch {
      toast.error('Не удалось отключиться. Пожалуйста, попробуйте снова.')
    } finally {
      setIsDisconnectingInstagram(false)
    }
  }

  const handleConnectWhatsApp = async () => {
    if (!waPhoneNumberId.trim() || !waWabaId.trim() || !waAccessToken.trim() ) {
      toast.error('Все три поля обязательны')
      return
    }
    setIsConnectingWhatsApp(true)
    try {
      const result = await connectWhatsAppManual({
        phone_number_id: waPhoneNumberId.trim(),
        waba_id: waWabaId.trim(),
        access_token: waAccessToken.trim(),
        app_id: waAppId.trim() || undefined,
        app_secret: waAppSecret.trim() || undefined,
      })
      toast.success(`\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d ${result.display_phone_number ?? result.verified_name ?? 'WhatsApp'}`)
      setWaPhoneNumberId('')
      setWaWabaId('')
      setWaAccessToken('')
      setWaAppId('')
      setWaAppSecret('')
      queryClient.invalidateQueries({ queryKey: ['whatsapp-integration-status'] })
    } catch (e: any) {
      const msg = e?.data?.error ?? e?.message ?? 'Connection failed. Please check your credentials.'
      toast.error(msg)
    } finally {
      setIsConnectingWhatsApp(false)
    }
  }


  const handleDisconnectWhatsApp = async () => {
    try {
      await disconnectWhatsApp()
      toast.success('WhatsApp отключен')
      queryClient.invalidateQueries({ queryKey: ['whatsapp-integration-status'] })
    } catch {
      toast.error('Не удалось отключиться. Пожалуйста, попробуйте снова.')
    }
  }

  const instagramStatusBadge = instagramStatus?.connected
    ? instagramStatus.token_expired
      ? { label: 'Токен истек', variant: 'destructive' as const, className: '' }
      : { label: 'Подключено', variant: 'default' as const, className: 'bg-green-600 hover:bg-green-700' }
    : isInstagramConnecting || instagramConnectStage === 'waiting_for_login' || instagramConnectStage === 'authorization_in_progress'
      ? { label: instagramConnectStage === 'waiting_for_login' ? 'Ожидание подтверждения' : 'Авторизация', variant: 'secondary' as const, className: 'bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-900/40 dark:text-amber-100' }
      : { label: 'Не подключено', variant: 'secondary' as const, className: '' }

  const instagramCredentialsReady = Boolean(instagramStatus?.app_id && instagramStatus?.app_secret_set)

  const instagramConnectButtonLabel = instagramConnectStage === 'waiting_for_login'
    ? 'Ожидание Instagram...'
    : instagramConnectStage === 'authorization_in_progress'
      ? 'Завершение подключения...'
      : 'Подключить Instagram'

  const instagramProgressTone = instagramConnectStage === 'failed' || instagramConnectStage === 'cancelled'
    ? 'border-destructive/30 bg-destructive/10 text-destructive'
    : instagramConnectStage === 'connected'
      ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-100'
      : 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100'

  const instagramProgressTitle = instagramConnectStage === 'waiting_for_login'
    ? 'Ожидание входа в Instagram и согласия'
    : instagramConnectStage === 'authorization_in_progress'
      ? 'Выполняется авторизация'
      : instagramConnectStage === 'failed'
        ? 'Ошибка подключения'
        : instagramConnectStage === 'cancelled'
          ? 'Подключение отменено'
          : instagramConnectStage === 'connected'
            ? 'Instagram подключен'
            : null

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
          <div className="px-4 lg:px-6">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold">{t('settings.title')}</h1>
              <p className="text-sm text-muted-foreground">
                {t('settings.subtitle')}
              </p>
            </div>
          </div>

          <div className="px-4 lg:px-6">
            <Tabs value={activeTab} onValueChange={(t) => navigate({ to: '/settings', search: { tab: t } })} className="space-y-6">
              <TabsList>
                {isOwnerOrAdmin && (
                  <>
                    <TabsTrigger value="general">{t('settings.tabs.general')}</TabsTrigger>
                    <TabsTrigger value="integrations">
                      <PlugIcon className="h-4 w-4 mr-2" />
                      {t('settings.tabs.integrations')}
                    </TabsTrigger>
                    <TabsTrigger value="ai-support">
                      <BrainCircuitIcon className="h-4 w-4 mr-2" />
                      {t('settings.tabs.aiAgent')}
                    </TabsTrigger>
                  </>
                )}
                <TabsTrigger value="preferences">
                  {t('settings.tabs.preferences')}
                </TabsTrigger>
                {isOwnerOrAdmin && (
                  <>
                    <TabsTrigger value="organization">Организация</TabsTrigger>
                  </>
                )}
              </TabsList>

              <TabsContent value="general" className="space-y-6">
                <div className="grid gap-6 max-w-4xl">
                  <Card>
                    <CardHeader>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <CardTitle>Этапы воронки</CardTitle>
                          <CardDescription>
                            Определите этапы, через которые проходят лиды в вашей воронке продаж
                          </CardDescription>
                        </div>
                        <Button onClick={handleAddStage} size="sm" className="w-full sm:w-auto">
                          <PlusIcon className="h-4 w-4" />
                          Добавить этап
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {isLoading ? (
                        <p className="text-sm text-muted-foreground">Загрузка...</p>
                      ) : stages.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-8">Этапы воронки еще не настроены.</p>
                      ) : (
                        <div className="space-y-2">
                          {stages.map((stage) => (
                            <div
                              key={stage.id}
                              className="flex items-center gap-2 sm:gap-3 p-3 rounded-md bg-muted/50"
                            >
                              <GripVerticalIcon className="h-4 w-4 text-muted-foreground hidden sm:block" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-sm sm:text-base">{stage.name}</span>
                                  {stage.is_final && (
                                    <Badge variant="secondary" className="text-xs">Финальный</Badge>
                                  )}
                                </div>
                                <div className="text-xs sm:text-sm text-muted-foreground truncate">
                                  {stage.description}
                                </div>
                              </div>
                              <div className="flex gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleEditStage(stage)}
                                  aria-label="Edit"
                                >
                                  <PencilIcon className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeleteStage(stage.id)}
                                  aria-label="Delete"
                                >
                                  <TrashIcon className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <CardTitle>Сегменты лидов</CardTitle>
                          <CardDescription>
                            Определите категории типов клиентов для ваших лидов (например, Индивидуальный, Бизнес)
                          </CardDescription>
                        </div>
                        <Button onClick={handleAddSegment} size="sm" className="w-full sm:w-auto">
                          <PlusIcon className="h-4 w-4" />
                          Добавить сегмент
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {isLoadingSegments ? (
                        <p className="text-sm text-muted-foreground">Загрузка...</p>
                      ) : segments.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-8">Сегменты еще не настроены.</p>
                      ) : (
                        <div className="space-y-2">
                          {segments.map((segment) => (
                            <div
                              key={segment.id}
                              className="flex items-center gap-2 sm:gap-3 p-3 rounded-md bg-muted/50"
                            >
                              <GripVerticalIcon className="h-4 w-4 text-muted-foreground hidden sm:block" />
                              <div className="flex-1 min-w-0">
                                <span className="font-medium text-sm sm:text-base">{segment.name}</span>
                                <span className="ml-2 text-xs text-muted-foreground">({segment.key})</span>
                              </div>
                              <div className="flex gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleEditSegment(segment)}
                                  aria-label="Edit"
                                >
                                  <PencilIcon className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeleteSegment(segment.id)}
                                  aria-label="Delete"
                                >
                                  <TrashIcon className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Источники “Откуда узнал”</CardTitle>
                      <CardDescription>
                        Настройте варианты, которые менеджеры выбирают в карточке лида и фильтрах.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Input
                          value={discoverySourceName}
                          onChange={(event) => {
                            setDiscoverySourceName(event.target.value)
                            setDiscoverySourceError('')
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault()
                              handleSaveDiscoverySource()
                            }
                          }}
                          placeholder="Например: TikTok, 2ГИС, блогер, рекомендация партнера"
                          disabled={updateLeadDiscoverySourcesMutation.isPending}
                        />
                        <div className="flex gap-2">
                          <Button
                            onClick={handleSaveDiscoverySource}
                            disabled={updateLeadDiscoverySourcesMutation.isPending}
                            className="shrink-0"
                          >
                            {updateLeadDiscoverySourcesMutation.isPending
                              ? 'Сохраняем...'
                              : editingDiscoverySourceValue ? 'Сохранить' : 'Добавить'}
                          </Button>
                          {editingDiscoverySourceValue ? (
                            <Button
                              variant="outline"
                              onClick={() => {
                                setDiscoverySourceName('')
                                setEditingDiscoverySourceValue(null)
                              }}
                              disabled={updateLeadDiscoverySourcesMutation.isPending}
                            >
                              Отмена
                            </Button>
                          ) : null}
                        </div>
                      </div>
                      {discoverySourceError ? (
                        <p className="text-sm text-destructive">{discoverySourceError}</p>
                      ) : null}

                      <div className="space-y-2">
                        {leadDiscoverySources.map((source) => (
                          <div key={source.value} className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
                            <div className="min-w-0 flex-1">
                              <span className="font-medium text-sm">{source.label}</span>
                              <span className="ml-2 text-xs text-muted-foreground">({source.value})</span>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleEditDiscoverySource(source)}
                              disabled={updateLeadDiscoverySourcesMutation.isPending}
                              aria-label="Редактировать источник"
                            >
                              <PencilIcon className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteDiscoverySource(source.value)}
                              disabled={updateLeadDiscoverySourcesMutation.isPending}
                              aria-label="Удалить источник"
                            >
                              <TrashIcon className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleResetDiscoverySources}
                        disabled={updateLeadDiscoverySourcesMutation.isPending}
                      >
                        Вернуть стандартный список
                      </Button>
                    </CardContent>
                  </Card>

                </div>
              </TabsContent>

              <TabsContent value="integrations" className="space-y-6">
                <div className="grid gap-6 max-w-4xl">
                  <Card>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-4">
                          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500">
                            <svg className="h-7 w-7 text-white" viewBox="0 0 24 24" fill="currentColor">
                              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                            </svg>
                          </div>
                          <div>
                            <h3 className="font-semibold text-lg">Telegram</h3>
                            <p className="text-sm text-muted-foreground">
                              Отправляйте и получайте сообщения через Telegram-бота
                            </p>
                          </div>
                        </div>
                        {telegramStatus?.configured ? (
                          <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                            <CheckCircleIcon className="h-3 w-3 mr-1" />
                            Подключено
                          </Badge>
                        ) : (
                          <Badge variant="secondary">Не подключено</Badge>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {telegramStatus?.configured ? (
                        <>
                          <div className="rounded-lg bg-muted/50 p-6 space-y-4">
                            <div className="grid gap-y-3">
                              <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Имя пользователя бота:</span>
                                <span className="font-medium">@{telegramStatus.bot_username}</span>
                              </div>
                              {telegramStatus.connected_at && (
                                <div className="flex items-center justify-between">
                                  <span className="text-sm text-muted-foreground">Подключено:</span>
                                  <span className="font-medium">
                                    {new Date(telegramStatus.connected_at).toLocaleString('ru-RU', {
                                      month: 'numeric',
                                      day: 'numeric',
                                      year: 'numeric',
                                      hour: 'numeric',
                                      minute: '2-digit',
                                      second: '2-digit',
                                      hour12: true
                                    })}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="rounded-lg bg-blue-50 dark:bg-blue-950/20 p-4 border border-blue-200 dark:border-blue-900">
                            <div className="space-y-3 text-sm">
                              <p className="font-medium text-blue-900 dark:text-blue-100">URL вебхука</p>
                              <p className="text-xs text-blue-700 dark:text-blue-300">
                                Этот URL автоматически регистрируется в Telegram, чтобы входящие сообщения поступали в вашу CRM.
                                Если вы не получаете сообщения, введите ваш публичный URL ниже и нажмите "Перерегистрировать вебхук".
                              </p>
                              <div className="space-y-1">
                                <Label htmlFor="webhook-base-url" className="text-xs text-blue-800 dark:text-blue-200">Публичный базовый URL (например, из ngrok или Cloudflare)</Label>
                                <Input
                                  id="webhook-base-url"
                                  placeholder="https://your-tunnel.trycloudflare.com"
                                  value={webhookBaseUrl}
                                  onChange={(e) => setWebhookBaseUrl(e.target.value)}
                                  className="text-xs bg-white dark:bg-gray-900 border-blue-200 dark:border-blue-800"
                                />
                                {webhookBaseUrl && (
                                  <code className="block p-2 bg-white dark:bg-gray-900 rounded text-xs break-all border border-blue-200 dark:border-blue-800 text-muted-foreground">
                                    {webhookBaseUrl.replace(/\/$/, '')}/api/telegram-webhook/
                                  </code>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="flex gap-3">
                            <Button
                              variant="outline"
                              onClick={async () => {
                                try {
                                  const res = await registerTelegramWebhook(webhookBaseUrl.trim() || undefined)
                                  if (res.success) {
                                    toast.success(`Webhook registered: ${res.webhook_url ?? ''}`)
                                  } else {
                                    toast.error(res.error || "Failed to register webhook")
                                  }
                                } catch {
                                  toast.error("Failed to register webhook")
                                }
                              }}
                            >
                              Перерегистрировать вебхук
                            </Button>
                            <Button
                              variant="destructive"
                              onClick={handleDisconnectTelegram}
                            >
                              Отключить
                            </Button>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="space-y-4">
                            <div className="rounded-lg bg-muted p-4">
                              <h4 className="font-medium text-sm mb-2">Инструкции по настройке</h4>
                              <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
                                <li>Создайте нового бота, начав диалог с <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">@BotFather</a> в Telegram</li>
                                <li>Отправьте команду <code className="bg-background px-1 py-0.5 rounded">/newbot</code> и следуйте инструкциям</li>
                                <li>Скопируйте токен бота, предоставленный BotFather</li>
                                <li>Вставьте токен ниже и нажмите "Подключить бота"</li>
                                <li>Ваш бот будет готов отправлять и получать сообщения</li>
                              </ol>
                            </div>
                            <div className="space-y-3">
                              <div className="space-y-2">
                                <Label htmlFor="telegram-token">Токен бота</Label>
                                <Input
                                  id="telegram-token"
                                  type="password"
                                  placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                                  value={telegramToken}
                                  onChange={(e) => setTelegramToken(e.target.value)}
                                  disabled={isSavingToken}
                                />
                                <p className="text-xs text-muted-foreground">
                                  Введите токен бота, который вы получили от @BotFather
                                </p>
                              </div>
                              <Button
                                onClick={handleSaveTelegramToken}
                                disabled={isSavingToken || !telegramToken.trim()}
                                className="w-full sm:w-auto"
                              >
                                {isSavingToken ? 'Подключение...' : 'Подключить бота'}
                              </Button>
                            </div>
                          </div>
                        </>
                      )}
                      {telegramStatus?.error && (
                        <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                          {telegramStatus.error}
                        </div>
                      )}
                      {renderChannelAiControl('telegram_ai_paused', 'Telegram')}
                    </CardContent>
                  </Card>

                  {/* Instagram Integration Card */}
                  <Card>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-4">
                          <div className="rounded-lg bg-gradient-to-br from-purple-500 via-pink-500 to-orange-500 p-2.5">
                            <svg className="h-7 w-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                            </svg>
                          </div>
                          <div>
                            <h3 className="font-semibold text-lg">Instagram</h3>
                            <p className="text-sm text-muted-foreground">
                              Отправляйте и получайте личные сообщения (Direct) Instagram
                            </p>
                          </div>
                        </div>
                        <Badge variant={instagramStatusBadge.variant} className={instagramStatusBadge.className}>
                          {instagramStatusBadge.label === 'Connected' && <CheckCircleIcon className="h-3 w-3 mr-1" />}
                          {instagramStatusBadge.label}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Connected account info */}
                      {instagramStatus?.connected ? (
                        <>
                          <div className="rounded-lg bg-muted/50 p-6 space-y-4">
                            <div className="flex items-center gap-3">
                              {instagramStatus.profile_picture_url && (
                                <img
                                  src={instagramStatus.profile_picture_url}
                                  alt="profile"
                                  className="h-10 w-10 rounded-full object-cover"
                                />
                              )}
                              <div>
                                <p className="font-medium">@{instagramStatus.instagram_username}</p>
                                {instagramStatus.connected_at && (
                                  <p className="text-xs text-muted-foreground">
                                     \{new Date(instagramStatus.connected_at).toLocaleString('ru-RU', {
                                      month: 'numeric', day: 'numeric', year: 'numeric',
                                      hour: 'numeric', minute: '2-digit', hour12: true
                                    })}
                                  </p>
                                )}
                              </div>
                            </div>
                            {instagramStatus.token_expiry && (
                              <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground">Срок действия токена:</span>
                                <span className={instagramStatus.token_expiring_soon ? 'font-medium text-amber-600' : 'font-medium'}>
                                  {new Date(instagramStatus.token_expiry).toLocaleDateString('ru-RU', {
                                    month: 'short', day: 'numeric', year: 'numeric'
                                  })}
                                  {instagramStatus.token_expiring_soon && !instagramStatus.token_expired && ' (скоро истекает)'}
                                </span>
                              </div>
                            )}
                          </div>
                          <div className="space-y-2">
                            <p className="text-xs text-amber-600 dark:text-amber-400">
                              Токен автоматически продлевается каждые 60 дней. Если Instagram перестает работать, отключите его и подключите заново для получения нового токена.
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Если сообщения перестают поступать или отправляться, отключите его и подключите снова для решения проблемы.
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={handleDisconnectInstagram}
                              disabled={isDisconnectingInstagram}
                            >
                              {isDisconnectingInstagram ? 'Отключение...' : 'Отключить'}
                            </Button>
                          </div>
                        </>
                      ) : (
                        <>
                          <p className="text-sm text-muted-foreground">
                            Подключите ваш бизнес-аккаунт Instagram, чтобы отправлять и получать личные сообщения напрямую из CRM. Вы будете перенаправлены в Instagram для авторизации доступа.
                          </p>
                          <div className="rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 p-4 space-y-1">
                            <p className="text-xs font-medium text-amber-900 dark:text-amber-100">Требование к аккаунту</p>
                            <p className="text-xs text-amber-700 dark:text-amber-300">
                              \u0412\u0430\u0448 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0434\u043e\u043b\u0436\u0435\u043d \u0431\u044b\u0442\u044c <strong>Instagram \u0411\u0438\u0437\u043d\u0435\u0441 \u0438\u043b\u0438 Creator</strong>, \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d\u043d\u044b\u043c \u043a Facebook Page. \u041b\u0438\u0447\u043d\u044b\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u044b \u043d\u0435 \u043c\u043e\u0433\u0443\u0442 \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u044c DM \u0447\u0435\u0440\u0435\u0437 API.
                            </p>
                          </div>
                          <div className="rounded-lg bg-muted/50 border border-border p-4 space-y-4">
                            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                              <div>
                                <p className="text-sm font-medium">Учетные данные Meta App</p>
                                <p className="text-xs text-muted-foreground">
                                  Сохраните App ID и App Secret из Meta App Dashboard перед подключением Instagram.
                                </p>
                              </div>
                              <Badge variant={instagramCredentialsReady ? 'default' : 'secondary'} className={instagramCredentialsReady ? 'bg-green-600 hover:bg-green-700' : ''}>
                                {instagramCredentialsReady ? 'Готово' : 'Требуется настройка'}
                              </Badge>
                            </div>

                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="space-y-1.5">
                                <Label htmlFor="ig-app-id">App ID</Label>
                                <Input
                                  id="ig-app-id"
                                  name="ig-app-id"
                                  value={igAppId}
                                  onChange={(e) => setIgAppId(e.target.value)}
                                  placeholder="Например, 123456789012345"
                                  disabled={isSavingInstagramCredentials}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label htmlFor="ig-app-secret">
                                  App Secret{instagramStatus?.app_secret_set ? ' сохранен' : ''}
                                </Label>
                                <div className="relative">
                                  <Input
                                    id="ig-app-secret"
                                    name="ig-app-secret"
                                    type={showIgAppSecret ? 'text' : 'password'}
                                    value={igAppSecret}
                                    onChange={(e) => setIgAppSecret(e.target.value)}
                                    placeholder={instagramStatus?.app_secret_set ? 'Оставьте пустым, чтобы не менять' : 'Вставьте App Secret'}
                                    disabled={isSavingInstagramCredentials}
                                    className="pr-10"
                                  />
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    aria-label={showIgAppSecret ? 'Hide secret' : 'Show secret'}
                                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                                    onClick={() => setShowIgAppSecret((v) => !v)}
                                  >
                                    {showIgAppSecret ? (
                                      <EyeOffIcon className="h-4 w-4" />
                                    ) : (
                                      <EyeIcon className="h-4 w-4" />
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </div>

                            <div className="space-y-1.5">
                              <Label htmlFor="ig-verify-token">Verify Token для вебхука</Label>
                              <Input
                                id="ig-verify-token"
                                name="ig-verify-token"
                                value={igVerifyToken}
                                onChange={(e) => setIgVerifyToken(e.target.value)}
                                placeholder="Например, cayu_instagram_webhook_2024"
                                disabled={isSavingInstagramCredentials}
                              />
                            </div>

                            <div className="grid gap-2 text-xs">
                              {instagramStatus?.webhook_url && (
                                <div className="space-y-1">
                                  <p className="font-medium text-muted-foreground uppercase tracking-wide">Callback URL вебхука</p>
                                  <code className="block rounded bg-background border px-2 py-1.5 font-mono break-all">
                                    {instagramStatus.webhook_url}
                                  </code>
                                </div>
                              )}
                              {instagramStatus?.callback_url && (
                                <div className="space-y-1">
                                  <p className="font-medium text-muted-foreground uppercase tracking-wide">OAuth Redirect URI</p>
                                  <code className="block rounded bg-background border px-2 py-1.5 font-mono break-all">
                                    {instagramStatus.callback_url}
                                  </code>
                                </div>
                              )}
                            </div>

                            <Button
                              type="button"
                              variant="outline"
                              onClick={handleSaveInstagramCredentials}
                              disabled={isSavingInstagramCredentials || !igAppId.trim() || (!igAppSecret.trim() && !instagramStatus?.app_secret_set)}
                            >
                              {isSavingInstagramCredentials ? 'Сохранение...' : 'Сохранить данные Meta App'}
                            </Button>
                          </div>
                          {instagramStatus?.callback_warning && (
                            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 space-y-2">
                              <p className="text-xs font-medium text-destructive">Обнаружена проблема настройки подключения</p>
                              <p className="text-xs text-destructive/90">
                                {instagramStatus.callback_warning}
                              </p>
                              {instagramStatus.callback_url && (
                                <p className="text-[11px] text-destructive/80 break-all">
                                  Expected callback: {instagramStatus.callback_url}
                                </p>
                              )}
                            </div>
                          )}
                          {instagramStatus?.oauth_last_status === 'error' && instagramStatus.oauth_last_error && (
                            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 space-y-1">
                              <p className="text-xs font-medium text-destructive">Последняя попытка подключения к Instagram</p>
                              <p className="text-xs text-destructive/90">{instagramStatus.oauth_last_error}</p>
                              {instagramStatus.oauth_last_callback_at && (
                                <p className="text-[11px] text-destructive/80">
                                     \{new Date(instagramStatus.oauth_last_callback_at).toLocaleString('ru-RU', {
                                    month: 'numeric', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true,
                                  })}
                                </p>
                              )}
                            </div>
                          )}
                          <div className="rounded-lg bg-muted/50 border border-border p-4 space-y-1">
                            <p className="text-xs font-medium text-foreground">Как это работает</p>
                            <p className="text-xs text-muted-foreground">
                              Нажатие на <strong>Подключить Instagram</strong> открывает небольшое всплывающее окно. Если ваш браузер блокирует всплывающие окна, разрешите их для этой страницы и попробуйте снова. Всплывающее окно закроется автоматически после завершения авторизации.
                            </p>
                          </div>
                          {instagramProgressTitle && instagramConnectionNotice && (
                            <div className={`rounded-lg border p-4 space-y-1 ${instagramProgressTone}`}>
                              <div className="flex items-center gap-2 text-sm font-medium">
                                {(instagramConnectStage === 'waiting_for_login' || instagramConnectStage === 'authorization_in_progress') && (
                                  <Loader2Icon className="h-4 w-4 animate-spin" />
                                )}
                                {instagramProgressTitle}
                              </div>
                              <p className="text-sm opacity-90">{instagramConnectionNotice}</p>
                            </div>
                          )}
                          <Button
                            onClick={handleConnectInstagram}
                            className="w-full sm:w-auto"
                            disabled={!instagramStatus?.embed_url || !instagramCredentialsReady || isInstagramConnecting}
                          >
                            {isInstagramConnecting
                              ? instagramConnectButtonLabel
                              : instagramStatus?.embed_url && instagramCredentialsReady
                                ? 'Подключить Instagram'
                                : 'Сначала сохраните Meta App'}
                          </Button>
                          {(instagramConnectStage === 'failed' || instagramConnectStage === 'cancelled') && instagramConnectionNotice && !instagramProgressTitle && (
                            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                              {instagramConnectionNotice}
                            </div>
                          )}
                        </>
                      )}

                      {renderChannelAiControl('instagram_ai_paused', 'Instagram')}

                    </CardContent>
                  </Card>

                  {/* WhatsApp Integration Card */}
                  <Card>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="rounded-lg bg-green-500 p-2.5">
                            <svg className="h-5 w-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                            </svg>
                          </div>
                          <div>
                            <h3 className="font-semibold text-lg">WhatsApp</h3>
                            <p className="text-sm text-muted-foreground">
                              Отправляйте и получайте сообщения через WhatsApp Business
                            </p>
                          </div>
                        </div>
                        {whatsappStatus?.connected ? (
                          <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                            <CheckCircleIcon className="h-3 w-3 mr-1" />
                            Подключено
                          </Badge>
                        ) : (
                          <Badge variant="secondary">Не подключено</Badge>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {whatsappStatus?.connected ? (
                        <>
                          <div className="rounded-lg bg-muted/50 p-4 space-y-3">
                            {whatsappStatus.display_phone_number ? (
                              <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Номер телефона:</span>
                                <span className="font-medium">{whatsappStatus.display_phone_number}</span>
                              </div>
                            ) : null}
                            {whatsappStatus.verified_name ? (
                              <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Имя бизнеса:</span>
                                <span className="font-medium">{whatsappStatus.verified_name}</span>
                              </div>
                            ) : null}
                            {whatsappStatus.connected_at ? (
                              <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Подключено:</span>
                                <span className="font-medium">
                                  {new Date(whatsappStatus.connected_at).toLocaleDateString('ru-RU', {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                  })}
                                </span>
                              </div>
                            ) : null}
                          </div>

                          {/* Webhook configuration instructions */}
                          <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 p-4 space-y-3">
                            <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                              Вставьте эти значения в Панель управления Meta App → WhatsApp → Настройка → Вебхук
                            </p>
                            <div className="space-y-2">
                              <div className="space-y-1">
                                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">URL вебхука</p>
                                <div className="flex items-center gap-2">
                                  <code className="flex-1 rounded bg-background border px-2 py-1.5 text-xs font-mono break-all">
                                    {whatsappStatus.webhook_url ?? ''}
                                  </code>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    aria-label="Copy webhook URL"
                                    onClick={() => {
                                      navigator.clipboard.writeText(whatsappStatus.webhook_url ?? '')
                                      toast.success('URL вебхука скопирован')
                                    }}
                                  >
                                    Копировать
                                  </Button>
                                </div>
                              </div>
                              {whatsappStatus.verify_token ? (
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Токен подтверждения</p>
                                  <div className="flex items-center gap-2">
                                    <code className="flex-1 rounded bg-background border px-2 py-1.5 text-xs font-mono break-all">
                                      {whatsappStatus.verify_token}
                                    </code>
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      aria-label="Copy verify token"
                                      onClick={() => {
                                        navigator.clipboard.writeText(whatsappStatus.verify_token ?? '')
                                        toast.success('Токен подтверждения скопирован')
                                      }}
                                    >
                                      Копировать
                                    </Button>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                            <p className="text-xs text-amber-800 dark:text-amber-300 mt-1">
                              ⚠️ Убедитесь, что ваше приложение Meta находится в режиме <strong>Live Mode</strong> (а не Development Mode) — в режиме разработки сообщения от реальных пользователей не доставляются.
                            </p>
                          </div>

                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={handleDisconnectWhatsApp}
                          >
                            Отключить
                          </Button>
                        </>
                      ) : (
                        <div className="space-y-4">
                          <p className="text-sm text-muted-foreground">
                            Введите учетные данные WhatsApp Business из панели разработчика Meta.
                          </p>
                          <div className="space-y-3">
                            <div className="space-y-1.5">
                              <Label htmlFor="wa-phone-number-id">ID номера телефона</Label>
                              <Input
                                id="wa-phone-number-id"
                                name="wa-phone-number-id"
                                value={waPhoneNumberId}
                                onChange={(e) => setWaPhoneNumberId(e.target.value)}
                                placeholder="e.g. 123456789012345"
                                disabled={isConnectingWhatsApp}
                              />
                              <p className="text-xs text-muted-foreground">
                                Находится в Meta Dashboard → WhatsApp → API Setup
                              </p>
                            </div>
                            <div className="space-y-1.5">
                              <Label htmlFor="wa-waba-id">ID бизнес-аккаунта</Label>
                              <Input
                                id="wa-waba-id"
                                name="wa-waba-id"
                                value={waWabaId}
                                onChange={(e) => setWaWabaId(e.target.value)}
                                placeholder="e.g. 123456789012345"
                                disabled={isConnectingWhatsApp}
                              />
                              <p className="text-xs text-muted-foreground">
                                Находится в Meta Dashboard → WhatsApp → API Setup
                              </p>
                            </div>
                            <div className="space-y-1.5">
                              <Label htmlFor="wa-access-token">Постоянный токен доступа</Label>
                              <div className="relative">
                                <Input
                                  id="wa-access-token"
                                  name="wa-access-token"
                                  type={showWaToken ? 'text' : 'password'}
                                  value={waAccessToken}
                                  onChange={(e) => setWaAccessToken(e.target.value)}
                                  placeholder="Вставьте ваш токен здесь"
                                  disabled={isConnectingWhatsApp}
                                  className="pr-10"
                                />
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  aria-label={showWaToken ? 'Hide token' : 'Show token'}
                                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                                  onClick={() => setShowWaToken((v) => !v)}
                                >
                                  {showWaToken ? (
                                    <EyeOffIcon className="h-4 w-4" />
                                  ) : (
                                    <EyeIcon className="h-4 w-4" />
                                  )}
                                </Button>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                Создайте токен системного пользователя в Meta Business Manager → Системные пользователи
                              </p>
                            </div>

                            <Separator />
                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Необязательно — учетные данные приложения</p>
                            <p className="text-xs text-muted-foreground">
                              Укажите App ID и Secret вашего приложения Meta для активации автоматической подписки на вебхуки.
                            </p>

                            <div className="space-y-1.5">
                              <Label htmlFor="wa-app-id">ID приложения</Label>
                              <Input
                                id="wa-app-id"
                                name="wa-app-id"
                                value={waAppId}
                                onChange={(e) => setWaAppId(e.target.value)}
                                placeholder="e.g. 1274437444500708"
                                disabled={isConnectingWhatsApp}
                              />
                              <p className="text-xs text-muted-foreground">
                                Находится в панели Meta App Dashboard → App Settings → Basic
                              </p>
                            </div>

                            <div className="space-y-1.5">
                              <Label htmlFor="wa-app-secret">Секрет приложения</Label>
                              <div className="relative">
                                <Input
                                  id="wa-app-secret"
                                  name="wa-app-secret"
                                  type={showWaAppSecret ? 'text' : 'password'}
                                  value={waAppSecret}
                                  onChange={(e) => setWaAppSecret(e.target.value)}
                                  placeholder="Вставьте секрет вашего приложения здесь"
                                  disabled={isConnectingWhatsApp}
                                  className="pr-10"
                                />
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  aria-label={showWaAppSecret ? 'Hide secret' : 'Show secret'}
                                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                                  onClick={() => setShowWaAppSecret((v) => !v)}
                                >
                                  {showWaAppSecret ? (
                                    <EyeOffIcon className="h-4 w-4" />
                                  ) : (
                                    <EyeIcon className="h-4 w-4" />
                                  )}
                                </Button>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                Находится в панели Meta App Dashboard → App Settings → Basic
                              </p>
                            </div>

                            <Button
                              onClick={handleConnectWhatsApp}
                              disabled={isConnectingWhatsApp || !waPhoneNumberId.trim() || !waWabaId.trim() || !waAccessToken.trim()}
                              className="w-full bg-green-600 hover:bg-green-700 text-white"
                            >
                              {isConnectingWhatsApp ? 'Подключение...' : 'Подключить WhatsApp'}
                            </Button>
                          </div>
                        </div>
                      )}

                      {renderChannelAiControl('whatsapp_ai_paused', 'WhatsApp')}

                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="ai-support" className="space-y-6">
                <div className="grid gap-6 max-w-4xl">
                  {/* AI Auto-Response Configuration */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Автоответ</CardTitle>
                      <CardDescription>
                        Настройте то, как AI отвечает на входящие сообщения
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* AI Auto-Response Toggle */}
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="ai-auto-response">Автоответ AI</Label>
                          <p className="text-sm text-muted-foreground">
                            Автоматически отвечать на сообщения в Telegram с помощью AI
                          </p>
                        </div>
                        <Switch
                          id="ai-auto-response"
                          checked={aiConfig?.ai_auto_response ?? false}
                          onCheckedChange={(checked) => handleAIConfigChange({ ai_auto_response: checked })}
                        />
                      </div>

                      <Separator />

                      {/* Auto Extract Data Toggle */}
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="auto-extract-data">Автоматическое извлечение данных</Label>
                          <p className="text-sm text-muted-foreground">
                            Автоматически извлекать информацию о лидах из диалогов
                          </p>
                        </div>
                        <Switch
                          id="auto-extract-data"
                          checked={aiConfig?.auto_extract_data ?? false}
                          onCheckedChange={(checked) => handleAIConfigChange({ auto_extract_data: checked })}
                        />
                      </div>

                      <Separator />

                      {/* Response Delay / Message Pooling Window */}
                      <div className="space-y-2">
                        <Label htmlFor="response-delay">Окно объединения сообщений (секунды)</Label>
                        <Input
                          id="response-delay"
                          type="number"
                          min="0"
                          max="60"
                          value={aiConfig?.response_delay ?? 5}
                          onChange={(e) => handleAIConfigChange({ response_delay: parseInt(e.target.value) || 0 })}
                          className="max-w-xs"
                        />
                        <p className="text-sm text-muted-foreground">
                          Сколько времени ждать после получения сообщения перед ответом. Короткие сообщения, отправленные быстро друг за другом, объединяются в один запрос и обрабатываются вместе. Рекомендуется: 5–10 секунд.
                        </p>
                        {(aiConfig?.response_delay ?? 5) > 15 && (
                          <p className="text-sm text-amber-600 dark:text-amber-400">
                            ⚠ Значения выше 15 секунд приводят к тому, что Telegram пробует повторить доставку, что может вызвать дублирование ответов. Рекомендуется: 5–10 секунд.
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Proactive Outreach */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Проактивный контакт</CardTitle>
                      <CardDescription>
                        AI-агент автоматически связывается с лидами, чтобы продвигать их к совершению бронирования
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Enable Toggle */}
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="proactive-outreach">Включить автономные напоминания</Label>
                          <p className="text-sm text-muted-foreground">
                            AI-агент отслеживает лидов и отправляет им персонализированные напоминания
                          </p>
                        </div>
                        <Switch
                          id="proactive-outreach"
                          checked={aiConfig?.proactive_outreach_enabled ?? false}
                          onCheckedChange={(checked) => handleAIConfigChange({ proactive_outreach_enabled: checked })}
                        />
                      </div>

                      {aiConfig?.proactive_outreach_enabled && (
                        <>
                          <Separator />

                          {/* Check Frequency */}
                          <div className="space-y-2">
                            <Label htmlFor="check-frequency">Частота проверки (часы)</Label>
                            <Select
                              value={String(aiConfig?.check_frequency_hours ?? 24)}
                              onValueChange={(v) => handleAIConfigChange({ check_frequency_hours: parseInt(v) })}
                            >
                              <SelectTrigger className="max-w-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="24">Каждые 24 часа</SelectItem>
                                <SelectItem value="48">Каждые 48 часов</SelectItem>
                                <SelectItem value="72">Каждые 72 часа</SelectItem>
                              </SelectContent>
                            </Select>
                            <p className="text-sm text-muted-foreground">
                              Как часто AI-агент проверяет лиды на необходимость отправки напоминаний
                            </p>
                          </div>

                          {/* Inactivity Threshold */}
                          <div className="space-y-2">
                            <Label htmlFor="inactivity-threshold">Порог неактивности (дни)</Label>
                            <Input
                              id="inactivity-threshold"
                              type="number"
                              min="1"
                              max="30"
                              value={aiConfig?.inactivity_threshold_days ?? 2}
                              onChange={(e) => handleAIConfigChange({ inactivity_threshold_days: parseInt(e.target.value) || 2 })}
                              className="max-w-xs"
                            />
                            <p className="text-sm text-muted-foreground">
                              Дни неактивности, после которых агент отправляет напоминание
                            </p>
                          </div>

                          {/* Max Follow-up Attempts */}
                          <div className="space-y-2">
                            <Label htmlFor="max-followups">Максимальное количество попыток напоминания</Label>
                            <Input
                              id="max-followups"
                              type="number"
                              min="1"
                              max="10"
                              value={aiConfig?.max_followup_attempts ?? 3}
                              onChange={(e) => handleAIConfigChange({ max_followup_attempts: parseInt(e.target.value) || 3 })}
                              className="max-w-xs"
                            />
                            <p className="text-sm text-muted-foreground">
                              Прекратить отправку напоминаний после указанного количества попыток на одного лида
                            </p>
                          </div>

                          <Separator />

                          {/* Manual Run Button */}
                          <div className="flex items-center justify-between">
                            <div className="space-y-0.5">
                              <Label>Запустить агента сейчас</Label>
                              <p className="text-sm text-muted-foreground">
                                Запустить агента вручную для проверки всех лидов
                              </p>
                            </div>
                            <Button
                              variant="outline"
                              onClick={async () => {
                                try {
                                  const result = await runAgentNow()
                                  if (result.success && result.results) {
                                    toast.success(`Agent completed: ${result.results.messaged} messages sent, ${result.results.skipped} skipped`)
                                  } else {
                                    toast.error(result.error || 'Failed to run agent')
                                  }
                                } catch {
                                  toast.error('Не удалось запустить агента')
                                }
                              }}
                            >
                              Запустить сейчас
                            </Button>
                          </div>
                        </>
                      )}
                    </CardContent>
                  </Card>

                  {/* Agent Autonomy Settings */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Автономия агента</CardTitle>
                      <CardDescription>
                        Управляйте тем, насколько автономно может действовать AI-агент
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Auto Status Progression */}
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="auto-status-progression">Автоматическое продвижение статуса</Label>
                          <p className="text-sm text-muted-foreground">
                            AI автоматически продвигает лиды по этапам на основе сигналов из диалога
                          </p>
                        </div>
                        <Switch
                          id="auto-status-progression"
                          checked={aiConfig?.auto_status_progression ?? false}
                          onCheckedChange={(checked) => handleAIConfigChange({ auto_status_progression: checked })}
                        />
                      </div>

                      <Separator />

                      {/* Smart Objection Handling */}
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="smart-objection-handling">Умная обработка возражений</Label>
                          <p className="text-sm text-muted-foreground">
                            AI обнаруживает возражения и отвечает на них на основе базы знаний
                          </p>
                        </div>
                        <Switch
                          id="smart-objection-handling"
                          checked={aiConfig?.smart_objection_handling ?? false}
                          onCheckedChange={(checked) => handleAIConfigChange({ smart_objection_handling: checked })}
                        />
                      </div>

                      <Separator />

                      {/* Auto Execute Tasks */}
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="auto-execute-tasks">Самовыполняющиеся задачи</Label>
                          <p className="text-sm text-muted-foreground">
                            AI автоматически создает и выполняет задачи (отправка сообщений, документов)
                          </p>
                        </div>
                        <Switch
                          id="auto-execute-tasks"
                          checked={aiConfig?.auto_execute_tasks ?? false}
                          onCheckedChange={(checked) => handleAIConfigChange({ auto_execute_tasks: checked })}
                        />
                      </div>

                      <Separator />

                      {/* Conversation Goals */}
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="conversation-goals">Цели диалога</Label>
                          <p className="text-sm text-muted-foreground">
                            AI отслеживает и стремится к выполнению целей для каждого лида (сбор почты, планирование звонка)
                          </p>
                        </div>
                        <Switch
                          id="conversation-goals"
                          checked={aiConfig?.conversation_goals_enabled ?? false}
                          onCheckedChange={(checked) => handleAIConfigChange({ conversation_goals_enabled: checked })}
                        />
                      </div>
                    </CardContent>
                  </Card>

                  {/* AI Persona — managed in Hotel Details */}
                  <Card className="border-dashed">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <SparklesIcon className="h-4 w-4 text-muted-foreground" />
                        Персона и стиль AI
                      </CardTitle>
                      <CardDescription>
                        Управляется в Деталях отеля → вкладка Стиль AI
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground">
                        Персонаж AI, тон, использование эмодзи, длина ответов, апсейл-поведение, языки и примеры
                        диалогов настраиваются на странице <strong>Деталей отеля</strong> во вкладке{' '}
                        <strong>Стиль AI</strong>. Изменения вступают в силу мгновенно на каждый ответ.
                      </p>
                    </CardContent>
                  </Card>

                  {/* Company Profile — managed in Hotel Details */}
                  <Card className="border-dashed">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Building2Icon className="h-4 w-4 text-muted-foreground" />
                        Информация об отеле и правила
                      </CardTitle>
                      <CardDescription>
                        Управляется в Деталях отеля → вкладка Инфо об отеле
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground">
                        Профиль отеля, адрес, направления, правила, часто задаваемые вопросы и контакты для передачи
                        настраиваются на странице <strong>Деталей отеля</strong> во вкладке{' '}
                        <strong>Инфо об отеле</strong>. AI автоматически использует весь этот контекст при
                        ответе гостям.
                      </p>
                    </CardContent>
                  </Card>

                </div>
              </TabsContent>

              <TabsContent value="preferences" className="space-y-6">
                <div className="grid gap-6 max-w-4xl">
                  <Card>
                    <CardHeader>
                      <CardTitle>{t('settings.preferences.title')}</CardTitle>
                      <CardDescription>{t('settings.preferences.subtitle')}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="space-y-2">
                        <Label>{t('settings.preferences.language')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.preferences.languageDesc')}</p>
                        <Select
                          value={language}
                          onValueChange={(val) => {
                            setLanguage(val as Language)
                            toast.success(t('settings.preferences.saved'))
                          }}
                        >
                          <SelectTrigger className="w-64">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="en">{t('settings.preferences.english')}</SelectItem>
                            <SelectItem value="ru">{t('settings.preferences.russian')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="team" className="space-y-6">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2"><UsersIcon className="h-5 w-5" />Участники команды</CardTitle>
                      <CardDescription>{orgMembers.length} участник(ов) в {currentOrg?.name || 'вашей организации'}</CardDescription>
                    </div>
                    {isOwnerOrAdmin && (
                      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
                        <DialogTrigger asChild>
                          <Button size="sm"><PlusIcon className="mr-1.5 h-3.5 w-3.5" />Пригласить участника</Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader><DialogTitle>Пригласить участника команды</DialogTitle></DialogHeader>
                          <div className="space-y-4 py-2">
                            <div className="space-y-2">
                              <Label>Email address</Label>
                              <Input value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="colleague@company.com" type="email" />
                            </div>
                            <div className="space-y-2">
                              <Label>Role</Label>
                              <Select value={inviteRole} onValueChange={v => setInviteRole(v as 'member' | 'admin')}>
                                <SelectTrigger><span>{inviteRole === 'admin' ? 'Администратор — может управлять настройками и интеграциями' : 'Участник — может управлять лидами и коммуникациями'}</span></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="member">Участник — может управлять лидами и коммуникациями</SelectItem>
                                  <SelectItem value="admin">Администратор — может управлять настройками и интеграциями</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            {inviteError && <p className="text-sm text-red-500">{inviteError}</p>}
                          </div>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setInviteOpen(false)}>Отмена</Button>
                            <Button onClick={handleInvite} disabled={inviteLoading || !inviteEmail}>
                              {inviteLoading ? <><Loader2Icon className="mr-2 h-4 w-4 animate-spin" />Приглашение...</> : 'Отправить приглашение'}
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    )}
                  </CardHeader>
                  <CardContent>
                    {membersLoading ? (
                      <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-12 bg-muted animate-pulse rounded" />)}</div>
                    ) : (
                      <div className="divide-y">
                        {orgMembers.map(member => (
                          <div key={member.id} className="flex items-center gap-3 py-3">
                            <Avatar className="h-9 w-9">
                              <AvatarFallback className="text-xs">{(member.user_name || member.user_email).slice(0,2).toUpperCase()}</AvatarFallback>
                            </Avatar>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm truncate">{member.user_name || member.user_email}</p>
                              <p className="text-xs text-muted-foreground truncate">{member.user_email}</p>
                            </div>
                            <RoleBadge role={member.role} />
                            {isOwnerOrAdmin && member.role !== 'owner' && (
                              <div className="flex items-center gap-1">
                                <Select value={member.role} onValueChange={v => handleRoleChange(member.user_id, v)}>
                                  <SelectTrigger className="h-7 w-24 text-xs"><span>{member.role === 'admin' ? 'Администратор' : 'Участник'}</span></SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="member">Участник</SelectItem>
                                    <SelectItem value="admin">Администратор</SelectItem>
                                  </SelectContent>
                                </Select>
                                <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                                  onClick={() => handleRemoveMember(member.user_id)}>
                                  <TrashIcon className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="organization" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><BuildingIcon className="h-5 w-5" />Настройки организации</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="space-y-2">
                      <Label>Название организации</Label>
                      <div className="flex gap-2">
                        <Input value={orgName} onChange={e => setOrgName(e.target.value)} className="max-w-sm" />
                        <Button onClick={handleSaveOrgName} disabled={orgNameSaving || orgName === currentOrg?.name}>
                          {orgNameSaving ? <Loader2Icon className="h-4 w-4 animate-spin" /> : 'Сохранить'}
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label>Слаг</Label>
                      <p className="text-sm font-mono text-muted-foreground bg-muted px-3 py-2 rounded w-fit">{currentOrg?.slug}</p>
                    </div>
                    <div className="space-y-2">
                      <Label>Тарифный план</Label>
                      <p className="capitalize text-sm font-medium">{currentOrg?.plan || '—'}</p>
                    </div>
                    <div className="space-y-2">
                      <Label>Создана</Label>
                      <p className="text-sm text-muted-foreground">
                        {currentOrg?.created_at ? new Date(currentOrg.created_at).toLocaleDateString() : '—'}
                      </p>
                    </div>
                  </CardContent>
                </Card>

                {isOwner && (
                  <Card className="border-destructive/40">
                    <CardHeader>
                      <CardTitle className="text-destructive">Опасная зона</CardTitle>
                      <CardDescription>Навсегда удалить эту организацию и все её данные.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="destructive">Удалить организацию</Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Удалить {currentOrg?.name}?</AlertDialogTitle>
                            <AlertDialogDescription>
                              Это навсегда удалит организацию и все связанные данные, включая лиды, клиентов и интеграции. Это действие невозможно отменить.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={handleDeleteOrg} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                              Удалить навсегда
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

            </Tabs>
          </div>
        </div>
      </div>

      {/* Stage Dialog */}
      <Dialog open={stageDialogOpen} onOpenChange={setStageDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingStage ? 'Редактировать' : 'Добавить'} этап воронки</DialogTitle>
            <DialogDescription>
              {editingStage ? 'Обновить' : 'Создать'} этап воронки для ваших лидов
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="stage-name">Название</Label>
              <Input
                id="stage-name"
                value={stageName}
                onChange={(e) => {
                  setStageName(e.target.value)
                  if (!isKeyManuallyEdited && !editingStage) {
                    setStageKey(slugify(e.target.value))
                  }
                }}
                placeholder="напр. Квалифицирован"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="stage-key">Ключ</Label>
              <Input
                id="stage-key"
                value={stageKey}
                onChange={(e) => {
                  setStageKey(e.target.value)
                  setIsKeyManuallyEdited(true)
                }}
                placeholder="напр. qualified"
                disabled={!!editingStage}
              />
              <p className="text-xs text-muted-foreground">
                Уникальный идентификатор (не может быть изменен после создания)
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="stage-description">Описание</Label>
              <Textarea
                id="stage-description"
                value={stageDescription}
                onChange={(e) => setStageDescription(e.target.value)}
                placeholder="Опишите этот этап..."
                rows={3}
              />
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="stage-is-final">Финальный этап</Label>
                <p className="text-sm text-muted-foreground">
                  Отметить как финальный (AI-агент не будет вести лиды на этом этапе)
                </p>
              </div>
              <Switch
                id="stage-is-final"
                checked={stageIsFinal}
                onCheckedChange={setStageIsFinal}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseStageDialog}>
              Отмена
            </Button>
            <Button onClick={handleSaveStage}>
              {editingStage ? 'Обновить' : 'Создать'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Segment Dialog */}
      <Dialog open={segmentDialogOpen} onOpenChange={(open) => {
        if (!open) handleCloseSegmentDialog()
        else setSegmentDialogOpen(true)
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingSegment ? 'Редактировать' : 'Добавить'} сегмент</DialogTitle>
            <DialogDescription>
              {editingSegment ? 'Обновить' : 'Создать'} сегмент типа клиента для категоризации лидов
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="segment-name">Название</Label>
              <Input
                id="segment-name"
                value={segmentName}
                onChange={(e) => {
                  setSegmentName(e.target.value)
                  if (!isSegmentKeyManuallyEdited && !editingSegment) {
                    setSegmentKey(slugify(e.target.value))
                  }
                }}
                placeholder="напр. Предприятие"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="segment-key">Ключ</Label>
              <Input
                id="segment-key"
                value={segmentKey}
                onChange={(e) => {
                  setSegmentKey(e.target.value)
                  setIsSegmentKeyManuallyEdited(true)
                }}
                placeholder="напр. enterprise"
                disabled={!!editingSegment}
              />
              <p className="text-xs text-muted-foreground">
                Уникальный идентификатор (не может быть изменен после создания)
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseSegmentDialog}>
              Отмена
            </Button>
            <Button onClick={handleSaveSegment}>
              {editingSegment ? 'Обновить' : 'Создать'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Удалить {deleteDialogType === 'stage' ? 'этап воронки' : 'сегмент'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              Вы уверены, что хотите удалить этот {deleteDialogType === 'stage' ? 'этап воронки' : 'сегмент'}? Это действие нельзя отменить.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  )
}
