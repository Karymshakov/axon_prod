import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useRef, useEffect, useMemo } from 'react'
import { MessageSquareIcon, SendIcon, InstagramIcon, PhoneIcon, SmileIcon, BotIcon, HandIcon, PlayIcon, RotateCcwIcon, UserIcon } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
import { useAuth } from '@/contexts/auth-context'
import { getInternalToolsVisibilitySettings } from '@/lib/org-settings'

export const Route = createFileRoute('/_app/communications')({
  component: CommunicationsPage,
})

const COMMON_EMOJIS = [
  '😀','😂','😍','🥰','😎','🤔','😊','🙏',
  '👍','👎','❤️','🔥','✅','⭐','🎉','💯',
  '😅','😢','😡','🤩','😴','🤗','😏','🥳',
  '👋','💪','🙌','👏','🤝','💬','📣','🚀',
]

type ConversationChannel = 'telegram' | 'instagram' | 'whatsapp'

type ResetTarget = {
  lead: Lead
  channel: ConversationChannel
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

function getSentBy(metadata: Record<string, unknown> | null): 'ai' | 'manager' {
  if (!metadata) return 'ai'
  if (metadata.is_manager_manual) return 'manager'
  if (metadata.is_ai_generated || metadata.is_ai_agent || metadata.is_ai_action) return 'ai'
  return 'ai'
}

function CommunicationsPage() {
  const navigate = useNavigate()
  const { t } = useLanguage()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [selectedInstagramLead, setSelectedInstagramLead] = useState<Lead | null>(null)
  const [selectedWhatsAppLead, setSelectedWhatsAppLead] = useState<Lead | null>(null)
  const [message, setMessage] = useState('')
  const [instagramMessage, setInstagramMessage] = useState('')
  const [whatsappMessage, setWhatsappMessage] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [instagramSearchQuery, setInstagramSearchQuery] = useState('')
  const [whatsappSearchQuery, setWhatsappSearchQuery] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isSendingInstagram, setIsSendingInstagram] = useState(false)
  const [isSendingWhatsApp, setIsSendingWhatsApp] = useState(false)
  const [isTogglingAi, setIsTogglingAi] = useState(false)
  const [isResettingAiMemory, setIsResettingAiMemory] = useState(false)
  const [resetTarget, setResetTarget] = useState<ResetTarget | null>(null)

  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const instagramScrollAreaRef = useRef<HTMLDivElement>(null)
  const whatsappScrollAreaRef = useRef<HTMLDivElement>(null)
  const telegramBottomRef = useRef<HTMLDivElement>(null)
  const instagramBottomRef = useRef<HTMLDivElement>(null)
  const whatsappBottomRef = useRef<HTMLDivElement>(null)

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

  const { data: unreadData } = useQuery({
    queryKey: ['communications-unread-counts'],
    queryFn: fetchCommunicationsUnreadCounts,
    refetchInterval: 5000,
    networkMode: 'always',
  })
  const unreadCounts = unreadData?.counts ?? {}

  const getUnread = (leadId: number, channel: string) =>
    unreadCounts[String(leadId)]?.[channel] ?? 0

  const { data: activities = [], refetch: refetchActivities } = useQuery({
    queryKey: ['lead-activities', selectedLead?.id],
    queryFn: () => selectedLead ? fetchLeadActivities(selectedLead.id) : Promise.resolve([]),
    enabled: !!selectedLead,
    refetchInterval: 3000,
  })

  const { data: instagramActivities = [], refetch: refetchInstagramActivities } = useQuery({
    queryKey: ['lead-activities', selectedInstagramLead?.id, 'instagram'],
    queryFn: () => selectedInstagramLead ? fetchLeadActivities(selectedInstagramLead.id) : Promise.resolve([]),
    enabled: !!selectedInstagramLead,
    refetchInterval: 3000,
  })

  const { data: whatsappActivities = [], refetch: refetchWhatsAppActivities } = useQuery({
    queryKey: ['lead-activities', selectedWhatsAppLead?.id, 'whatsapp'],
    queryFn: () => selectedWhatsAppLead ? fetchLeadActivities(selectedWhatsAppLead.id) : Promise.resolve([]),
    enabled: !!selectedWhatsAppLead,
    refetchInterval: 3000,
  })

  const telegramMessages = useMemo(() => activities.filter(
    activity => activity.activity_type === 'telegram_sent' || activity.activity_type === 'telegram_received'
  ), [activities])

  const orderedTelegramMessages = useMemo(
    () => sortActivitiesChronologically(telegramMessages),
    [telegramMessages],
  )

  const instagramMessages = useMemo(() => instagramActivities.filter(
    activity => activity.activity_type === 'instagram_sent' || activity.activity_type === 'instagram_received'
  ), [instagramActivities])

  const orderedInstagramMessages = useMemo(
    () => sortActivitiesChronologically(instagramMessages),
    [instagramMessages],
  )

  const whatsappMessages = useMemo(() => whatsappActivities.filter(
    activity => activity.activity_type === 'whatsapp_sent' || activity.activity_type === 'whatsapp_received'
  ), [whatsappActivities])

  const orderedWhatsAppMessages = useMemo(
    () => sortActivitiesChronologically(whatsappMessages),
    [whatsappMessages],
  )

  const scrollToBottom = (ref: React.RefObject<HTMLDivElement | null>) => {
    if (ref.current) {
      const scrollContainer = ref.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }

  const scrollAnchorIntoView = (ref: React.RefObject<HTMLDivElement | null>) => {
    if (!ref.current) return

    requestAnimationFrame(() => {
      ref.current?.scrollIntoView({ behavior: 'auto', block: 'end' })
    })
  }

  useEffect(() => {
    scrollToBottom(scrollAreaRef)
    scrollAnchorIntoView(telegramBottomRef)
    const timer = setTimeout(() => {
      scrollToBottom(scrollAreaRef)
      scrollAnchorIntoView(telegramBottomRef)
    }, 150)
    return () => clearTimeout(timer)
  }, [orderedTelegramMessages, selectedLead?.id])

  useEffect(() => {
    scrollToBottom(instagramScrollAreaRef)
    scrollAnchorIntoView(instagramBottomRef)
    const timer = setTimeout(() => {
      scrollToBottom(instagramScrollAreaRef)
      scrollAnchorIntoView(instagramBottomRef)
    }, 150)
    return () => clearTimeout(timer)
  }, [orderedInstagramMessages, selectedInstagramLead?.id])

  useEffect(() => {
    scrollToBottom(whatsappScrollAreaRef)
    scrollAnchorIntoView(whatsappBottomRef)
    const timer = setTimeout(() => {
      scrollToBottom(whatsappScrollAreaRef)
      scrollAnchorIntoView(whatsappBottomRef)
    }, 150)
    return () => clearTimeout(timer)
  }, [orderedWhatsAppMessages, selectedWhatsAppLead?.id])

  const sortByLastContacted = (a: Lead, b: Lead) => {
    if (!a.last_contacted && !b.last_contacted) return 0
    if (!a.last_contacted) return 1
    if (!b.last_contacted) return -1
    return new Date(b.last_contacted).getTime() - new Date(a.last_contacted).getTime()
  }

  // Filter leads that have Telegram configured, sorted by most recent contact
  const telegramLeads = leads
    .filter(lead => lead.telegram_chat_id)
    .sort(sortByLastContacted)

  // Filter leads that have Instagram configured (exclude own account), sorted by most recent contact
  const instagramLeads = leads
    .filter(lead =>
      lead.instagram_user_id &&
      lead.instagram_username !== instagramStatus?.instagram_username
    )
    .sort(sortByLastContacted)

  // Filter leads that have WhatsApp configured, sorted by most recent contact
  const whatsappLeads = leads
    .filter(lead => lead.whatsapp_phone)
    .sort(sortByLastContacted)

  // Filter based on search
  const filteredLeads = searchQuery
    ? telegramLeads.filter(lead =>
        lead.contact_person.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : telegramLeads

  // Filter Instagram leads based on search
  const filteredInstagramLeads = instagramSearchQuery
    ? instagramLeads.filter(lead =>
        lead.contact_person.toLowerCase().includes(instagramSearchQuery.toLowerCase()) ||
        lead.instagram_username.toLowerCase().includes(instagramSearchQuery.toLowerCase())
      )
    : instagramLeads

  // Filter WhatsApp leads based on search
  const filteredWhatsAppLeads = whatsappSearchQuery
    ? whatsappLeads.filter(lead =>
        lead.contact_person.toLowerCase().includes(whatsappSearchQuery.toLowerCase())
      )
    : whatsappLeads

  const handleSelectLead = (lead: Lead, channel: 'telegram' | 'instagram' | 'whatsapp') => {
    if (channel === 'telegram') setSelectedLead(lead)
    if (channel === 'instagram') setSelectedInstagramLead(lead)
    if (channel === 'whatsapp') setSelectedWhatsAppLead(lead)

    try {
      const count = getUnread(lead.id, channel)
      if (count > 0) {
        markCommunicationsRead(lead.id, channel).then(() => {
          queryClient.invalidateQueries({ queryKey: ['communications-unread-counts'] })
        }).catch(console.error)
      }
    } catch (err) {
      console.error('Error marking read:', err)
    }
  }

  const handleToggleAiPause = async (lead: Lead, setSelected: (lead: Lead) => void) => {
    setIsTogglingAi(true)
    try {
      const updated = await toggleAiPause(lead.id)
      setSelected(updated)
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      toast.success(updated.ai_paused ? 'AI paused — you are now in control' : 'AI agent re-enabled')
    } catch {
      toast.error('Failed to toggle AI')
    } finally {
      setIsTogglingAi(false)
    }
  }

  const updateSelectedLeadForChannel = (channel: ConversationChannel, lead: Lead) => {
    if (channel === 'telegram') setSelectedLead(lead)
    if (channel === 'instagram') setSelectedInstagramLead(lead)
    if (channel === 'whatsapp') setSelectedWhatsAppLead(lead)
  }

  const handleResetAiMemory = async (target: ResetTarget) => {
    setIsResettingAiMemory(true)
    try {
      const response = await resetLeadAiMemory(target.lead.id)
      updateSelectedLeadForChannel(target.channel, response.lead)
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', target.lead.id] })
      toast.success(`AI memory cleared for ${response.lead.contact_person}. Message history is unchanged.`)
      setResetTarget(null)
    } catch {
      toast.error('Failed to reset AI memory for this conversation')
    } finally {
      setIsResettingAiMemory(false)
    }
  }

  const handleSendMessage = async () => {
    if (!selectedLead || !message.trim()) {
      toast.error('Please enter a message')
      return
    }

    setIsSending(true)
    try {
      const response = await sendTelegramMessageFromComms(selectedLead.id, message)
      if (response.success) {
        toast.success('Message sent successfully')
        setMessage('')
        await refetchActivities()
      } else {
        toast.error(response.error || 'Failed to send message')
      }
    } catch (error) {
      if (error instanceof ApiError) {
        const errorData = error.data as any
        toast.error(errorData?.error || 'Failed to send message')
      } else {
        toast.error('Failed to send message. Please try again.')
      }
    } finally {
      setIsSending(false)
    }
  }

  const handleSendInstagramMessage = async () => {
    if (!selectedInstagramLead || !instagramMessage.trim()) {
      toast.error('Please enter a message')
      return
    }

    setIsSendingInstagram(true)
    try {
      const response = await sendInstagramMessageFromComms(selectedInstagramLead.id, instagramMessage)
      if (response.success) {
        toast.success('Instagram message sent successfully')
        setInstagramMessage('')
        await refetchInstagramActivities()
      } else {
        toast.error(response.error || 'Failed to send Instagram message')
      }
    } catch (error) {
      if (error instanceof ApiError) {
        const errorData = error.data as any
        toast.error(errorData?.error || 'Failed to send Instagram message')
      } else {
        toast.error('Failed to send Instagram message. Please try again.')
      }
    } finally {
      setIsSendingInstagram(false)
    }
  }

  const handleSendWhatsAppMessage = async () => {
    if (!selectedWhatsAppLead || !whatsappMessage.trim()) {
      toast.error('Please enter a message')
      return
    }

    setIsSendingWhatsApp(true)
    try {
      const response = await sendWhatsAppMessageFromComms(selectedWhatsAppLead.id, whatsappMessage)
      if (response.success) {
        toast.success('WhatsApp message sent successfully')
        setWhatsappMessage('')
        await refetchWhatsAppActivities()
      } else {
        toast.error(response.error || 'Failed to send WhatsApp message')
      }
    } catch (error) {
      if (error instanceof ApiError) {
        const errorData = error.data as any
        toast.error(errorData?.error || 'Failed to send WhatsApp message')
      } else {
        toast.error('Failed to send WhatsApp message. Please try again.')
      }
    } finally {
      setIsSendingWhatsApp(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
          <div className="px-4 lg:px-6">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold">{t('communications.title')}</h1>
              <p className="text-sm text-muted-foreground">
                {t('communications.subtitle')}
              </p>
            </div>
          </div>

          <div className="px-4 lg:px-6">
            <Tabs defaultValue="instagram" className="space-y-6">
              <TabsList>
                <TabsTrigger value="instagram">
                  <InstagramIcon className="h-4 w-4 mr-2" />
                  Instagram
                </TabsTrigger>
                <TabsTrigger value="whatsapp">
                  <PhoneIcon className="h-4 w-4 mr-2" />
                  WhatsApp
                </TabsTrigger>
                <TabsTrigger value="telegram">
                  <MessageSquareIcon className="h-4 w-4 mr-2" />
                  Telegram
                </TabsTrigger>
              </TabsList>

              <TabsContent value="telegram">
                {!telegramStatus?.configured ? (
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center space-y-4">
                        <MessageSquareIcon className="h-12 w-12 mx-auto text-muted-foreground" />
                        <div>
                          <h3 className="font-semibold text-lg">{t('settings.integrations.connect')} Telegram</h3>
                          <p className="text-sm text-muted-foreground mt-2">
                            {t('communications.noConversationsDesc')}
                          </p>
                        </div>
                        <Button onClick={() => navigate({ to: '/settings', search: { tab: 'integrations' } })}>
                          {t('settings.integrations.connect')}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
                    {/* Leads List */}
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">{t('communications.title')}</CardTitle>
                        <CardDescription>
                          {t('communications.selectConversationDesc')}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="p-0">
                        <div className="p-4 border-b">
                          <Input
                            placeholder={t('leads.searchPlaceholder')}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                          />
                        </div>
                        <ScrollArea className="h-[500px]">
                          {filteredLeads.length === 0 ? (
                            <div className="p-4 text-center text-sm text-muted-foreground">
                              {searchQuery ? 'No leads found' : 'No leads with Telegram configured'}
                            </div>
                          ) : (
                            <div className="divide-y">
                              {filteredLeads.map((lead) => {
                                const unread = getUnread(lead.id, 'telegram')
                                return (
                                <div
                                  key={lead.id}
                                  role="button"
                                  tabIndex={0}
                                  onClick={(e) => { e.preventDefault(); handleSelectLead(lead, 'telegram'); }}
                                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectLead(lead, 'telegram'); } }}
                                  className={`w-full p-4 text-left hover:bg-muted/50 transition-colors cursor-pointer block border-none bg-transparent outline-none ${
                                    selectedLead?.id === lead.id ? 'bg-muted' : ''
                                  }`}
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0 flex-1">
                                      <p className={`text-sm truncate ${unread > 0 ? 'font-semibold' : 'font-medium'}`}>
                                        {lead.contact_person}
                                      </p>
                                      {lead.telegram_username && (
                                        <p className="text-xs text-muted-foreground mt-1">
                                          @{lead.telegram_username}
                                        </p>
                                      )}
                                    </div>
                                    {unread > 0 && (
                                      <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-red-500 px-1 text-[11px] font-semibold text-white">
                                        {unread > 99 ? '99+' : unread}
                                      </span>
                                    )}
                                  </div>
                                </div>
                                )
                              })}
                            </div>
                          )}
                        </ScrollArea>
                      </CardContent>
                    </Card>

                    {/* Message Area */}
                    <Card className="min-w-0 overflow-hidden py-0 gap-0">
                      {selectedLead ? (
                        <>
                          <CardHeader className="border-b py-4">
                            <div className="flex items-center justify-between">
                              <div>
                                <CardTitle className="text-base">{selectedLead.contact_person}</CardTitle>
                                <CardDescription>
                                  {selectedLead.contact_person}
                                  {selectedLead.telegram_username ? ` • @${selectedLead.telegram_username}` : ''}
                                </CardDescription>
                              </div>
                              <Badge variant="secondary">Telegram</Badge>
                            </div>
                            <div className={`mt-1 flex flex-wrap items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm ${selectedLead.ai_paused ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                {selectedLead.ai_paused ? (
                                  <>
                                    <Badge className="bg-amber-500 text-white hover:bg-amber-500 gap-1 text-xs h-5">
                                      <HandIcon className="h-3 w-3" />
                                      Manual Mode
                                    </Badge>
                                    {selectedLead.ai_paused_at ? (
                                      <span className="text-xs text-amber-600">
                                        � \{new Date(selectedLead.ai_paused_at).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                                      </span>
                                    ) : null}
                                  </>
                                ) : (
                                  <Badge className="bg-green-600 text-white hover:bg-green-600 gap-1 text-xs h-5">
                                    <BotIcon className="h-3 w-3" />
                                    AI Active
                                  </Badge>
                                )}
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {showResetAiMemory && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-8 gap-1 border-red-200 bg-white/80 text-red-700 hover:bg-red-50"
                                    onClick={() => setResetTarget({ lead: selectedLead, channel: 'telegram' })}
                                  >
                                    <RotateCcwIcon className="h-3.5 w-3.5" />
                                    Reset AI Memory
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  disabled={isTogglingAi}
                                  className={selectedLead.ai_paused
                                    ? 'bg-green-600 hover:bg-green-700 text-white h-8 text-xs gap-1'
                                    : 'border border-amber-400 bg-transparent text-amber-700 hover:bg-amber-50 h-8 text-xs gap-1'
                                  }
                                  onClick={() => handleToggleAiPause(selectedLead, setSelectedLead)}
                                >
                                  {selectedLead.ai_paused ? (
                                    <><PlayIcon className="h-3 w-3" />Return to AI</>
                                  ) : (
                                    <><HandIcon className="h-3 w-3" />Take Control</>
                                  )}
                                </Button>
                              </div>
                            </div>
                          </CardHeader>
                          <CardContent className="p-0">
                            {showAiDiagnostics && (
                              <AiDiagnosticsPanel activities={orderedTelegramMessages} channelLabel="Telegram" />
                            )}
                            <ScrollArea className="h-[400px] p-4" ref={scrollAreaRef}>
                              <div className="space-y-4">
                                {orderedTelegramMessages.length === 0 ? (
                                  <div className="text-center text-sm text-muted-foreground">
                                    Start a conversation with {selectedLead.contact_person}
                                  </div>
                                ) : (
                                  orderedTelegramMessages.map((activity) => {
                                    const isSent = activity.activity_type === 'telegram_sent'
                                    const mediaType = activity.metadata?.media_type as string | undefined
                                    const fileUrl = activity.metadata?.file_url as string | undefined
                                    const fileUrls = activity.metadata?.file_urls as string[] | undefined
                                    const mediaTitle = activity.metadata?.media_title as string | undefined
                                    const messageText = !mediaType ? getTelegramMessageText(activity) : null
                                    const timestamp = new Date(activity.created_at).toLocaleString('ru-RU', {
                                      month: 'short',
                                      day: 'numeric',
                                      hour: 'numeric',
                                      minute: '2-digit',
                                    })
                                    const photoUrls = fileUrls && fileUrls.length > 0 ? fileUrls : (fileUrl ? [fileUrl] : [])
                                    const sentBy = isSent ? getSentBy(activity.metadata) : null

                                    return (
                                      <div
                                        key={activity.id}
                                        className={`flex ${isSent ? 'justify-end' : 'justify-start'}`}
                                      >
                                        <div
                                          className={`max-w-[85%] overflow-hidden rounded-2xl shadow-sm sm:max-w-[80%] ${
                                            isSent
                                              ? 'bg-primary text-primary-foreground'
                                              : 'border bg-muted/70'
                                          }`}
                                        >
                                          {mediaType === 'photo' && photoUrls.length > 0 ? (
                                            <div>
                                              {photoUrls.length === 1 ? (
                                                <img
                                                  src={photoUrls[0]}
                                                  alt={mediaTitle || 'Photo'}
                                                  className="w-full max-w-[280px] object-cover"
                                                />
                                              ) : (
                                                <div className={`grid gap-0.5 max-w-[280px] ${photoUrls.length === 2 ? 'grid-cols-2' : 'grid-cols-2'}`}>
                                                  {photoUrls.length === 3 ? (
                                                    <>
                                                      <img
                                                        src={photoUrls[0]}
                                                        alt={mediaTitle || 'Photo 1'}
                                                        className="col-span-2 w-full h-[140px] object-cover"
                                                      />
                                                      <img
                                                        src={photoUrls[1]}
                                                        alt={mediaTitle || 'Photo 2'}
                                                        className="w-full h-[100px] object-cover"
                                                      />
                                                      <img
                                                        src={photoUrls[2]}
                                                        alt={mediaTitle || 'Photo 3'}
                                                        className="w-full h-[100px] object-cover"
                                                      />
                                                    </>
                                                  ) : (
                                                    photoUrls.slice(0, 2).map((url, i) => (
                                                      <img
                                                        key={i}
                                                        src={url}
                                                        alt={mediaTitle ? `${mediaTitle} ${i + 1}` : `Photo ${i + 1}`}
                                                        className="w-full h-[130px] object-cover"
                                                      />
                                                    ))
                                                  )}
                                                </div>
                                              )}
                                              {mediaTitle && (
                                                <p className={`px-3 pt-2 text-xs ${isSent ? 'text-primary-foreground/80' : 'text-muted-foreground'}`}>
                                                  {mediaTitle}
                                                </p>
                                              )}
                                              <div className="flex items-center justify-end gap-1 px-3 pb-3 pt-1">
                                                {sentBy && (
                                                  sentBy === 'ai'
                                                    ? <BotIcon className={`h-2.5 w-2.5 ${isSent ? 'text-primary-foreground/60' : 'text-muted-foreground'}`} />
                                                    : <UserIcon className={`h-2.5 w-2.5 ${isSent ? 'text-primary-foreground/60' : 'text-muted-foreground'}`} />
                                                )}
                                                {sentBy && (
                                                  <span className={`text-[10px] leading-none ${isSent ? 'text-primary-foreground/60' : 'text-muted-foreground'}`}>
                                                    {sentBy === 'ai' ? 'AI' : 'Manager'}
                                                  </span>
                                                )}
                                                <p className={`text-[11px] leading-none ${isSent ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                                                  {timestamp}
                                                </p>
                                              </div>
                                            </div>
                                          ) : (
                                            <div className="px-4 py-3">
                                              {messageText && <p className="text-sm whitespace-pre-wrap break-words leading-6">{messageText}</p>}
                                              <div className="mt-2 flex items-center justify-end gap-1">
                                                {sentBy && (
                                                  sentBy === 'ai'
                                                    ? <BotIcon className={`h-2.5 w-2.5 ${isSent ? 'text-primary-foreground/60' : 'text-muted-foreground'}`} />
                                                    : <UserIcon className={`h-2.5 w-2.5 ${isSent ? 'text-primary-foreground/60' : 'text-muted-foreground'}`} />
                                                )}
                                                {sentBy && (
                                                  <span className={`text-[10px] leading-none ${isSent ? 'text-primary-foreground/60' : 'text-muted-foreground'}`}>
                                                    {sentBy === 'ai' ? 'AI' : 'Manager'}
                                                  </span>
                                                )}
                                                <p className={`text-[11px] leading-none ${isSent ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                                                  {timestamp}
                                                </p>
                                              </div>
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )
                                  })
                                )}
                                <div ref={telegramBottomRef} aria-hidden="true" />
                              </div>
                            </ScrollArea>
                            <div className="border-t p-4 space-y-2">
                              <Textarea
                                placeholder={t('communications.typeMessage')}
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault()
                                    handleSendMessage()
                                  }
                                }}
                                className="min-h-[100px] max-h-[200px] resize-none"
                              />
                              <div className="flex items-center justify-between">
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground" aria-label="Emoji picker">
                                      <SmileIcon className="h-4 w-4" />
                                      Emoji
                                    </Button>
                                  </PopoverTrigger>
                                  <PopoverContent className="w-72 p-3" align="start" side="top">
                                    <div className="grid grid-cols-8 gap-1">
                                      {COMMON_EMOJIS.map((emoji) => (
                                        <button
                                          key={emoji}
                                          onClick={() => setMessage(prev => prev + emoji)}
                                          className="text-xl hover:bg-muted rounded p-1.5 transition-colors leading-none"
                                        >
                                          {emoji}
                                        </button>
                                      ))}
                                    </div>
                                  </PopoverContent>
                                </Popover>
                                <div className="flex items-center gap-2">
                                  <p className="text-xs text-muted-foreground">Shift+Enter for new line</p>
                                  <Button
                                    onClick={handleSendMessage}
                                    disabled={!message.trim() || isSending}
                                    size="sm"
                                    className="gap-1.5"
                                  >
                                    <SendIcon className="h-3.5 w-3.5" />
                                    {t('leads.sendMessage')}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          </CardContent>
                        </>
                      ) : (
                        <CardContent className="flex items-center justify-center h-full min-h-[500px]">
                          <div className="text-center space-y-2">
                            <MessageSquareIcon className="h-12 w-12 mx-auto text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">
                              {t('communications.selectConversationDesc')}
                            </p>
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="instagram">
                {!instagramStatus?.connected ? (
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center space-y-4">
                        <InstagramIcon className="h-12 w-12 mx-auto text-muted-foreground" />
                        <div>
                          <h3 className="font-semibold text-lg">Connect Instagram</h3>
                          <p className="text-sm text-muted-foreground mt-2">
                            To start messaging leads via Instagram, connect your account in Settings.
                          </p>
                        </div>
                        <Button onClick={() => navigate({ to: '/settings', search: { tab: 'integrations' } })}>
                          Connect Instagram
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
                    {/* Instagram Leads List */}
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">{t('communications.title')}</CardTitle>
                        <CardDescription>
                          {t('communications.selectConversationDesc')}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="p-0">
                        <div className="p-4 border-b">
                          <Input
                            placeholder={t('leads.searchPlaceholder')}
                            value={instagramSearchQuery}
                            onChange={(e) => setInstagramSearchQuery(e.target.value)}
                          />
                        </div>
                        <ScrollArea className="h-[500px]">
                          {filteredInstagramLeads.length === 0 ? (
                            <div className="p-4 text-center text-sm text-muted-foreground">
                              {instagramSearchQuery ? 'No leads found' : 'No leads with Instagram configured'}
                            </div>
                          ) : (
                            <div className="divide-y">
                              {filteredInstagramLeads.map((lead) => {
                                const unread = getUnread(lead.id, 'instagram')
                                return (
                                <div
                                  key={lead.id}
                                  role="button"
                                  tabIndex={0}
                                  onClick={(e) => { e.preventDefault(); handleSelectLead(lead, 'instagram'); }}
                                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectLead(lead, 'instagram'); } }}
                                  className={`w-full p-4 text-left hover:bg-muted/50 transition-colors cursor-pointer block border-none bg-transparent outline-none ${
                                    selectedInstagramLead?.id === lead.id ? 'bg-muted' : ''
                                  }`}
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0 flex-1">
                                      <p className={`text-sm truncate ${unread > 0 ? 'font-semibold' : 'font-medium'}`}>
                                        {lead.contact_person || (lead.instagram_username ? `@${lead.instagram_username}` : lead.instagram_user_id)}
                                      </p>
                                      {lead.instagram_username && lead.contact_person && (
                                        <p className="text-xs text-muted-foreground mt-1">
                                          @{lead.instagram_username}
                                        </p>
                                      )}
                                    </div>
                                    <div className="flex items-center gap-1 shrink-0">
                                      {lead.ai_paused && (
                                        <span className="flex h-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white">
                                          Manual
                                        </span>
                                      )}
                                      {unread > 0 && (
                                        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[11px] font-semibold text-white">
                                          {unread > 99 ? '99+' : unread}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                                )
                              })}
                            </div>
                          )}
                        </ScrollArea>
                      </CardContent>
                    </Card>

                    {/* Instagram Message Area */}
                    <Card>
                      {selectedInstagramLead ? (
                        <>
                          <CardHeader className="border-b">
                            <div className="flex items-center justify-between">
                              <div>
                                <CardTitle className="text-base">
                                  {selectedInstagramLead.contact_person || (selectedInstagramLead.instagram_username ? `@${selectedInstagramLead.instagram_username}` : 'Unknown')}
                                </CardTitle>
                                <CardDescription>
                                  {selectedInstagramLead.contact_person
                                    ? `${selectedInstagramLead.contact_person}${selectedInstagramLead.instagram_username ? ` • @${selectedInstagramLead.instagram_username}` : ''}`
                                    : selectedInstagramLead.instagram_username
                                      ? `@${selectedInstagramLead.instagram_username}`
                                      : ''}
                                </CardDescription>
                              </div>
                              <Badge variant="secondary" className="bg-gradient-to-r from-purple-500 to-pink-500 text-white">Instagram</Badge>
                            </div>
                            <div className={`mt-1 flex flex-wrap items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm ${selectedInstagramLead.ai_paused ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                {selectedInstagramLead.ai_paused ? (
                                  <>
                                    <Badge className="bg-amber-500 text-white hover:bg-amber-500 gap-1 text-xs h-5">
                                      <HandIcon className="h-3 w-3" />
                                      Manual Mode
                                    </Badge>
                                    {selectedInstagramLead.ai_paused_at ? (
                                      <span className="text-xs text-amber-600">
                                        � \{new Date(selectedInstagramLead.ai_paused_at).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                                      </span>
                                    ) : null}
                                  </>
                                ) : (
                                  <Badge className="bg-green-600 text-white hover:bg-green-600 gap-1 text-xs h-5">
                                    <BotIcon className="h-3 w-3" />
                                    AI Active
                                  </Badge>
                                )}
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {showResetAiMemory && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-8 gap-1 border-red-200 bg-white/80 text-red-700 hover:bg-red-50"
                                    onClick={() => setResetTarget({ lead: selectedInstagramLead, channel: 'instagram' })}
                                  >
                                    <RotateCcwIcon className="h-3.5 w-3.5" />
                                    Reset AI Memory
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  disabled={isTogglingAi}
                                  className={selectedInstagramLead.ai_paused
                                    ? 'bg-green-600 hover:bg-green-700 text-white h-8 text-xs gap-1'
                                    : 'border border-amber-400 bg-transparent text-amber-700 hover:bg-amber-50 h-8 text-xs gap-1'
                                  }
                                  onClick={() => handleToggleAiPause(selectedInstagramLead, setSelectedInstagramLead)}
                                >
                                  {selectedInstagramLead.ai_paused ? (
                                    <><PlayIcon className="h-3 w-3" />Return to AI</>
                                  ) : (
                                    <><HandIcon className="h-3 w-3" />Take Control</>
                                  )}
                                </Button>
                              </div>
                            </div>
                          </CardHeader>
                          <CardContent className="p-0">
                            <ScrollArea className="h-[400px] p-4" ref={instagramScrollAreaRef}>
                              <div className="space-y-4">
                                {orderedInstagramMessages.length === 0 ? (
                                  <div className="text-center text-sm text-muted-foreground">
                                    Start a conversation with {selectedInstagramLead.contact_person || (selectedInstagramLead.instagram_username ? `@${selectedInstagramLead.instagram_username}` : selectedInstagramLead.instagram_user_id)}
                                  </div>
                                ) : (
                                  orderedInstagramMessages.map((activity) => {
                                    const isSent = activity.activity_type === 'instagram_sent'
                                    const messageText = activity.metadata?.text as string || activity.description
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
                                          className={`max-w-[80%] rounded-lg px-4 py-2 ${
                                            isSent
                                              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                                              : 'bg-muted'
                                          }`}
                                        >
                                          <p className="text-sm whitespace-pre-wrap break-words">{messageText}</p>
                                          <div className={`flex items-center justify-end gap-1 mt-1`}>
                                            {sentBy && (
                                              sentBy === 'ai'
                                                ? <BotIcon className={`h-2.5 w-2.5 ${isSent ? 'text-white/60' : 'text-muted-foreground'}`} />
                                                : <UserIcon className={`h-2.5 w-2.5 ${isSent ? 'text-white/60' : 'text-muted-foreground'}`} />
                                            )}
                                            {sentBy && (
                                              <span className={`text-[10px] leading-none ${isSent ? 'text-white/60' : 'text-muted-foreground'}`}>
                                                {sentBy === 'ai' ? 'AI' : 'Manager'}
                                              </span>
                                            )}
                                            <p className={`text-xs leading-none ${isSent ? 'text-white/70' : 'text-muted-foreground'}`}>
                                              {timestamp}
                                            </p>
                                          </div>
                                        </div>
                                      </div>
                                    )
                                  })
                                )}
                                <div ref={instagramBottomRef} aria-hidden="true" />
                              </div>
                            </ScrollArea>
                            <div className="border-t p-4 space-y-2">
                              <Textarea
                                placeholder={t('communications.typeMessage')}
                                value={instagramMessage}
                                onChange={(e) => setInstagramMessage(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault()
                                    handleSendInstagramMessage()
                                  }
                                }}
                                className="min-h-[100px] max-h-[200px] resize-none"
                              />
                              <div className="flex items-center justify-between">
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground" aria-label="Emoji picker">
                                      <SmileIcon className="h-4 w-4" />
                                      Emoji
                                    </Button>
                                  </PopoverTrigger>
                                  <PopoverContent className="w-72 p-3" align="start" side="top">
                                    <div className="grid grid-cols-8 gap-1">
                                      {COMMON_EMOJIS.map((emoji) => (
                                        <button
                                          key={emoji}
                                          onClick={() => setInstagramMessage(prev => prev + emoji)}
                                          className="text-xl hover:bg-muted rounded p-1.5 transition-colors leading-none"
                                        >
                                          {emoji}
                                        </button>
                                      ))}
                                    </div>
                                  </PopoverContent>
                                </Popover>
                                <div className="flex items-center gap-2">
                                  <p className="text-xs text-muted-foreground">Shift+Enter for new line</p>
                                  <Button
                                    onClick={handleSendInstagramMessage}
                                    disabled={!instagramMessage.trim() || isSendingInstagram}
                                    size="sm"
                                    className="gap-1.5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                                  >
                                    <SendIcon className="h-3.5 w-3.5" />
                                    {t('leads.sendMessage')}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          </CardContent>
                        </>
                      ) : (
                        <CardContent className="flex items-center justify-center h-full min-h-[500px]">
                          <div className="text-center space-y-2">
                            <InstagramIcon className="h-12 w-12 mx-auto text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">
                              {t('communications.selectConversationDesc')}
                            </p>
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="whatsapp">
                {!whatsappStatus?.connected ? (
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center space-y-4">
                        <PhoneIcon className="h-12 w-12 mx-auto text-muted-foreground" />
                        <div>
                          <h3 className="font-semibold text-lg">Connect WhatsApp Business</h3>
                          <p className="text-sm text-muted-foreground mt-2">
                            To start messaging leads via WhatsApp, connect your account in Settings.
                          </p>
                        </div>
                        <Button onClick={() => navigate({ to: '/settings', search: { tab: 'integrations' } })}>
                          Connect WhatsApp
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
                    {/* WhatsApp Leads List */}
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">{t('communications.title')}</CardTitle>
                        <CardDescription>
                          {t('communications.selectConversationDesc')}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="p-0">
                        <div className="p-4 border-b">
                          <Input
                            placeholder={t('leads.searchPlaceholder')}
                            value={whatsappSearchQuery}
                            onChange={(e) => setWhatsappSearchQuery(e.target.value)}
                          />
                        </div>
                        <ScrollArea className="h-[500px]">
                          {filteredWhatsAppLeads.length === 0 ? (
                            <div className="p-4 text-center text-sm text-muted-foreground">
                              {whatsappSearchQuery ? 'No leads found' : 'No leads with WhatsApp configured'}
                            </div>
                          ) : (
                            <div className="divide-y">
                              {filteredWhatsAppLeads.map((lead) => {
                                const unread = getUnread(lead.id, 'whatsapp')
                                return (
                                <div
                                  key={lead.id}
                                  role="button"
                                  tabIndex={0}
                                  onClick={(e) => { e.preventDefault(); handleSelectLead(lead, 'whatsapp'); }}
                                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectLead(lead, 'whatsapp'); } }}
                                  className={`w-full p-4 text-left hover:bg-muted/50 transition-colors cursor-pointer block border-none bg-transparent outline-none ${
                                    selectedWhatsAppLead?.id === lead.id ? 'bg-muted' : ''
                                  }`}
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0 flex-1">
                                      <p className={`text-sm truncate ${unread > 0 ? 'font-semibold' : 'font-medium'}`}>
                                        {lead.contact_person}
                                      </p>
                                      {lead.whatsapp_phone && (
                                        <p className="text-xs text-muted-foreground mt-1">
                                          {lead.whatsapp_phone}
                                        </p>
                                      )}
                                    </div>
                                    {unread > 0 && (
                                      <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-red-500 px-1 text-[11px] font-semibold text-white">
                                        {unread > 99 ? '99+' : unread}
                                      </span>
                                    )}
                                  </div>
                                </div>
                                )
                              })}
                            </div>
                          )}
                        </ScrollArea>
                      </CardContent>
                    </Card>

                    {/* WhatsApp Message Area */}
                    <Card>
                      {selectedWhatsAppLead ? (
                        <>
                          <CardHeader className="border-b">
                            <div className="flex items-center justify-between">
                              <div>
                                <CardTitle className="text-base">{selectedWhatsAppLead.contact_person}</CardTitle>
                                <CardDescription>
                                  {selectedWhatsAppLead.contact_person}
                                  {selectedWhatsAppLead.whatsapp_phone ? ` • ${selectedWhatsAppLead.whatsapp_phone}` : ''}
                                </CardDescription>
                              </div>
                              <Badge variant="secondary" className="bg-green-500 text-white">WhatsApp</Badge>
                            </div>
                            <div className={`mt-1 flex flex-wrap items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm ${selectedWhatsAppLead.ai_paused ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                {selectedWhatsAppLead.ai_paused ? (
                                  <>
                                    <Badge className="bg-amber-500 text-white hover:bg-amber-500 gap-1 text-xs h-5">
                                      <HandIcon className="h-3 w-3" />
                                      Manual Mode
                                    </Badge>
                                    {selectedWhatsAppLead.ai_paused_at ? (
                                      <span className="text-xs text-amber-600">
                                        � \{new Date(selectedWhatsAppLead.ai_paused_at).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                                      </span>
                                    ) : null}
                                  </>
                                ) : (
                                  <Badge className="bg-green-600 text-white hover:bg-green-600 gap-1 text-xs h-5">
                                    <BotIcon className="h-3 w-3" />
                                    AI Active
                                  </Badge>
                                )}
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {showResetAiMemory && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-8 gap-1 border-red-200 bg-white/80 text-red-700 hover:bg-red-50"
                                    onClick={() => setResetTarget({ lead: selectedWhatsAppLead, channel: 'whatsapp' })}
                                  >
                                    <RotateCcwIcon className="h-3.5 w-3.5" />
                                    Reset AI Memory
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  disabled={isTogglingAi}
                                  className={selectedWhatsAppLead.ai_paused
                                    ? 'bg-green-600 hover:bg-green-700 text-white h-8 text-xs gap-1'
                                    : 'border border-amber-400 bg-transparent text-amber-700 hover:bg-amber-50 h-8 text-xs gap-1'
                                  }
                                  onClick={() => handleToggleAiPause(selectedWhatsAppLead, setSelectedWhatsAppLead)}
                                >
                                  {selectedWhatsAppLead.ai_paused ? (
                                    <><PlayIcon className="h-3 w-3" />Return to AI</>
                                  ) : (
                                    <><HandIcon className="h-3 w-3" />Take Control</>
                                  )}
                                </Button>
                              </div>
                            </div>
                          </CardHeader>
                          <CardContent className="p-0">
                            {showAiDiagnostics && (
                              <AiDiagnosticsPanel activities={whatsappMessages} channelLabel="WhatsApp" />
                            )}
                            <ScrollArea className="h-[400px] p-4" ref={whatsappScrollAreaRef}>
                              <div className="space-y-4">
                                {orderedWhatsAppMessages.length === 0 ? (
                                  <div className="text-center text-sm text-muted-foreground">
                                    Start a conversation with {selectedWhatsAppLead.contact_person}
                                  </div>
                                ) : (
                                  orderedWhatsAppMessages.map((activity) => {
                                    const isSent = activity.activity_type === 'whatsapp_sent'
                                    const messageText = activity.metadata?.text as string || activity.description
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
                                          className={`max-w-[80%] rounded-lg px-4 py-2 ${
                                            isSent
                                              ? 'bg-green-500 text-white'
                                              : 'bg-muted'
                                          }`}
                                        >
                                          <p className="text-sm whitespace-pre-wrap break-words">{messageText}</p>
                                          <div className={`flex items-center justify-end gap-1 mt-1`}>
                                            {sentBy && (
                                              sentBy === 'ai'
                                                ? <BotIcon className={`h-2.5 w-2.5 ${isSent ? 'text-white/60' : 'text-muted-foreground'}`} />
                                                : <UserIcon className={`h-2.5 w-2.5 ${isSent ? 'text-white/60' : 'text-muted-foreground'}`} />
                                            )}
                                            {sentBy && (
                                              <span className={`text-[10px] leading-none ${isSent ? 'text-white/60' : 'text-muted-foreground'}`}>
                                                {sentBy === 'ai' ? 'AI' : 'Manager'}
                                              </span>
                                            )}
                                            <p className={`text-xs leading-none ${isSent ? 'text-white/70' : 'text-muted-foreground'}`}>
                                              {timestamp}
                                            </p>
                                          </div>
                                        </div>
                                      </div>
                                    )
                                  })
                                )}
                                <div ref={whatsappBottomRef} aria-hidden="true" />
                              </div>
                            </ScrollArea>
                            <div className="border-t p-4 space-y-2">
                              <Textarea
                                placeholder={t('communications.typeMessage')}
                                value={whatsappMessage}
                                onChange={(e) => setWhatsappMessage(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault()
                                    handleSendWhatsAppMessage()
                                  }
                                }}
                                className="min-h-[100px] max-h-[200px] resize-none"
                              />
                              <div className="flex items-center justify-between">
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground" aria-label="Emoji picker">
                                      <SmileIcon className="h-4 w-4" />
                                      Emoji
                                    </Button>
                                  </PopoverTrigger>
                                  <PopoverContent className="w-72 p-3" align="start" side="top">
                                    <div className="grid grid-cols-8 gap-1">
                                      {COMMON_EMOJIS.map((emoji) => (
                                        <button
                                          key={emoji}
                                          onClick={() => setWhatsappMessage(prev => prev + emoji)}
                                          className="text-xl hover:bg-muted rounded p-1.5 transition-colors leading-none"
                                        >
                                          {emoji}
                                        </button>
                                      ))}
                                    </div>
                                  </PopoverContent>
                                </Popover>
                                <div className="flex items-center gap-2">
                                  <p className="text-xs text-muted-foreground">Shift+Enter for new line</p>
                                  <Button
                                    onClick={handleSendWhatsAppMessage}
                                    disabled={!whatsappMessage.trim() || isSendingWhatsApp}
                                    size="sm"
                                    className="gap-1.5 bg-green-500 hover:bg-green-600"
                                  >
                                    <SendIcon className="h-3.5 w-3.5" />
                                    {t('leads.sendMessage')}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          </CardContent>
                        </>
                      ) : (
                        <CardContent className="flex items-center justify-center h-full min-h-[500px]">
                          <div className="text-center space-y-2">
                            <PhoneIcon className="h-12 w-12 mx-auto text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">
                              {t('communications.selectConversationDesc')}
                            </p>
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  </div>
                )}
              </TabsContent>

            </Tabs>
          </div>
        </div>
      </div>

      <AlertDialog open={!!resetTarget} onOpenChange={(open) => { if (!open && !isResettingAiMemory) setResetTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset AI memory for this conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This temporary testing action clears the saved AI summary, extracted booking details, flow state, and other per-lead AI memory for {resetTarget?.lead.contact_person || 'this lead'}.
              The lead record and visible message history will stay in place.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isResettingAiMemory}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={!resetTarget || isResettingAiMemory}
              onClick={() => {
                if (resetTarget) {
                  void handleResetAiMemory(resetTarget)
                }
              }}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              {isResettingAiMemory ? 'Resetting…' : 'Reset AI Memory'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
