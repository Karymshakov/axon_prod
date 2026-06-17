import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useRef, useEffect, useMemo } from 'react'
import {
  MessageSquareIcon,
  SendIcon,
  InstagramIcon,
  PhoneIcon,
  SmileIcon,
  BotIcon,
  HandIcon,
  PlayIcon,
  RotateCcwIcon,
  UserIcon,
  SearchIcon,
  InfoIcon,
  SlidersHorizontalIcon,
  ScrollTextIcon,
  ArrowLeftIcon,
  PaperclipIcon,
  XIcon,
  FileIcon,
  PauseIcon,
  MicIcon,
  SquareIcon,
  Volume2Icon
} from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LeadSourceBadge } from '@/components/lead-source-badge'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  fetchTelegramIntegrationStatus,
  fetchInstagramStatus,
  fetchWhatsAppIntegrationStatus,
  fetchLeads,
  fetchOrganizations,
  sendTelegramMessageFromComms,
  sendInstagramMessageFromComms,
  sendWhatsAppMessageFromComms,
  uploadCommsMedia,
  fetchLeadActivities,
  fetchCommunicationsUnreadCounts,
  markCommunicationsRead,
  toggleAiPause,
  resetLeadAiMemory,
  type Lead,
} from '@/lib/api'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { AiDiagnosticsPanel } from '@/components/communications/ai-diagnostics-panel'
import { LeadDetailsSidebar } from '@/components/communications/lead-details-sidebar'
import { CopilotSuggestions } from '@/components/communications/copilot-suggestions'
import { QuickRepliesPopover } from '@/components/communications/quick-replies-popover'
import { useAuth } from '@/contexts/auth-context'
import { getInternalToolsVisibilitySettings } from '@/lib/org-settings'

export const Route = createFileRoute('/_app/communications')({
  validateSearch: (search: Record<string, unknown>) => ({
    leadId: typeof search.leadId === 'string' ? search.leadId : undefined,
    channel:
      search.channel === 'telegram' || search.channel === 'instagram' || search.channel === 'whatsapp'
        ? search.channel
        : undefined,
  }),
  component: CommunicationsPage,
})

const COMMON_EMOJIS = [
  '😀', '😃', '😄', '😁', '😆', '😅', '😂', '🤣',
  '😊', '😇', '🙂', '🙃', '😉', '😌', '😍', '🥰',
  '😘', '😗', '😙', '😚', '😋', '😛', '😝', '😜',
  '🤪', '🤨', '🧐', '🤓', '😎', '🤩', '🥳', '😏',
]

type ConversationChannel = 'telegram' | 'instagram' | 'whatsapp'

type ResetTarget = {
  lead: Lead
  channel: ConversationChannel
}

function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url
  }
  const apiBase = import.meta.env.VITE_API_BASE_URL || ''
  if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
    try {
      const origin = new URL(apiBase).origin
      return `${origin}${url}`
    } catch {
      // fallback
    }
  }
  return url
}

function getTelegramMessageText(activity: { description: string; metadata: Record<string, unknown> | null }) {
  const metadata = activity.metadata ?? {}
  const directText = typeof metadata.text === 'string'
    ? metadata.text
    : typeof metadata.message === 'string'
      ? metadata.message
      : ''

  if (directText.trim()) {
    return directText.trim()
  }

  return activity.description.replace(/^Telegram message sent:\s*/i, '').trim()
}

function sortActivitiesChronologically<T extends { created_at: string; id: number }>(items: T[]) {
  return [...items].sort((a, b) => {
    const createdAtDiff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    if (createdAtDiff !== 0) {
      return createdAtDiff
    }
    return a.id - b.id
  })
}

function getSentBy(metadata: Record<string, unknown> | null): string {
  if (!metadata) return 'ИИ'
  if (metadata.is_manager_manual) {
    const name = typeof metadata.sent_by_name === 'string' ? metadata.sent_by_name.trim() : ''
    const initials = typeof metadata.sent_by_initials === 'string' ? metadata.sent_by_initials.trim() : ''
    const email = typeof metadata.sent_by_email === 'string' ? metadata.sent_by_email.trim() : ''
    return name || initials || email || 'Менеджер'
  }
  if (metadata.is_ai_generated || metadata.is_ai_agent || metadata.is_ai_action) return 'ИИ'
  return 'ИИ'
}

type CommsMediaType = 'photo' | 'video' | 'audio' | 'document'

function inferFileMediaType(file: File): CommsMediaType {
  if (file.type.startsWith('image/')) return 'photo'
  if (file.type.startsWith('video/')) return 'video'
  if (file.type.startsWith('audio/')) return 'audio'
  return 'document'
}

function getConversationDraftKey(leadId: number, channel: ConversationChannel) {
  return `communications:draft:${leadId}:${channel}`
}

function getPreferredRecorderMimeType(channel: ConversationChannel) {
  if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') {
    return ''
  }

  const candidates = channel === 'whatsapp'
    ? ['audio/ogg;codecs=opus', 'audio/mp4']
    : ['audio/ogg;codecs=opus', 'audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']

  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || ''
}

function canRecordVoiceForChannel(channel: ConversationChannel) {
  if (channel === 'instagram') return false
  if (typeof MediaRecorder === 'undefined') return false
  if (channel === 'whatsapp') return Boolean(getPreferredRecorderMimeType(channel))
  return true
}

function formatMediaTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0:00'
  const totalSeconds = Math.floor(seconds)
  const minutes = Math.floor(totalSeconds / 60)
  const rest = totalSeconds % 60
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

function CustomVideoPlayer({ src, title }: { src: string; title?: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const togglePlayback = () => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) {
      void video.play()
    } else {
      video.pause()
    }
  }

  const handleSeek = (value: string) => {
    const nextTime = Number(value)
    const video = videoRef.current
    if (!video || !Number.isFinite(nextTime)) return
    video.currentTime = nextTime
    setCurrentTime(nextTime)
  }

  return (
    <div className="relative w-full min-w-[240px] max-w-[440px] overflow-hidden rounded-xl bg-black shadow-sm">
      <video
        ref={videoRef}
        src={src}
        preload="metadata"
        className="max-h-80 w-full bg-black"
        onClick={togglePlayback}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
      >
        Ваш браузер не поддерживает просмотр видео.
      </video>
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/45 to-transparent px-3 pb-3 pt-8 text-white">
        <div className="mb-2 flex items-center gap-2">
          <button
            type="button"
            onClick={togglePlayback}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-slate-950 shadow-sm transition hover:bg-white/90"
            aria-label={isPlaying ? 'Пауза' : 'Воспроизвести'}
          >
            {isPlaying ? <PauseIcon className="h-4 w-4" /> : <PlayIcon className="h-4 w-4" />}
          </button>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold">{title || 'Видео'}</div>
            <div className="text-[11px] text-white/75">{formatMediaTime(currentTime)} / {formatMediaTime(duration)}</div>
          </div>
        </div>
        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={Math.min(currentTime, duration || currentTime)}
          onChange={(event) => handleSeek(event.target.value)}
          className="h-1 w-full accent-white"
          aria-label="Позиция видео"
        />
      </div>
    </div>
  )
}

