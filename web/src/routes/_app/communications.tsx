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

function objectValue(value: unknown): Record<string, unknown> {

  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}

}



function stringValue(value: unknown): string {

  return typeof value === 'string' ? value.trim() : ''

}



function firstString(values: unknown[]): string {

  for (const value of values) {

    if (Array.isArray(value)) {

      const nested = firstString(value)

      if (nested) return nested

      continue

    }

    const text = stringValue(value)

    if (text) return text

  }

  return ''

}



function trimPreviewText(value: string, maxLength = 140): string {

  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}…` : value

}



function isRenderablePreviewUrl(value: string): boolean {

  const lower = value.toLowerCase()

  return Boolean(value)

    && !lower.includes('instagram.com/p/')

    && !lower.includes('instagram.com/reel/')

    && !lower.includes('instagram.com/stories/')

}



const INSTAGRAM_CONTENT_LABELS: Record<string, string> = {

  post: 'пост',

  story: 'сторис',

  reel: 'Reels',

  highlight: 'актуальное',

}



const ROOM_CATEGORY_LABELS: Record<string, string> = {

  standard_queen: 'Стандарт Квин',

  standard_twin: 'Стандарт Твин',

  comfort: 'Комфорт',

  family: 'Семейный',

  other: 'Другой номер',

}



const MEDIA_CATEGORY_LABELS: Record<string, string> = {

  rooms: 'Номера',

  cafeteria: 'Кафе',

  pool: 'Бассейн',

  spa: 'SPA',

  conference: 'Конференции',

  exterior: 'Территория',

  lobby: 'Лобби',

  other: 'Другое',

}



function getInstagramContextPreview(metadata: Record<string, unknown> | null) {

  if (!metadata) return null

  const mediaContext = objectValue(metadata.media_context)

  const instagramContext = objectValue(metadata.instagram_context)

  const hasInstagramContext = Object.keys(instagramContext).length > 0

  const hasMediaContext = Object.keys(mediaContext).length > 0

  if (!hasInstagramContext && !hasMediaContext) return null

  const source = stringValue(mediaContext.source)

  const contentType = stringValue(mediaContext.content_type) || stringValue(instagramContext.content_type)

  const contentLabel = INSTAGRAM_CONTENT_LABELS[contentType] || (contentType ? contentType : 'контент')

  const rawTitle = firstString([

    mediaContext.title,

    mediaContext.caption,

    instagramContext.title,

    instagramContext.caption,

  ]) || (source === 'hotel_media' ? 'Фото из медиабазы' : `Instagram ${contentLabel}`)

  const title = trimPreviewText(rawTitle)

  const roomCategory = stringValue(mediaContext.room_category)

  const category = stringValue(mediaContext.category)

  const confidence = typeof mediaContext.confidence === 'number' ? mediaContext.confidence : null

  const previewUrl = firstString([

    mediaContext.preview_url,

    mediaContext.thumbnail_url,

    mediaContext.media_url,

    mediaContext.photo_url,

    mediaContext.linked_media_url,

    instagramContext.thumbnail_url,

    instagramContext.media_url,

    instagramContext.story_url,

    instagramContext.share_url,

    instagramContext.urls,

  ])

  const linkUrl = firstString([

    mediaContext.permalink,

    instagramContext.permalink,

    instagramContext.share_url,

    instagramContext.story_url,

    instagramContext.urls,

  ])

  const badges = [

    roomCategory ? ROOM_CATEGORY_LABELS[roomCategory] || roomCategory : '',

    category ? MEDIA_CATEGORY_LABELS[category] || category : '',

    confidence !== null ? `${Math.round(confidence * 100)}%` : '',

  ].filter(Boolean)

  return {

    title,

    heading: source === 'hotel_media' ? 'Распознано по фото' : `Ответ на ${contentLabel}`,

    previewUrl: isRenderablePreviewUrl(previewUrl) ? resolveMediaUrl(previewUrl) : '',

    linkUrl,

    badges,

  }

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
  if (metadata.sent_via === 'native_app' || metadata.echo_origin === 'instagram_app') {
    return 'Менеджер · Instagram'
  }
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
    queryFn: () => fetchLeads({ include_non_sales: true }),
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
      const updated = await toggleAiPause(lead.id, !lead.ai_paused)
      setSelectedLead(updated)
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', lead.id] })
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

  // contact_person can be empty — or just a bare '@' (username lookup returned
  // nothing but the '@' prefix still got saved) — if the Instagram username
  // lookup failed at webhook time (rate limits/token scope/network). Fall back
  // through the other channel identifiers we do have instead of showing '@.'/'?'.
  const isUsableContactPerson = (value: string | null | undefined): value is string =>
    !!value && value.trim().replace(/^@+/, '').trim().length > 0

  const getLeadDisplayName = (lead: Lead): string => {
    if (isUsableContactPerson(lead.contact_person)) return lead.contact_person
    if (lead.instagram_username) return `@${lead.instagram_username}`
    if (lead.telegram_username) return `@${lead.telegram_username}`
    if (lead.whatsapp_phone) return lead.whatsapp_phone
    if (lead.instagram_user_id) return `IG ${lead.instagram_user_id}`
    if (lead.telegram_chat_id) return `TG ${lead.telegram_chat_id}`
    return 'Гость'
  }

  // Short label for the leads list — initials only, full name shown on hover/selection.
  // Only makes sense for real multi-letter human names; a single-token handle like
  // "@erdem_axon" would otherwise collapse to a meaningless "@.".
  const getContactInitials = (name: string | null | undefined) => {
    if (!name) return '—'
    const parts = name.trim().split(/\s+/).filter(Boolean)
    if (parts.length === 0) return '—'
    if (parts.length === 1) return `${parts[0][0].toUpperCase()}.`
    return parts.slice(0, 2).map((p) => `${p[0].toUpperCase()}.`).join(' ')
  }

  // What the leads list sidebar shows: initials for a real contact_person name,
  // but the full handle/phone/ID (truncated by CSS, not reduced to one letter)
  // when we only have a channel identifier to fall back on. Instagram/Telegram
  // leads without a real name often have contact_person set to the handle itself
  // (e.g. "@erdem_axon") — that's not a name, so it must not go through
  // getContactInitials either, or it collapses to "@." same as the other handles.
  const getSidebarLabel = (lead: Lead): string => {
    const person = lead.contact_person?.trim() ?? ''
    if (isUsableContactPerson(person) && !person.startsWith('@')) {
      return getContactInitials(person)
    }
    return getLeadDisplayName(lead)
  }

  return (
    <div className="flex flex-1 flex-col min-h-0 overflow-hidden crm-enter comms-root">

      {/* Upper Title Panel */}
      <div className="border-b bg-card px-4 py-3 flex items-center justify-between crm-panel">
        <div>
          <h1 className="text-base sm:text-xl font-bold tracking-tight">Центр сообщений</h1>
          <p className="text-xs text-muted-foreground hidden sm:block">
            Telegram, WhatsApp и Instagram с поддержкой ИИ-ассистента
          </p>
        </div>
      </div>

      {/* Main Unified Workspace */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        
        {/* Left Column: Unified Leads List & Search.
             On mobile: full-width and hidden when a lead is selected (chat view).
             On md+: fixed 280px sidebar always visible. */}
        <div className={`shrink-0 border-r bg-card flex flex-col h-full min-h-0 overflow-hidden ${
          selectedLead ? 'hidden md:flex md:w-[300px]' : 'flex w-full md:w-[300px]'
        }`}>

          {/* Channel Filters */}
          <div className="px-3 pt-3 pb-2 border-b space-y-2 bg-card">
            <div className="flex rounded-xl bg-muted/60 p-1 w-full gap-0.5">
              <button
                onClick={() => setActiveChannelTab('all')}
                className={`flex-1 text-[11px] font-bold py-2 rounded-lg transition-all ${activeChannelTab === 'all' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                Все
              </button>
              <button
                onClick={() => setActiveChannelTab('telegram')}
                className={`flex-1 text-[11px] font-bold py-2 rounded-lg transition-all flex items-center justify-center gap-1 ${activeChannelTab === 'telegram' ? 'bg-sky-500 shadow-sm text-white' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <MessageSquareIcon className="h-3 w-3" />
                <span>TG</span>
              </button>
              <button
                onClick={() => setActiveChannelTab('whatsapp')}
                className={`flex-1 text-[11px] font-bold py-2 rounded-lg transition-all flex items-center justify-center gap-1 ${activeChannelTab === 'whatsapp' ? 'bg-green-500 shadow-sm text-white' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <PhoneIcon className="h-3 w-3" />
                <span>WA</span>
              </button>
              <button
                onClick={() => setActiveChannelTab('instagram')}
                className={`flex-1 text-[11px] font-bold py-2 rounded-lg transition-all flex items-center justify-center gap-1 ${activeChannelTab === 'instagram' ? 'bg-gradient-to-r from-purple-500 to-pink-500 shadow-sm text-white' : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <InstagramIcon className="h-3 w-3" />
                <span>IG</span>
              </button>
            </div>

            {/* Status filters */}
            <div className="flex items-center gap-1 flex-wrap">
              {([
                { key: 'all', label: 'Все', cls: 'bg-foreground text-background' },
                { key: 'unread', label: 'Новые', cls: 'bg-red-500 text-white' },
                { key: 'paused', label: 'Ручной', cls: 'bg-amber-500 text-white' },
                { key: 'active', label: 'ИИ', cls: 'bg-green-500 text-white' },
              ] as const).map(({ key, label, cls }) => (
                <button
                  key={key}
                  onClick={() => setActiveStatusFilter(key)}
                  className={`text-[10px] font-bold px-2.5 py-1.5 rounded-full transition-all ${
                    activeStatusFilter === key
                      ? cls
                      : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Поиск по имени или телефону..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 h-10 text-sm rounded-xl bg-muted/40 border-border/40 focus:border-primary/30"
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
              <div className="divide-y crm-stagger">
                {filteredLeads.map((lead) => {
                  const unread = getLeadTotalUnread(lead.id)
                  const isSelected = selectedLead?.id === lead.id

                  return (
                    <button
                      key={lead.id}
                      onClick={() => handleSelectLead(lead)}
                      className={`w-full px-3 py-3 text-left transition-all outline-none group ${
                        isSelected
                          ? 'bg-primary/8 border-l-2 border-l-primary pl-[10px]'
                          : 'hover:bg-muted/50 border-l-2 border-l-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        {/* Avatar */}
                        <div className={`shrink-0 h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                          isSelected ? 'bg-primary text-primary-foreground'
                          : unread > 0 ? 'bg-primary/80 text-primary-foreground'
                          : 'bg-muted text-muted-foreground'
                        }`}>
                          {getLeadDisplayName(lead)[0].toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-1 mb-0.5">
                            <span
                              title={getLeadDisplayName(lead)}
                              className={`flex-1 truncate min-w-0 text-sm font-semibold ${
                                unread > 0 ? 'text-foreground' : 'text-foreground/80'
                              }`}
                            >
                              {getSidebarLabel(lead)}
                            </span>
                            <div className="flex items-center gap-1 shrink-0">
                              {unread > 0 && (
                                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white crm-live-dot">
                                  {unread > 99 ? '99+' : unread}
                                </span>
                              )}
                              <span className="shrink-0 whitespace-nowrap text-[10px] text-muted-foreground">
                                {formatLastActive(lead.last_contacted || lead.created_at)}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {lead.telegram_chat_id && (
                              <MessageSquareIcon className="h-3 w-3 text-sky-500 shrink-0" />
                            )}
                            {lead.whatsapp_phone && (
                              <PhoneIcon className="h-3 w-3 text-green-500 shrink-0" />
                            )}
                            {lead.instagram_user_id && (
                              <InstagramIcon className="h-3 w-3 text-pink-500 shrink-0" />
                            )}
                            <span className={`text-[10px] font-medium ${
                              lead.ai_paused ? 'text-amber-600' : 'text-green-600'
                            }`}>
                              {lead.ai_paused ? 'Ручной' : 'ИИ'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Center Column: Chat Window. Takes all remaining space. */}
        <div className={`flex-1 min-w-0 flex flex-col h-full overflow-hidden comms-chat-bg ${selectedLead ? 'flex' : 'hidden md:flex'}`}>
          {selectedLead ? (
            <>
              {/* Chat Header */}
              <div className="border-b bg-card/95 backdrop-blur-sm px-3 sm:px-4 py-3 flex items-center gap-2 shrink-0 shadow-sm">
                {/* Mobile: back button */}
                <button
                  className="md:hidden flex items-center justify-center h-9 w-9 -ml-1 rounded-full hover:bg-muted transition-colors shrink-0"
                  onClick={() => setSelectedLead(null)}
                >
                  <ArrowLeftIcon className="h-5 w-5" />
                </button>
                {/* Avatar */}
                <div className="shrink-0 h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center text-primary text-sm font-bold">
                  {getLeadDisplayName(selectedLead)[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <h2 className="text-sm font-bold truncate leading-tight min-w-0">{getLeadDisplayName(selectedLead)}</h2>

                    {/* Channel Quick Switcher */}
                    {availableChannels.length > 1 && (
                      <div className="flex items-center rounded-lg bg-muted p-0.5 shrink-0 gap-0.5">
                        {availableChannels.map(ch => (
                          <button
                            key={ch}
                            onClick={() => setOverrideChannel(ch)}
                            className={`px-2 py-1 text-[10px] font-bold rounded-md transition-all flex items-center gap-1 ${
                              activeChannel === ch
                                ? ch === 'telegram' ? 'bg-sky-500 text-white shadow-sm'
                                : ch === 'whatsapp' ? 'bg-green-500 text-white shadow-sm'
                                : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                            }`}
                          >
                            {ch === 'telegram' && <><MessageSquareIcon className="h-3 w-3" /> TG</>}
                            {ch === 'instagram' && <><InstagramIcon className="h-3 w-3" /> IG</>}
                            {ch === 'whatsapp' && <><PhoneIcon className="h-3 w-3" /> WA</>}
                          </button>
                        ))}
                      </div>
                    )}
                    {availableChannels.length <= 1 && (
                      <>
                        {selectedLead.telegram_chat_id && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-sky-600 bg-sky-50 dark:bg-sky-950/30 px-2 py-0.5 rounded-full border border-sky-200 dark:border-sky-800">
                            <MessageSquareIcon className="h-2.5 w-2.5" />{selectedLead.telegram_username ? `@${selectedLead.telegram_username}` : 'Telegram'}
                          </span>
                        )}
                        {selectedLead.whatsapp_phone && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-green-700 bg-green-50 dark:bg-green-950/30 px-2 py-0.5 rounded-full border border-green-200 dark:border-green-800">
                            <PhoneIcon className="h-2.5 w-2.5" />{selectedLead.whatsapp_phone}
                          </span>
                        )}
                        {selectedLead.instagram_user_id && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-pink-700 bg-pink-50 dark:bg-pink-950/30 px-2 py-0.5 rounded-full border border-pink-200 dark:border-pink-800">
                            <InstagramIcon className="h-2.5 w-2.5" />{selectedLead.instagram_username ? `@${selectedLead.instagram_username}` : 'Instagram'}
                          </span>
                        )}
                      </>
                    )}
                  </div>
                  <div className="text-[10px] text-muted-foreground sm:hidden leading-tight">
                    {selectedLead.ai_paused ? 'Ручной режим' : 'ИИ активен'}
                  </div>
                </div>

                {/* AI / Manual Controls */}
                <div className="flex items-center gap-1.5 shrink-0 ml-auto">

                  {/* Status pill */}
                  <div className={`hidden lg:flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-semibold ${
                    selectedLead.ai_paused
                      ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
                      : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                  }`}>
                    {selectedLead.ai_paused ? (
                      <><HandIcon className="h-3 w-3" /> Ручной</>
                    ) : (
                      <><BotIcon className="h-3 w-3" /> ИИ активен</>
                    )}
                  </div>

                  {/* Toggle AI */}
                  <button
                    disabled={isTogglingAi}
                    className={`flex items-center gap-1.5 h-9 px-3 rounded-xl text-xs font-semibold transition-all disabled:opacity-50 ${
                      selectedLead.ai_paused
                        ? 'bg-green-600 hover:bg-green-700 text-white shadow-sm'
                        : 'border border-amber-400 text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-900/20'
                    }`}
                    onClick={() => handleToggleAiPause(selectedLead)}
                  >
                    {selectedLead.ai_paused ? (
                      <><PlayIcon className="h-3.5 w-3.5" /><span className="hidden sm:inline">Вкл. ИИ</span></>
                    ) : (
                      <><HandIcon className="h-3.5 w-3.5" /><span className="hidden sm:inline">Перехват</span></>
                    )}
                  </button>

                  {/* Logs */}
                  {showAiDiagnostics && (
                    <button
                      className={`flex items-center justify-center h-9 w-9 rounded-xl border text-sm transition-all ${
                        showAiDiagnosticsOpen
                          ? 'bg-primary/10 text-primary border-primary/20'
                          : 'border-border text-muted-foreground hover:text-foreground hover:bg-muted'
                      }`}
                      onClick={() => setShowAiDiagnosticsOpen(!showAiDiagnosticsOpen)}
                      title="Логи ИИ"
                    >
                      <ScrollTextIcon className="h-4 w-4" />
                    </button>
                  )}

                  {/* Card sidebar */}
                  <button
                    className={`flex items-center justify-center h-9 w-9 rounded-xl border text-sm transition-all ${
                      showRightSidebar
                        ? 'bg-primary/10 text-primary border-primary/20'
                        : 'border-border text-muted-foreground hover:text-foreground hover:bg-muted'
                    }`}
                    onClick={() => setShowRightSidebar(!showRightSidebar)}
                    title="Карточка клиента"
                  >
                    <SlidersHorizontalIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* AI Diagnostic Step reasoning panel - shown only when toggled on */}
              {showAiDiagnostics && showAiDiagnosticsOpen && (
                <AiDiagnosticsPanel activities={orderedMessages} channelLabel={activeChannel.toUpperCase()} />
              )}

              {/* Message Timeline (using min-h-0 and flex-1 to let Flexbox limit height inside viewport) */}
              <ScrollArea className="flex-1 min-h-0" ref={scrollAreaRef}>
                <div className="flex flex-col gap-2 p-3 sm:p-4 pb-3">
                  {orderedMessages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
                      <div className="h-16 w-16 rounded-full bg-muted/80 flex items-center justify-center">
                        <MessageSquareIcon className="h-8 w-8 text-muted-foreground/40" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">Нет сообщений</p>
                        <p className="text-xs text-muted-foreground mt-0.5">Начните диалог с гостем</p>
                      </div>
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

                        lowerText.startsWith('[получено: ig_') ||
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

                      const instagramContextPreview = isInstagram && !isSent

                        ? getInstagramContextPreview(activity.metadata)

                        : null

                      const timestamp = new Date(activity.created_at).toLocaleString('ru-RU', {
                        month: 'short',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                      })

                      const sentBy = isSent ? getSentBy(activity.metadata) : null

                      return (
                        <div key={activity.id} className={`flex crm-message ${isSent ? 'justify-end' : 'justify-start'}`}>
                          <div className={`comms-bubble max-w-[88%] sm:max-w-[72%] lg:max-w-[62%] ${
                            isSent
                              ? activeChannel === 'instagram'
                                ? 'comms-bubble-instagram'
                                : 'comms-bubble-sent'
                              : 'comms-bubble-recv'
                          }`}>
                            {/* Reply Reference Context */}
                            {(activity.metadata as any)?.reply_to && (() => {
                              const reply = (activity.metadata as any).reply_to as {
                                message_id?: number | string
                                text?: string
                                sender_name?: string
                                from_bot?: boolean
                              }
                              return (
                                <div className={`mb-1.5 text-xs border-l-2 pl-2 py-0.5 rounded-r bg-black/5 dark:bg-white/5 max-w-full ${
                                  isSent ? 'border-white/40' : 'border-sky-500/60'
                                }`}>
                                  <div className="font-semibold text-[11px] opacity-80 truncate">
                                    {reply.from_bot ? 'Бот' : (reply.sender_name || 'Гость')}
                                  </div>
                                  <div className="opacity-75 break-words line-clamp-2 text-[12px] mt-0.5">
                                    {reply.text}
                                  </div>
                                </div>
                              )
                            })()}


                            {/* Photo */}
                            {mediaType === 'photo' && mediaUrls.length > 0 && (
                              <div className="overflow-hidden rounded-xl mb-1 -mx-0.5 -mt-0.5">
                                {mediaUrls.length === 1 ? (
                                  <img
                                    src={mediaUrls[0]}
                                    alt={mediaTitle || 'Фото'}
                                    className="max-h-72 w-full object-cover"
                                  />
                                ) : (
                                  <div className="grid gap-0.5 grid-cols-2">
                                    {mediaUrls.slice(0, 4).map((url, idx) => (
                                      <img
                                        key={idx}
                                        src={url}
                                        alt={mediaTitle ? `${mediaTitle} ${idx + 1}` : `Фото ${idx + 1}`}
                                        className="h-32 w-full object-cover"
                                      />
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Video */}
                            {mediaType === 'video' && mediaUrls.length > 0 && (
                              <div className="overflow-hidden rounded-xl mb-1 -mx-0.5 -mt-0.5">
                                <CustomVideoPlayer src={mediaUrls[0]} title={mediaTitle || fileName || 'Видео'} />
                              </div>
                            )}

                            {/* Audio */}
                            {mediaType === 'audio' && mediaUrls.length > 0 && (
                              <div className="py-1">
                                <CustomAudioPlayer src={mediaUrls[0]} title={mediaTitle || fileName} isVoice={isVoice} />
                              </div>
                            )}

                            {/* Document */}
                            {mediaType === 'document' && mediaUrls.length > 0 && (
                              <a
                                href={mediaUrls[0]}
                                target="_blank"
                                rel="noreferrer"
                                className={`flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors mb-1 ${
                                  isSent ? 'bg-white/15 hover:bg-white/25' : 'bg-muted/60 hover:bg-muted'
                                }`}
                              >
                                <FileIcon className="h-4 w-4 shrink-0" />
                                <span className="max-w-[220px] truncate">{fileName || mediaTitle || 'Открыть файл'}</span>
                              </a>
                            )}

                            {instagramContextPreview && (

                              <div className={`mb-2 overflow-hidden rounded-lg border text-left ${

                                isSent ? 'border-white/25 bg-white/10' : 'border-border bg-background/80'

                              }`}>

                                {instagramContextPreview.previewUrl && (

                                  <img

                                    src={instagramContextPreview.previewUrl}

                                    alt={instagramContextPreview.title}

                                    className="h-28 w-full object-cover"

                                  />

                                )}

                                <div className="space-y-1.5 px-3 py-2.5">

                                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-normal text-muted-foreground">

                                    <InstagramIcon className="h-3 w-3 text-pink-500" />

                                    <span>{instagramContextPreview.heading}</span>

                                  </div>

                                  <div className="text-[13px] font-semibold leading-snug text-foreground break-words">

                                    {instagramContextPreview.title}

                                  </div>

                                  {instagramContextPreview.badges.length > 0 && (

                                    <div className="flex flex-wrap gap-1">

                                      {instagramContextPreview.badges.map((badge) => (

                                        <span key={badge} className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">

                                          {badge}

                                        </span>

                                      ))}

                                    </div>

                                  )}

                                  {instagramContextPreview.linkUrl && (

                                    <a

                                      href={instagramContextPreview.linkUrl}

                                      target="_blank"

                                      rel="noreferrer"

                                      className="inline-flex text-[11px] font-medium text-pink-600 hover:text-pink-700"

                                    >

                                      Открыть в Instagram

                                    </a>

                                  )}

                                </div>

                              </div>

                            )}



                            {/* Text */}
                            {messageText && (
                              <p className="text-[14px] sm:text-[15px] leading-relaxed whitespace-pre-wrap break-words">{messageText}</p>
                            )}

                            {/* Footer */}
                            <div className={`flex items-center gap-1.5 mt-1.5 ${isSent ? 'justify-end' : 'justify-start'}`}>
                              {sentBy && (
                                <span className={`text-[11px] font-semibold ${isSent ? 'opacity-70' : 'text-muted-foreground'}`}>
                                  {sentBy} ·
                                </span>
                              )}
                              <span className={`text-[11px] ${isSent ? 'opacity-65' : 'text-muted-foreground'}`}>{timestamp}</span>
                              {isTelegram && <MessageSquareIcon className={`h-2.5 w-2.5 shrink-0 ${isSent ? 'opacity-55' : 'text-sky-400'}`} />}
                              {isWhatsApp && <PhoneIcon className={`h-2.5 w-2.5 shrink-0 ${isSent ? 'opacity-55' : 'text-green-400'}`} />}
                              {isInstagram && <InstagramIcon className={`h-2.5 w-2.5 shrink-0 ${isSent ? 'opacity-55' : 'text-pink-400'}`} />}
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
              <div className="border-t bg-card/95 backdrop-blur-sm px-3 sm:px-4 pt-2.5 pb-3 sm:pb-4 space-y-2 shrink-0">

                {/* AI Co-pilot Suggestions Area (if AI paused) */}
                {selectedLead.ai_paused && (
                  <CopilotSuggestions
                    key={`${selectedLead.id}:${activeChannel}`}
                    leadId={selectedLead.id}
                    onSelectSuggestion={(text) => setMessage(text)}
                  />
                )}

                {/* Templates and Quick utilities */}
                <div className="flex items-center gap-1 flex-wrap">
                  <QuickRepliesPopover channel={activeChannel} onSelectTemplate={(text) => setMessage(prev => prev + text)} />

                  {/* Emoji Picker */}
                  <Popover>
                    <PopoverTrigger asChild>
                      <button className="flex items-center justify-center h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" title="Эмодзи">
                        <SmileIcon className="h-4 w-4" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-72 p-2" align="start" side="top">
                      <div className="grid grid-cols-8 gap-1">
                        {COMMON_EMOJIS.map((emoji) => (
                          <button
                            key={emoji}
                            onClick={() => setMessage(prev => prev + emoji)}
                            className="text-xl hover:bg-muted rounded-lg p-1.5 transition-colors outline-none"
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
                      <button
                        className={`flex items-center justify-center h-8 w-8 rounded-lg transition-colors ${
                          attachment ? 'text-primary bg-primary/10' : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                        }`}
                        onClick={() => fileInputRef.current?.click()}
                        title="Прикрепить медиа"
                      >
                        <PaperclipIcon className="h-4 w-4" />
                      </button>

                      {canRecordVoice && (
                        <button
                          className={`flex items-center gap-1.5 h-8 px-2 rounded-lg text-xs font-semibold transition-colors ${
                            isRecordingVoice
                              ? 'bg-red-500 text-white hover:bg-red-600'
                              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                          }`}
                          onClick={isRecordingVoice ? handleStopVoiceRecording : handleStartVoiceRecording}
                          type="button"
                          title="Голосовое сообщение"
                        >
                          {isRecordingVoice ? (
                            <><SquareIcon className="h-4 w-4" /><span>{formatMediaTime(recordingSeconds)}</span></>
                          ) : (
                            <MicIcon className="h-4 w-4" />
                          )}
                        </button>
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
                      placeholder="Напишите сообщение... (Shift+Enter — новая строка)"
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          void handleSendMessage()
                        }
                      }}
                      className="min-h-[44px] max-h-36 text-sm resize-none py-3 px-4 leading-normal rounded-2xl border-border/60 bg-muted/30 focus:bg-background transition-colors"
                    />
                  </div>
                  <button
                    onClick={handleSendMessage}
                    disabled={(!message.trim() && !attachment) || isSending}
                    className="h-11 w-11 shrink-0 rounded-2xl bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground shadow-md flex items-center justify-center transition-all active:scale-95"
                  >
                    <SendIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 gap-4">
              <div className="h-20 w-20 rounded-full bg-muted/60 flex items-center justify-center">
                <MessageSquareIcon className="h-10 w-10 text-muted-foreground/40" />
              </div>
              <div className="space-y-1">
                <h3 className="font-semibold text-base">Выберите диалог</h3>
                <p className="text-sm text-muted-foreground max-w-[260px]">
                  Нажмите на гостя слева, чтобы открыть переписку
                </p>
              </div>
            </div>
          )}
        </div>

          {/* Right Sidebar: drawer on mobile, inline on desktop */}
          {selectedLead && showRightSidebar && (
            <div className="absolute inset-0 z-30 md:relative md:inset-auto md:z-auto md:w-[300px] md:shrink-0 flex justify-end">
              {/* Mobile backdrop */}
              <div
                className="absolute inset-0 bg-black/40 md:hidden"
                onClick={() => setShowRightSidebar(false)}
              />
              <div className="relative w-[85vw] sm:w-[320px] md:w-full bg-card border-l shadow-2xl md:shadow-none h-full z-10">
                <LeadDetailsSidebar
                  lead={selectedLead}
                  onClose={() => setShowRightSidebar(false)}
                  showResetAiMemory={showResetAiMemory}
                  isResettingAiMemory={isResettingAiMemory}
                  onResetAiMemory={() => setResetTarget({ lead: selectedLead, channel: activeChannel })}
                  onMergeSuccess={(targetLeadId) => {
                    queryClient.invalidateQueries({ queryKey: ['leads'] })
                    queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
                    const targetLead = leads.find((l) => l.id === targetLeadId)
                    if (targetLead) {
                      handleSelectLead(targetLead)
                      navigate({
                        search: { leadId: String(targetLeadId) } as any,
                      })
                    } else {
                      setSelectedLead(null)
                      navigate({
                        search: {} as any,
                      })
                    }
                  }}
                />
              </div>
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