function CustomAudioPlayer({ src, title, isVoice }: { src: string; title?: string; isVoice?: boolean }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const togglePlayback = () => {
    const audio = audioRef.current
    if (!audio) return
    if (audio.paused) {
      void audio.play()
    } else {
      audio.pause()
    }
  }

  const handleSeek = (value: string) => {
    const nextTime = Number(value)
    const audio = audioRef.current
    if (!audio || !Number.isFinite(nextTime)) return
    audio.currentTime = nextTime
    setCurrentTime(nextTime)
  }

  return (
    <div className="min-w-[260px] max-w-[380px] rounded-xl border border-violet-200/70 bg-white/90 p-3 text-slate-950 shadow-sm dark:border-violet-900/40 dark:bg-slate-950/80 dark:text-white">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
      >
        Ваш браузер не поддерживает воспроизведение аудио.
      </audio>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={togglePlayback}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-violet-600 text-white shadow-sm transition hover:bg-violet-700"
          aria-label={isPlaying ? 'Пауза' : 'Воспроизвести'}
        >
          {isPlaying ? <PauseIcon className="h-4 w-4" /> : <PlayIcon className="h-4 w-4" />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-violet-800 dark:text-violet-200">
            {isVoice ? <MicIcon className="h-3.5 w-3.5" /> : <Volume2Icon className="h-3.5 w-3.5" />}
            <span className="truncate">{title || (isVoice ? 'Голосовое сообщение' : 'Аудио')}</span>
          </div>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={Math.min(currentTime, duration || currentTime)}
            onChange={(event) => handleSeek(event.target.value)}
            className="h-1 w-full accent-violet-600"
            aria-label="Позиция аудио"
          />
          <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
            <span>{formatMediaTime(currentTime)}</span>
            <span>{formatMediaTime(duration)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function CommunicationsPage() {
  const navigate = useNavigate()
  const routeSearch = Route.useSearch()
  const { t } = useLanguage()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const requestedLeadId = routeSearch.leadId
  const requestedChannel = routeSearch.channel as ConversationChannel | undefined

  // Dynamic Unified inbox filters
  const [activeChannelTab, setActiveChannelTab] = useState<'all' | ConversationChannel>('all')
  const [activeStatusFilter, setActiveStatusFilter] = useState<'all' | 'unread' | 'paused' | 'active'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Workspace layout states
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [showRightSidebar, setShowRightSidebar] = useState(false)
  const [showAiDiagnosticsOpen, setShowAiDiagnosticsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isTogglingAi, setIsTogglingAi] = useState(false)
  const [isResettingAiMemory, setIsResettingAiMemory] = useState(false)
  const [resetTarget, setResetTarget] = useState<ResetTarget | null>(null)

  const [attachment, setAttachment] = useState<File | null>(null)
  const [attachmentPreview, setAttachmentPreview] = useState<string | null>(null)
  const [attachmentMediaType, setAttachmentMediaType] = useState<CommsMediaType | null>(null)
  const [attachmentIsVoice, setAttachmentIsVoice] = useState(false)
  const [isRecordingVoice, setIsRecordingVoice] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recordingChunksRef = useRef<Blob[]>([])
  const recordingTimerRef = useRef<number | null>(null)
  const activeChannelRef = useRef<ConversationChannel>('telegram')
  const suppressDraftSaveRef = useRef(false)

  const clearRecordingTimer = () => {
    if (recordingTimerRef.current !== null) {
      window.clearInterval(recordingTimerRef.current)
      recordingTimerRef.current = null
    }
  }

  const setAttachmentFromFile = (file: File, isVoice = false) => {
    const nextMediaType = inferFileMediaType(file)
    const composerChannel = activeChannelRef.current
    if (composerChannel === 'instagram' && nextMediaType === 'audio') {
      toast.error('Instagram API не поддерживает отправку аудио и голосовых через Direct')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      return
    }
    if (composerChannel === 'whatsapp' && nextMediaType === 'audio' && file.type.startsWith('audio/webm')) {
      toast.error('WhatsApp обычно не принимает audio/webm. Загрузите .ogg, .mp3 или .m4a')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      return
    }

    if (attachmentPreview) {
      URL.revokeObjectURL(attachmentPreview)
    }
    setAttachment(file)
    setAttachmentMediaType(nextMediaType)
    setAttachmentIsVoice(isVoice)
    setAttachmentPreview(URL.createObjectURL(file))
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setAttachmentFromFile(file)
    }
  }

  const handleRemoveAttachment = () => {
    if (attachmentPreview) {
      URL.revokeObjectURL(attachmentPreview)
    }
    setAttachment(null)
    setAttachmentPreview(null)
    setAttachmentMediaType(null)
    setAttachmentIsVoice(false)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleStartVoiceRecording = async () => {
    const composerChannel = activeChannelRef.current
    if (composerChannel === 'instagram') {
      toast.error('Instagram API не поддерживает отправку голосовых через Direct')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      toast.error('Запись голоса не поддерживается в этом браузере')
      return
    }

    try {
      const recorderMimeType = getPreferredRecorderMimeType(composerChannel)
      if (composerChannel === 'whatsapp' && !recorderMimeType) {
        toast.error('Ваш браузер не умеет записывать голос в формате, который принимает WhatsApp')
        return
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = recorderMimeType
        ? new MediaRecorder(stream, { mimeType: recorderMimeType })
        : new MediaRecorder(stream)
      recordingChunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordingChunksRef.current.push(event.data)
        }
      }
      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm'
        const blob = new Blob(recordingChunksRef.current, { type: mimeType })
        const extension = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('mp4') ? 'm4a' : 'webm'
        const file = new File([blob], `voice-message.${extension}`, { type: mimeType })
        setAttachmentFromFile(file, mimeType.includes('ogg'))
        stream.getTracks().forEach((track) => track.stop())
        recordingChunksRef.current = []
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setIsRecordingVoice(true)
      setRecordingSeconds(0)
      clearRecordingTimer()
      recordingTimerRef.current = window.setInterval(() => {
        setRecordingSeconds((seconds) => seconds + 1)
      }, 1000)
    } catch {
      toast.error('Не удалось получить доступ к микрофону')
    }
  }

  const handleStopVoiceRecording = () => {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
    setIsRecordingVoice(false)
    clearRecordingTimer()
  }

  useEffect(() => {
    return () => {
      clearRecordingTimer()
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop()
      }
      if (attachmentPreview) {
        URL.revokeObjectURL(attachmentPreview)
      }
    }
  }, [attachmentPreview])

  // Channel override for leads with multiple communication channels
  const [overrideChannel, setOverrideChannel] = useState<ConversationChannel | null>(null)

  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const handledLeadSearchRef = useRef<string | null>(null)

  // Fetch integration statuses
  const { data: telegramStatus } = useQuery({
    queryKey: ['telegram-integration-status'],
    queryFn: fetchTelegramIntegrationStatus,
  })

  const { data: instagramStatus } = useQuery({
    queryKey: ['instagram-status', user?.current_organization_slug ?? ''],
    queryFn: fetchInstagramStatus,
    enabled: !!user,
  })

  const { data: whatsappStatus } = useQuery({
    queryKey: ['whatsapp-integration-status'],
    queryFn: fetchWhatsAppIntegrationStatus,
  })

  // Fetch all leads
  const { data: leads = [] } = useQuery({
    queryKey: ['leads'],
    queryFn: () => fetchLeads(),
    refetchInterval: 5000,
  })

  const { data: organizations = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: fetchOrganizations,
    enabled: !!user,
  })

  const currentOrganization = organizations.find((organization) => organization.slug === user?.current_organization_slug)
  const internalToolsVisibility = getInternalToolsVisibilitySettings(currentOrganization?.org_settings)
  const showAiDiagnostics = internalToolsVisibility.showAiDiagnostics
  const showResetAiMemory = internalToolsVisibility.showResetAiMemory

  // Reset override channel when selecting a different lead
  useEffect(() => {
    if (!requestedChannel) {
      setOverrideChannel(null)
    }
  }, [selectedLead?.id, requestedChannel])

  // Fetch unread count map
  const { data: unreadData } = useQuery({
    queryKey: ['communications-unread-counts'],
    queryFn: fetchCommunicationsUnreadCounts,
    refetchInterval: 5000,
    networkMode: 'always',
  })
  const unreadCounts = unreadData?.counts ?? {}

  const getUnread = (leadId: number, channel: string) =>
    unreadCounts[String(leadId)]?.[channel] ?? 0

  const getLeadTotalUnread = (leadId: number) => {
    const tg = getUnread(leadId, 'telegram')
    const ig = getUnread(leadId, 'instagram')
    const wa = getUnread(leadId, 'whatsapp')
    return tg + ig + wa
  }

  // Fetch activities of the selected lead
  const { data: activities = [], refetch: refetchActivities } = useQuery({
    queryKey: ['lead-activities', selectedLead?.id],
    queryFn: () => selectedLead ? fetchLeadActivities(selectedLead.id) : Promise.resolve([]),
    enabled: !!selectedLead,
    refetchInterval: 3000,
  })

  // Determine active channel type for sending message
  const getLeadActiveChannel = (lead: Lead): ConversationChannel => {
    if (activeChannelTab !== 'all') return activeChannelTab

    // Check computed last contact channel from backend
    if (lead.last_contact_channel?.channel) {
      const lowerChannel = lead.last_contact_channel.channel.toLowerCase()
      if (lowerChannel === 'telegram') return 'telegram'
      if (lowerChannel === 'instagram') return 'instagram'
      if (lowerChannel === 'whatsapp') return 'whatsapp'
    }

    if (lead.telegram_chat_id) return 'telegram'
    if (lead.whatsapp_phone) return 'whatsapp'
    if (lead.instagram_user_id) return 'instagram'
    return 'telegram'
  }

  // Find all configured channels for the selected lead
  const availableChannels = useMemo(() => {
    if (!selectedLead) return []
    const channels: ConversationChannel[] = []
    if (selectedLead.telegram_chat_id) channels.push('telegram')
    if (selectedLead.whatsapp_phone) channels.push('whatsapp')
    if (selectedLead.instagram_user_id) channels.push('instagram')
    return channels
  }, [selectedLead])

  // Resolve active channel, taking manual overrides into account
  const activeChannel = useMemo(() => {
    if (!selectedLead) return 'telegram'
    if (overrideChannel && availableChannels.includes(overrideChannel)) {
      return overrideChannel
    }
    return getLeadActiveChannel(selectedLead)
  }, [selectedLead, overrideChannel, availableChannels, activeChannelTab])
  const canRecordVoice = canRecordVoiceForChannel(activeChannel)

  activeChannelRef.current = activeChannel

  const conversationDraftKey = selectedLead ? getConversationDraftKey(selectedLead.id, activeChannel) : null

  useEffect(() => {
    if (!conversationDraftKey) {
      suppressDraftSaveRef.current = true
      setMessage('')
      window.setTimeout(() => {
        suppressDraftSaveRef.current = false
      }, 0)
      return
    }

    suppressDraftSaveRef.current = true
    setMessage(localStorage.getItem(conversationDraftKey) ?? '')
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null
      recorder.stop()
      recorder.stream.getTracks().forEach((track) => track.stop())
    }
    mediaRecorderRef.current = null
    recordingChunksRef.current = []
    clearRecordingTimer()
    setIsRecordingVoice(false)
    setRecordingSeconds(0)
    setAttachmentPreview((preview) => {
      if (preview) {
        URL.revokeObjectURL(preview)
      }
      return null
    })
    setAttachment(null)
    setAttachmentMediaType(null)
    setAttachmentIsVoice(false)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    window.setTimeout(() => {
      suppressDraftSaveRef.current = false
    }, 0)
  }, [conversationDraftKey])

  useEffect(() => {
    if (!conversationDraftKey) return
    if (suppressDraftSaveRef.current) return

    if (message.trim()) {
      localStorage.setItem(conversationDraftKey, message)
    } else {
      localStorage.removeItem(conversationDraftKey)
    }
  }, [conversationDraftKey, message])

  // Filter messages based on active channel
  const conversationMessages = useMemo(() => {
    return activities.filter(activity => {
      if (activeChannel === 'telegram') {
        return activity.activity_type === 'telegram_sent' || activity.activity_type === 'telegram_received'
      }
      if (activeChannel === 'instagram') {
        return activity.activity_type === 'instagram_sent' || activity.activity_type === 'instagram_received'
      }
      if (activeChannel === 'whatsapp') {
        return activity.activity_type === 'whatsapp_sent' || activity.activity_type === 'whatsapp_received'
      }
      return false
    })
  }, [activities, activeChannel])

  const orderedMessages = useMemo(
    () => sortActivitiesChronologically(conversationMessages),
    [conversationMessages]
  )

  // Scroll logic
  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }

  const scrollAnchorIntoView = () => {
    if (messagesEndRef.current) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' })
      })
    }
  }

  useEffect(() => {
    scrollToBottom()
    scrollAnchorIntoView()
    const timer = setTimeout(() => {
      scrollToBottom()
      scrollAnchorIntoView()
    }, 150)
    return () => clearTimeout(timer)
  }, [orderedMessages, selectedLead?.id, activeChannel])

  // Exclude own instagram account from lists
  const isOwnInstagram = (lead: Lead) => {
    return !!(lead.instagram_user_id &&
      instagramStatus?.instagram_username &&
      lead.instagram_username === instagramStatus.instagram_username)
  }

  // Sorting and Filtering of Leads List
  const sortedLeads = useMemo(() => {
    return [...leads].sort((a, b) => {
      if (!a.last_contacted && !b.last_contacted) return 0
      if (!a.last_contacted) return 1
      if (!b.last_contacted) return -1
      return new Date(b.last_contacted).getTime() - new Date(a.last_contacted).getTime()
    })
  }, [leads])

  const filteredLeads = useMemo(() => {
    return sortedLeads.filter(lead => {
      // Exclude own instagram account
      if (isOwnInstagram(lead)) return false

      // In the 'All' tab, only show leads that have at least one active communication channel
      if (activeChannelTab === 'all' && !lead.telegram_chat_id && !lead.whatsapp_phone && !lead.instagram_user_id) {
        return false
      }

      // 1. Channel Filter
      if (activeChannelTab === 'telegram' && !lead.telegram_chat_id) return false
      if (activeChannelTab === 'instagram' && !lead.instagram_user_id) return false
      if (activeChannelTab === 'whatsapp' && !lead.whatsapp_phone) return false

      // 2. Status Filter
      const totalUnread = getLeadTotalUnread(lead.id)
      if (activeStatusFilter === 'unread' && totalUnread === 0) return false
      if (activeStatusFilter === 'paused' && !lead.ai_paused) return false
      if (activeStatusFilter === 'active' && lead.ai_paused) return false

      // 3. Search Query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        const matchName = lead.contact_person?.toLowerCase().includes(query)
        const matchTg = lead.telegram_username?.toLowerCase().includes(query)
        const matchIg = lead.instagram_username?.toLowerCase().includes(query)
        const matchPhone = lead.phone?.toLowerCase().includes(query) || lead.whatsapp_phone?.toLowerCase().includes(query)
        return matchName || matchTg || matchIg || matchPhone
      }

      return true
    })
  }, [sortedLeads, activeChannelTab, activeStatusFilter, searchQuery, unreadCounts, instagramStatus])

  // Handle lead selection
  const handleSelectLead = (lead: Lead) => {
    setSelectedLead(lead)

    // Determine active channels to mark as read
    const channels: ConversationChannel[] = []
    if (lead.telegram_chat_id) channels.push('telegram')
    if (lead.instagram_user_id) channels.push('instagram')
    if (lead.whatsapp_phone) channels.push('whatsapp')

    channels.forEach(channel => {
      const count = getUnread(lead.id, channel)
      if (count > 0) {
        markCommunicationsRead(lead.id, channel).then(() => {
          queryClient.invalidateQueries({ queryKey: ['communications-unread-counts'] })
        }).catch(console.error)
      }
    })
  }

  useEffect(() => {
    if (!requestedLeadId || leads.length === 0) return

    const requestKey = `${requestedLeadId}:${requestedChannel ?? ''}`
    if (handledLeadSearchRef.current === requestKey) return

    const targetLead = leads.find((lead) => String(lead.id) === requestedLeadId)
    if (!targetLead) return

    setActiveChannelTab('all')
    handleSelectLead(targetLead)
    if (requestedChannel) {
      setOverrideChannel(requestedChannel)
    }
    handledLeadSearchRef.current = requestKey
  }, [requestedLeadId, requestedChannel, leads])

  // Toggle AI agent control
  const handleToggleAiPause = async (lead: Lead) => {
    setIsTogglingAi(true)
    try {
      const updated = await toggleAiPause(lead.id)
      setSelectedLead(updated)
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      toast.success(updated.ai_paused ? 'Диалог переведен на ручной контроль' : 'ИИ-агент успешно перезапущен')
    } catch {
      toast.error('Не удалось переключить режим управления')
    } finally {
      setIsTogglingAi(false)
    }
  }

  // Reset AI memory handler
  const handleResetAiMemory = async (target: ResetTarget) => {
    setIsResettingAiMemory(true)
    try {
      const response = await resetLeadAiMemory(target.lead.id)
      setSelectedLead(response.lead)
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', target.lead.id] })
      toast.success(`Контекст ИИ для ${response.lead.contact_person} успешно очищен. История переписки сохранена.`)
      setResetTarget(null)
    } catch {
      toast.error('Не удалось сбросить память ИИ для этого диалога')
    } finally {
      setIsResettingAiMemory(false)
    }
  }

  // Send message router
  const handleSendMessage = async () => {
    if (!selectedLead || (!message.trim() && !attachment)) {
      toast.error('Пожалуйста, введите сообщение или прикрепите фото')
      return
    }

    setIsSending(true)
    try {
      let fileUrl: string | undefined = undefined
      let mediaType: CommsMediaType | undefined = attachmentMediaType ?? undefined
      if (attachment) {
        const uploadRes = await uploadCommsMedia(attachment)
        if (uploadRes && uploadRes.success) {
          fileUrl = uploadRes.file_url
          mediaType = uploadRes.media_type || mediaType
        } else {
          throw new Error('Не удалось загрузить медиафайл на сервер')
        }
      }

      let response
      if (activeChannel === 'telegram') {
        response = await sendTelegramMessageFromComms(selectedLead.id, message, fileUrl, mediaType, attachmentIsVoice)
      } else if (activeChannel === 'instagram') {
        response = await sendInstagramMessageFromComms(selectedLead.id, message, fileUrl, mediaType, attachmentIsVoice)
      } else if (activeChannel === 'whatsapp') {
        response = await sendWhatsAppMessageFromComms(selectedLead.id, message, fileUrl, mediaType, attachmentIsVoice)
      }

      if (response?.success) {
        toast.success('Сообщение успешно отправлено')
        if (conversationDraftKey) {
          localStorage.removeItem(conversationDraftKey)
        }
        setMessage('')
        handleRemoveAttachment()
        await refetchActivities()
      } else {
        toast.error(response?.error || 'Не удалось отправить сообщение')
      }
    } catch (error) {
      if (error instanceof ApiError) {
        const errorData = error.data as any
        toast.error(errorData?.error || 'Не удалось отправить сообщение')
      } else {
        toast.error('Не удалось отправить сообщение. Пожалуйста, попробуйте еще раз.')
      }
    } finally {
      setIsSending(false)
    }
  }

  // Formatter for lead last active time
  const formatLastActive = (dateStr?: string | null) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)

    if (diffMin < 1) return 'Только что'
    if (diffMin < 60) return `${diffMin} мин назад`

    const diffHours = Math.floor(diffMin / 60)
    if (diffHours < 24) return `${diffHours} ч назад`

    return date.toLocaleDateString('ru-RU', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="flex flex-1 flex-col min-h-0 overflow-hidden">

      {/* Upper Title Panel */}
      <div className="border-b bg-card px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-lg sm:text-xl font-bold tracking-tight">Единый Центр Сообщений</h1>
          <p className="text-xs text-muted-foreground">
            Управление общением с гостями в Telegram, WhatsApp и Instagram с поддержкой ИИ-ассистента
          </p>
        </div>
      </div>

      {/* Main Unified Workspace */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        
        {/* Left Column: Unified Leads List & Search.
             On mobile: full-width and hidden when a lead is selected (chat view).
             On md+: fixed 280px sidebar always visible. */}
        <div className={`shrink-0 border-r bg-background flex flex-col h-full min-h-0 overflow-hidden ${
          selectedLead ? 'hidden md:flex md:w-[280px]' : 'flex w-full md:w-[280px]'
        }`}>

          {/* Channel Filters */}
          <div className="p-3 border-b space-y-2.5">
            <div className="flex rounded-lg bg-muted p-0.5 w-full">
              <button
                onClick={() => setActiveChannelTab('all')}
                className={`flex-1 text-[11px] font-semibold py-1.5 rounded-md transition-all ${activeChannelTab === 'all' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                Все
              </button>
              <button
                onClick={() => setActiveChannelTab('telegram')}
                className={`flex-1 text-[11px] font-semibold py-1.5 rounded-md transition-all flex items-center justify-center gap-1 ${activeChannelTab === 'telegram' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <span title="Telegram" className="shrink-0 flex items-center gap-1">
                  <MessageSquareIcon className="h-3 w-3 text-blue-500" />
                  TG
                </span>
              </button>
              <button
                onClick={() => setActiveChannelTab('whatsapp')}
                className={`flex-1 text-[11px] font-semibold py-1.5 rounded-md transition-all flex items-center justify-center gap-1 ${activeChannelTab === 'whatsapp' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <span title="WhatsApp" className="shrink-0 flex items-center gap-1">
                  <PhoneIcon className="h-3 w-3 text-green-500" />
                  WA
                </span>
              </button>
              <button
                onClick={() => setActiveChannelTab('instagram')}
                className={`flex-1 text-[11px] font-semibold py-1.5 rounded-md transition-all flex items-center justify-center gap-1 ${activeChannelTab === 'instagram' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <span title="Instagram" className="shrink-0 flex items-center gap-1">
                  <InstagramIcon className="h-3 w-3 text-pink-500" />
                  IG
                </span>
              </button>
            </div>

            {/* Status filters */}
            <div className="flex items-center justify-between gap-1">
              <button
                onClick={() => setActiveStatusFilter('all')}
                className={`text-[10px] font-bold px-2 py-1 rounded border transition-all ${activeStatusFilter === 'all' ? 'bg-primary/5 border-primary/20 text-primary' : 'bg-transparent border-transparent text-muted-foreground hover:text-foreground'
                  }`}
              >
                Все
              </button>
              <button
                onClick={() => setActiveStatusFilter('unread')}
                className={`text-[10px] font-bold px-2 py-1 rounded border transition-all flex items-center gap-1 ${activeStatusFilter === 'unread' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-transparent border-transparent text-muted-foreground hover:text-foreground'
                  }`}
              >
                Новые
              </button>
              <button
                onClick={() => setActiveStatusFilter('paused')}
                className={`text-[10px] font-bold px-2 py-1 rounded border transition-all flex items-center gap-1 ${activeStatusFilter === 'paused' ? 'bg-amber-50 border-amber-200 text-amber-700' : 'bg-transparent border-transparent text-muted-foreground hover:text-foreground'
                  }`}
              >
                Ручной
              </button>
              <button
                onClick={() => setActiveStatusFilter('active')}
                className={`text-[10px] font-bold px-2 py-1 rounded border transition-all flex items-center gap-1 ${activeStatusFilter === 'active' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-transparent border-transparent text-muted-foreground hover:text-foreground'
                  }`}
              >
                ИИ
              </button>
            </div>

            {/* Search Input */}
            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Поиск по имени или телефону..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 h-9 text-xs"
              />
            </div>
          </div>

          {/* Leads scrollable area */}
          <ScrollArea className="flex-1 min-h-0">
            {filteredLeads.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground">
                Диалоги не найдены
              </div>
            ) : (
              <div className="divide-y">
                {filteredLeads.map((lead) => {
                  const unread = getLeadTotalUnread(lead.id)
                  const isSelected = selectedLead?.id === lead.id

                  return (
                    <button
                      key={lead.id}
                      onClick={() => handleSelectLead(lead)}
                      className={`w-full p-3.5 text-left transition-all hover:bg-muted/50 flex flex-col gap-1 border-l-4 outline-none ${isSelected
                          ? 'bg-muted border-primary'
                          : 'border-transparent bg-transparent'
                        }`}
                    >
                      <div className="flex items-start justify-between gap-1 w-full min-w-0">
                        <span className={`text-xs font-semibold truncate flex-1 ${unread > 0 ? 'text-foreground' : 'text-muted-foreground'}`}>
                          {lead.contact_person}
                        </span>
                        <span className="text-[10px] text-muted-foreground shrink-0">
                          {formatLastActive(lead.last_contacted)}
                        </span>
                      </div>

                      {/* Details & Status badges */}
                      <div className="flex items-center justify-between w-full mt-0.5">
                        <div className="flex items-center gap-1.5 min-w-0">
                          {/* Channel indicators */}
                          {lead.telegram_chat_id && (
                            <span title={`Telegram: @${lead.telegram_username || '-'}`} className="shrink-0">
                              <MessageSquareIcon className="h-3.5 w-3.5 text-blue-400" />
                            </span>
                          )}
                          {lead.whatsapp_phone && (
                            <span title={`WhatsApp: ${lead.whatsapp_phone}`} className="shrink-0">
                              <PhoneIcon className="h-3.5 w-3.5 text-green-400" />
                            </span>
                          )}
                          {lead.instagram_user_id && (
                            <span title={`Instagram: @${lead.instagram_username || '-'}`} className="shrink-0">
                              <InstagramIcon className="h-3.5 w-3.5 text-pink-400" />
                            </span>
                          )}

                          {/* AI state dots */}
                          {lead.ai_paused ? (
                            <Badge className="h-4 px-1 bg-amber-500/10 border-amber-500/20 text-amber-600 hover:bg-amber-500/10 text-[9px] gap-0.5 font-bold">
                              <HandIcon className="h-2 w-2" /> Ручной
                            </Badge>
                          ) : (
                            <Badge className="h-4 px-1 bg-green-500/10 border-green-500/20 text-green-600 hover:bg-green-500/10 text-[9px] gap-0.5 font-bold">
                              <BotIcon className="h-2 w-2" /> ИИ
                            </Badge>
                          )}

                          {lead.discovery_source && (
                            <LeadSourceBadge source={lead.discovery_source} className="h-4 px-1 text-[8px] shrink-0" />
                          )}
                        </div>

                        {/* Unread badge */}
                        {unread > 0 && (
                          <span className="flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white leading-none">
                            {unread}
                          </span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Center Column: Chat Window. Takes all remaining space. */}
        <div className={`flex-1 min-w-0 bg-muted/20 flex flex-col h-full overflow-hidden ${selectedLead ? 'flex' : 'hidden md:flex'}`}>
          {selectedLead ? (
            <>
              {/* Chat Header */}
              <div className="border-b bg-card px-4 py-3 flex items-center justify-between flex-wrap gap-2">
                {/* Mobile: back button to return to leads list */}
                <button
                  className="md:hidden flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mr-1 shrink-0"
                  onClick={() => setSelectedLead(null)}
                >
                  <ArrowLeftIcon className="h-4 w-4" />
                </button>
                <div className="min-w-0 flex items-center flex-wrap gap-2">
                  <h2 className="text-sm font-bold truncate">{selectedLead.contact_person}</h2>

                  {/* Channel Quick Switcher for leads with multiple communication channels */}
                  {availableChannels.length > 1 && (
                    <div className="flex items-center rounded-md bg-muted p-0.5 border border-muted-foreground/10 shrink-0">
                      {availableChannels.map(ch => (
                        <button
                          key={ch}
                          onClick={() => setOverrideChannel(ch)}
                          className={`px-2 py-0.5 text-[9px] font-bold rounded-sm transition-all flex items-center gap-1 ${activeChannel === ch
                              ? 'bg-background shadow text-foreground'
                              : 'text-muted-foreground hover:text-foreground'
                            }`}
                        >
                          {ch === 'telegram' && <><MessageSquareIcon className="h-2.5 w-2.5 text-blue-500" /> TG</>}
                          {ch === 'instagram' && <><InstagramIcon className="h-2.5 w-2.5 text-pink-500" /> IG</>}
                          {ch === 'whatsapp' && <><PhoneIcon className="h-2.5 w-2.5 text-green-500" /> WA</>}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Fallback Single Channel Badges */}
                  {availableChannels.length <= 1 && (
                    <div className="flex items-center gap-1.5">
                      {selectedLead.telegram_chat_id && (
                        <Badge variant="outline" className="text-[9px] py-0 border-blue-200 text-blue-700 bg-blue-50/50 gap-1 font-semibold">
                          <MessageSquareIcon className="h-2.5 w-2.5" /> TG {selectedLead.telegram_username ? `@${selectedLead.telegram_username}` : ''}
                        </Badge>
                      )}
                      {selectedLead.whatsapp_phone && (
                        <Badge variant="outline" className="text-[9px] py-0 border-green-200 text-green-700 bg-green-50/50 gap-1 font-semibold">
                          <PhoneIcon className="h-2.5 w-2.5" /> WA {selectedLead.whatsapp_phone}
                        </Badge>
                      )}
                      {selectedLead.instagram_user_id && (
                        <Badge variant="outline" className="text-[9px] py-0 border-pink-200 text-pink-700 bg-pink-50/50 gap-1 font-semibold">
                          <InstagramIcon className="h-2.5 w-2.5" /> IG {selectedLead.instagram_username ? `@${selectedLead.instagram_username}` : ''}
                        </Badge>
                      )}
                    </div>
                  )}
                </div>

                {/* AI / Manual Controls */}
                <div className="flex items-center gap-2 shrink-0">

                  {/* Status Banner Card */}
                  <div className={`hidden sm:flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${selectedLead.ai_paused
                      ? 'bg-amber-50 border-amber-200 text-amber-700'
                      : 'bg-green-50 border-green-200 text-green-700'
                    }`}>
                    {selectedLead.ai_paused ? (
                      <span className="flex items-center gap-1"><HandIcon className="h-3.5 w-3.5" /> Ручной режим · ИИ ведет карточку</span>
                    ) : (
                      <span className="flex items-center gap-1"><BotIcon className="h-3.5 w-3.5" /> Ассистент активен</span>
                    )}
                  </div>

                  {/* Toggle Control Button */}
                  <Button
                    size="sm"
                    disabled={isTogglingAi}
                    className={`h-8 text-xs gap-1.5 px-2 sm:px-3 ${selectedLead.ai_paused
                        ? 'bg-green-600 hover:bg-green-700 text-white'
                        : 'border border-amber-400 bg-transparent text-amber-700 hover:bg-amber-50'
                      }`}
                    onClick={() => handleToggleAiPause(selectedLead)}
                  >
                    {selectedLead.ai_paused ? (
                      <>
                        <PlayIcon className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Включить ИИ</span>
                        <span className="sm:hidden">ИИ</span>
                      </>
                    ) : (
                      <>
                        <HandIcon className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Перехватить</span>
                        <span className="sm:hidden">Ручной</span>
                      </>
                    )}
                  </Button>

                  {/* Logs toggle - only shown if org setting allows AI diagnostics */}
                  {showAiDiagnostics && (
                    <Button
                      variant="outline"
                      size="sm"
                      className={`h-8 gap-1 text-xs px-2 sm:px-3 ${showAiDiagnosticsOpen ? 'bg-primary/5 text-primary border-primary/20' : ''}`}
                      onClick={() => setShowAiDiagnosticsOpen(!showAiDiagnosticsOpen)}
                    >
                      <ScrollTextIcon className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">Логи</span>
                    </Button>
                  )}

                  {/* Right Sidebar toggle */}
                  <Button
                    variant="outline"
                    size="sm"
                    className={`h-8 gap-1 text-xs px-2 sm:px-3 ${showRightSidebar ? 'bg-primary/5 text-primary border-primary/20' : ''}`}
                    onClick={() => setShowRightSidebar(!showRightSidebar)}
                  >
                    <SlidersHorizontalIcon className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Карточка</span>
                  </Button>
                </div>
              </div>

              {/* AI Diagnostic Step reasoning panel - shown only when toggled on */}
              {showAiDiagnostics && showAiDiagnosticsOpen && (
                <AiDiagnosticsPanel activities={orderedMessages} channelLabel={activeChannel.toUpperCase()} />
              )}

              {/* Message Timeline (using min-h-0 and flex-1 to let Flexbox limit height inside viewport) */}
              <ScrollArea className="flex-1 min-h-0 p-4" ref={scrollAreaRef}>
                <div className="space-y-4">
                  {orderedMessages.length === 0 ? (
                    <div className="text-center text-xs text-muted-foreground py-10 flex flex-col items-center gap-2">
                      <InfoIcon className="h-8 w-8 text-muted-foreground/50" />
                      Начните диалог с гостем. История сообщений в выбранном канале пока пуста.
                    </div>
                  ) : (
                    orderedMessages.map((activity) => {
                      // Routing channel properties
                      const isTelegram = activity.activity_type.startsWith('telegram')
                      const isInstagram = activity.activity_type.startsWith('instagram')
                      const isWhatsApp = activity.activity_type.startsWith('whatsapp')

                      const isSent = activity.activity_type.endsWith('_sent')

                      // Message content resolution
                      let messageText = ''
                      if (isTelegram) {
                        messageText = getTelegramMessageText(activity)
                      } else if (isInstagram || isWhatsApp) {
                        messageText = activity.metadata?.text as string || ''
                      }

                      // Filter out developer stubs / system notifications so they don't render as text bubbles
                      const lowerText = messageText.toLowerCase().trim()
                      const isPlaceholder =
                        lowerText === '[image received]' ||
                        lowerText === '[sticker received]' ||
                        lowerText === '[attachment received]' ||
                        lowerText === '[audio received]' ||
                        lowerText === '[video received]' ||
                        lowerText === '[file received]' ||
                        lowerText === '[изображение получено]' ||
                        lowerText === '[стикер получен]' ||
                        lowerText === '[аудио получено]' ||
                        lowerText === '[видео получено]' ||
                        lowerText === '[файл получен]' ||
                        lowerText === '[получено: image]' ||
                        lowerText === '[получено: video]' ||
                        lowerText === '[получено: audio]' ||
                        lowerText === 'received photo from whatsapp' ||
                        lowerText === 'received video from whatsapp' ||
                        lowerText === 'received audio from whatsapp' ||
                        lowerText === 'received telegram photo' ||
                        lowerText === 'received telegram video' ||
                        lowerText === 'received telegram audio' ||
                        lowerText.startsWith('received photo from') ||
                        lowerText.startsWith('received video from') ||
                        lowerText.startsWith('received audio from')

                      if (isPlaceholder) {
                        messageText = ''
                      } else if (!messageText && !activity.metadata?.media_type) {
                        // For non-media activities (e.g. status updates, notes), fallback to description
                        messageText = activity.description
                      }

                      const mediaType = activity.metadata?.media_type as string | undefined
                      const fileUrl = activity.metadata?.file_url as string | undefined
                      const fileUrls = activity.metadata?.file_urls as string[] | undefined
                      const mediaTitle = activity.metadata?.media_title as string | undefined
                      const fileName = activity.metadata?.file_name as string | undefined
                      const isVoice = Boolean(activity.metadata?.is_voice)
                      const rawMediaUrls = fileUrls && fileUrls.length > 0 ? fileUrls : (fileUrl ? [fileUrl] : [])
                      const mediaUrls = rawMediaUrls.map(resolveMediaUrl)

                      const timestamp = new Date(activity.created_at).toLocaleString('ru-RU', {
                        month: 'short',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                      })

                      const sentBy = isSent ? getSentBy(activity.metadata) : null

                      return (
                        <div
                          key={activity.id}
                          className={`flex ${isSent ? 'justify-end' : 'justify-start'}`}
                        >
                          <div
                            className={`max-w-[85%] sm:max-w-[70%] overflow-hidden rounded-2xl shadow-sm border ${isSent
                                ? activeChannel === 'instagram'
                                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 border-purple-600 text-white'
                                  : 'bg-primary border-primary text-primary-foreground'
                                : 'bg-card border-border text-foreground'
                              }`}
                          >
                            {/* Render attachments */}
                            {mediaType === 'photo' && mediaUrls.length > 0 && (
                              <div className="p-1.5">
                                {mediaUrls.length === 1 ? (
                                  <img
                                    src={mediaUrls[0]}
                                    alt={mediaTitle || 'Фото'}
                                    className="max-h-60 rounded-xl object-cover"
                                  />
                                ) : (
                                  <div className="grid gap-1 grid-cols-2 max-w-[280px]">
                                    {mediaUrls.slice(0, 4).map((url, idx) => (
                                      <img
                                        key={idx}
                                        src={url}
                                        alt={mediaTitle ? `${mediaTitle} ${idx + 1}` : `Фото ${idx + 1}`}
                                        className="h-28 w-full rounded-lg object-cover"
                                      />
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}

                            {mediaType === 'video' && mediaUrls.length > 0 && (
                              <div className="p-1.5">
                                <CustomVideoPlayer src={mediaUrls[0]} title={mediaTitle || fileName || 'Видео'} />
                              </div>
                            )}

                            {mediaType === 'audio' && mediaUrls.length > 0 && (
                              <div className="p-2.5 min-w-[240px]">
                                <CustomAudioPlayer src={mediaUrls[0]} title={mediaTitle || fileName} isVoice={isVoice} />
                              </div>
                            )}

                            {mediaType === 'document' && mediaUrls.length > 0 && (
                              <div className="p-2.5">
                                <a
                                  href={mediaUrls[0]}
                                  target="_blank"
                                  rel="noreferrer"
                                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${isSent
                                      ? 'border-white/25 bg-white/10 text-white hover:bg-white/15'
                                      : 'border-border bg-muted/40 text-foreground hover:bg-muted'
                                    }`}
                                >
                                  <FileIcon className="h-4 w-4" />
                                  <span className="max-w-[260px] truncate">{fileName || mediaTitle || 'Открыть файл'}</span>
                                </a>
                              </div>
                            )}

                            {/* Text message */}
                            {messageText && (
                              <div className="px-4 py-2.5">
                                <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">{messageText}</p>
                              </div>
                            )}

                            {/* Footer info (sender, channel icon, timestamp) */}
                            <div className="px-3 pb-1.5 flex items-center justify-end gap-1.5 text-[10px] select-none">
                              {isTelegram && <span title="Telegram" className="shrink-0"><MessageSquareIcon className="h-3 w-3 text-sky-400" /></span>}
                              {isWhatsApp && <span title="WhatsApp" className="shrink-0"><PhoneIcon className="h-3 w-3 text-green-400" /></span>}
                              {isInstagram && <span title="Instagram" className="shrink-0"><InstagramIcon className="h-3 w-3 text-pink-400" /></span>}

                              {sentBy && (
                                <span className={`font-semibold ${isSent ? 'text-primary-foreground/60' : 'text-muted-foreground'}`}>
                                  {sentBy}
                                </span>
                              )}
                              <span className={isSent ? 'text-primary-foreground/75' : 'text-muted-foreground'}>
                                {timestamp}
                              </span>
                            </div>
                          </div>
                        </div>
                      )
                    })
                  )}
                  <div ref={messagesEndRef} aria-hidden="true" />
                </div>
              </ScrollArea>

              {/* Chat Input Workspace */}
              <div className="border-t bg-card p-4 space-y-3 shrink-0">

                {/* AI Co-pilot Suggestions Area (if AI paused) */}
                {selectedLead.ai_paused && (
                  <CopilotSuggestions
                    key={`${selectedLead.id}:${activeChannel}`}
                    leadId={selectedLead.id}
                    onSelectSuggestion={(text) => setMessage(text)}
                  />
                )}

                {/* Templates and Quick utilities */}
                <div className="flex flex-wrap items-center gap-2">
                  <QuickRepliesPopover channel={activeChannel} onSelectTemplate={(text) => setMessage(prev => prev + text)} />

                  {/* Emoji Picker */}
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" size="sm" className="h-8 gap-1.5 text-muted-foreground hover:text-foreground">
                        <SmileIcon className="h-4 w-4" />
                        Эмодзи
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-72 p-2" align="start" side="top">
                      <div className="grid grid-cols-8 gap-1">
                        {COMMON_EMOJIS.map((emoji) => (
                          <button
                            key={emoji}
                            onClick={() => setMessage(prev => prev + emoji)}
                            className="text-lg hover:bg-muted rounded p-1 transition-colors outline-none focus-visible:ring-1 focus-visible:ring-primary"
                          >
                            {emoji}
                          </button>
                        ))}
                      </div>
                    </PopoverContent>
                  </Popover>

                  {/* Attach File Button */}
                  {(activeChannel === 'telegram' || activeChannel === 'whatsapp' || activeChannel === 'instagram') && (
                    <>
                      <input
                        type="file"
                        accept="image/*,video/*,audio/*"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        className="hidden"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        className={`h-8 gap-1.5 ${attachment ? 'text-primary border-primary bg-primary/5' : 'text-muted-foreground hover:text-foreground'}`}
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <PaperclipIcon className="h-4 w-4" />
                        Медиа
                      </Button>

                      {canRecordVoice && (
                        <Button
                          variant={isRecordingVoice ? 'default' : 'outline'}
                          size="sm"
                          className={`h-8 gap-1.5 ${isRecordingVoice ? 'bg-red-600 text-white hover:bg-red-700' : 'text-muted-foreground hover:text-foreground'}`}
                          onClick={isRecordingVoice ? handleStopVoiceRecording : handleStartVoiceRecording}
                          type="button"
                        >
                          {isRecordingVoice ? <SquareIcon className="h-4 w-4" /> : <MicIcon className="h-4 w-4" />}
                          {isRecordingVoice ? formatMediaTime(recordingSeconds) : 'Голос'}
                        </Button>
                      )}
                    </>
                  )}
                </div>

                {/* Attachment Preview */}
                {attachmentPreview && (
                  <div className="relative inline-block max-w-[320px] overflow-hidden rounded-xl border bg-muted p-1 shadow-sm">
                    {attachmentMediaType === 'photo' && (
                      <img src={attachmentPreview} alt="Превью" className="max-h-28 rounded-lg object-cover" />
                    )}
                    {attachmentMediaType === 'video' && (
                      <div className="w-[280px]">
                        <CustomVideoPlayer src={attachmentPreview} title={attachment?.name || 'Видео'} />
                      </div>
                    )}
                    {attachmentMediaType === 'audio' && (
                      <CustomAudioPlayer src={attachmentPreview} title={attachment?.name} isVoice={attachmentIsVoice} />
                    )}
                    {attachmentMediaType === 'document' && (
                      <div className="flex min-w-[240px] items-center gap-2 rounded-lg bg-background px-3 py-2 text-sm">
                        <FileIcon className="h-4 w-4 text-muted-foreground" />
                        <span className="truncate">{attachment?.name || 'Файл'}</span>
                      </div>
                    )}
                    <button
                      onClick={handleRemoveAttachment}
                      className="absolute top-2 right-2 bg-background/80 hover:bg-background rounded-full p-1 shadow-sm transition-colors text-muted-foreground hover:text-foreground"
                      type="button"
                    >
                      <XIcon className="h-3 w-3" />
                    </button>
                  </div>
                )}

                {/* Chat text area input */}
                <div className="flex gap-2 items-end">
                  <div className="flex-1 relative">
                    <Textarea
                      placeholder="Напишите сообщение... (Shift+Enter для новой строки)"
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          void handleSendMessage()
                        }
                      }}
                      className="min-h-11 max-h-32 text-sm resize-none pr-8 py-2.5 leading-normal"
                    />
                  </div>
                  <Button
                    onClick={handleSendMessage}
                    disabled={(!message.trim() && !attachment) || isSending}
                    size="icon"
                    className="h-10 w-10 shrink-0 bg-primary hover:bg-primary/95 text-primary-foreground shadow"
                  >
                    <SendIcon className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-3">
              <MessageSquareIcon className="h-12 w-12 text-muted-foreground/45" />
              <div>
                <h3 className="font-semibold text-sm">Диалог не выбран</h3>
                <p className="text-xs text-muted-foreground mt-1 max-w-[280px]">
                  Выберите гостя в левом меню, чтобы начать переписку в Telegram, WhatsApp или Instagram.
                </p>
              </div>
            </div>
          )}
        </div>

          {/* Right Sidebar: Absolute overlay on mobile, inline flex column on desktop (md+) */}
          {selectedLead && showRightSidebar && (
            <div className="absolute right-0 top-0 bottom-0 w-full sm:w-[300px] md:relative md:top-auto md:bottom-auto md:right-auto md:w-[300px] md:shrink-0 bg-card border-l shadow-xl md:shadow-none z-20 h-full">
            <LeadDetailsSidebar
              lead={selectedLead}
              onClose={() => setShowRightSidebar(false)}
              showResetAiMemory={showResetAiMemory}
              isResettingAiMemory={isResettingAiMemory}
              onResetAiMemory={() => setResetTarget({ lead: selectedLead, channel: activeChannel })}
            />
          </div>
        )}

      </div>

      {/* Reset AI Memory Dialog */}
      <AlertDialog open={!!resetTarget} onOpenChange={(open) => { if (!open && !isResettingAiMemory) setResetTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Сбросить память ИИ для этого диалога?</AlertDialogTitle>
            <AlertDialogDescription>
              Это действие полностью очистит извлеченные параметры бронирования, цели, задачи и текущие возражения гостя в памяти ИИ.
              Сама переписка и карточка лида останутся без изменений.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isResettingAiMemory}>Отмена</AlertDialogCancel>
            <AlertDialogAction
              disabled={!resetTarget || isResettingAiMemory}
              onClick={() => {
                if (resetTarget) {
                  void handleResetAiMemory(resetTarget)
                }
              }}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              {isResettingAiMemory ? 'Сброс...' : 'Сбросить память ИИ'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  )
}
