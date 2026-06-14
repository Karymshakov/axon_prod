import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeftIcon, MailIcon, PhoneIcon, AlertTriangleIcon, BotIcon, HandIcon, PlayIcon, MessageSquareIcon } from 'lucide-react'
import { useState } from 'react'
import { useLanguage } from '@/contexts/language-context'
import {
  fetchLead,
  fetchPipelineStages,
  getContactChannelLabel,
  getLeadStatusLabel,
  resolveLeadContactChannel,
  updateLead,
  triggerInstagramAiResponse,
  toggleAiPause,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { InstagramIntentBadge, INTENT_TIER_CONFIG } from '@/components/lead-card'
import { LeadSourceBadge } from '@/components/lead-source-badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { LeadNotes } from '@/components/lead-notes'
import { LeadActivityTimeline } from '@/components/lead-activity-timeline'
import { LeadTasks } from '@/components/lead-tasks'
import { LeadGoals } from '@/components/lead-goals'
import { useLeadDiscoverySources } from '@/hooks/use-lead-discovery-sources'
import { toast } from 'sonner'

export const Route = createFileRoute('/_app/leads/$leadId')({
  component: LeadDetailPage,
})

function LeadDetailPage() {
  const { t } = useLanguage()
  const { leadId } = Route.useParams()
  const leadIdNum = parseInt(leadId, 10)
  const [isTriggeringAi, setIsTriggeringAi] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const discoverySourceOptions = useLeadDiscoverySources()

  const { data: lead, isLoading } = useQuery({
    queryKey: ['lead', leadIdNum],
    queryFn: () => fetchLead(leadIdNum),
  })

  const { data: stages = [] } = useQuery({
    queryKey: ['pipeline-stages'],
    queryFn: fetchPipelineStages,
  })

  const openLeadChat = () => {
    const channel = lead ? resolveLeadContactChannel(lead) : ''
    navigate({
      to: '/communications',
      search: {
        leadId: String(leadIdNum),
        channel: channel || undefined,
      } as never,
    })
  }

  const getStatusColor = (status: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    const colorMap: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      new: 'default',
      attempted: 'secondary',
      contacted: 'outline',
      unqualified: 'destructive',
      nurturing: 'secondary',
      converted: 'default',
    }
    return colorMap[status] || 'default'
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-muted-foreground">{t('leads.loadingDetails')}</p>
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-muted-foreground">{t('leads.leadNotFound')}</p>
        <Link to="/leads">
          <Button variant="link">{t('leads.backToLeads')}</Button>
        </Link>
      </div>
    )
  }

  const stageName = getLeadStatusLabel(lead.status, stages)
  const discoverySourceLabel = discoverySourceOptions.find((option) => option.value === lead.discovery_source)?.label

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
          {/* Header */}
          <div className="px-4 lg:px-6">
            <div className="flex flex-col gap-3">
              <Link to="/leads">
                <Button variant="ghost" size="sm">
                  <ArrowLeftIcon className="h-4 w-4 mr-2" />
                  {t('leads.backToLeads')}
                </Button>
              </Link>

              <div className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-bold">{lead.contact_person || 'Без имени'}</h1>

                  {/* Contact details inline */}
                  <div className="flex items-center gap-3 mt-1 text-sm">
                    {lead.email ? (
                      <a href={`mailto:${lead.email}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors">
                        <MailIcon className="h-3.5 w-3.5" />
                        <span>{lead.email}</span>
                      </a>
                    ) : null}
                    {lead.phone ? (
                      <a href={`tel:${lead.phone}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors">
                        <PhoneIcon className="h-3.5 w-3.5" />
                        <span>{lead.phone}</span>
                      </a>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <Badge variant={getStatusColor(lead.status)}>
                      {stageName}
                    </Badge>
                    {resolveLeadContactChannel(lead) ? (
                      <Badge variant="outline">{getContactChannelLabel(resolveLeadContactChannel(lead))}</Badge>
                    ) : null}
                    {lead.discovery_source ? (
                      <LeadSourceBadge source={lead.discovery_source} label={discoverySourceLabel} />
                    ) : null}
                    {lead.ai_paused ? (
                      <Badge className="gap-1 bg-amber-500 text-white hover:bg-amber-500">
                        <HandIcon className="h-3 w-3" />
                        Ручной режим
                      </Badge>
                    ) : null}
                    {lead.instagram_intent_tier ? (
                      <InstagramIntentBadge tier={lead.instagram_intent_tier} />
                    ) : null}
                    {lead.current_objection ? (
                      <Badge variant="destructive" className="gap-1">
                        <AlertTriangleIcon className="h-3 w-3" />
                        {t('leads.objectionLabel')} {lead.current_objection_display}
                      </Badge>
                    ) : null}
                  </div>

                  {/* ИИ Control — Взять управление / Вернуть ИИ */}
                  <div className={`flex items-center gap-3 mt-3 p-3 rounded-md border ${lead.ai_paused ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
                    {lead.ai_paused ? (
                      <>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <Badge className="bg-amber-500 text-white hover:bg-amber-500 gap-1 shrink-0">
                              <HandIcon className="h-3 w-3" />
                              Ручной режим
                            </Badge>
                            {lead.ai_paused_at ? (
                              <span className="text-xs text-amber-600 truncate">
                                 {new Date(lead.ai_paused_at).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700 text-white shrink-0 gap-1.5"
                          onClick={async () => {
                            try {
                              await toggleAiPause(lead.id)
                              queryClient.invalidateQueries({ queryKey: ['lead', leadIdNum] })
                              queryClient.invalidateQueries({ queryKey: ['leads'] })
                              queryClient.invalidateQueries({ queryKey: ['lead-activities', leadIdNum] })
                              toast.success('ИИ-агент снова включен')
                            } catch {
                              toast.error('Не удалось переключить ИИ')
                            }
                          }}
                        >
                          <PlayIcon className="h-3.5 w-3.5" />
                          Вернуть ИИ
                        </Button>
                      </>
                    ) : (
                      <>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <Badge className="bg-green-600 text-white hover:bg-green-600 gap-1 shrink-0">
                              <BotIcon className="h-3 w-3" />
                              ИИ активен
                            </Badge>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-amber-400 text-amber-700 hover:bg-amber-50 shrink-0 gap-1.5"
                          onClick={async () => {
                            try {
                              await toggleAiPause(lead.id)
                              queryClient.invalidateQueries({ queryKey: ['lead', leadIdNum] })
                              queryClient.invalidateQueries({ queryKey: ['leads'] })
                              queryClient.invalidateQueries({ queryKey: ['lead-activities', leadIdNum] })
                              toast.success('ИИ на паузе — управление перешло к вам')
                            } catch {
                              toast.error('Не удалось переключить ИИ')
                            }
                          }}
                        >
                          <HandIcon className="h-3.5 w-3.5" />
                          Взять управление
                        </Button>
                      </>
                    )}
                  </div>

                  {/* Instagram intent tier controls — only for Instagram leads */}
                  {lead.instagram_user_id ? (
                    <div className="flex flex-wrap items-center gap-2 mt-3">
                      <span className="text-xs text-muted-foreground">{t('leads.instagramIntent')}</span>
                      <Select
                        value={lead.instagram_intent_tier ?? ''}
                        onValueChange={async (value) => {
                          await updateLead(lead.id, { instagram_intent_tier: (value || null) as 'booking_intent' | 'soft_interest' | 'not_relevant' | null })
                          queryClient.invalidateQueries({ queryKey: ['lead', leadIdNum] })
                          queryClient.invalidateQueries({ queryKey: ['leads'] })
                        }}
                      >
                        <SelectTrigger className="h-7 w-[160px] text-xs">
                          <SelectValue placeholder={t('leads.notClassified')} />
                        </SelectTrigger>
                        <SelectContent>
                          {(Object.entries(INTENT_TIER_CONFIG) as Array<[keyof typeof INTENT_TIER_CONFIG, typeof INTENT_TIER_CONFIG[keyof typeof INTENT_TIER_CONFIG]]>).map(([value, cfg]) => (
                            <SelectItem key={value} value={value} className="text-xs">
                              {cfg.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {lead.instagram_intent_tier === 'booking_intent' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isTriggeringAi}
                          onClick={async () => {
                            setIsTriggeringAi(true)
                            try {
                              await triggerInstagramAiResponse(lead.id)
                              toast.success(t('leads.aiResponseTriggered'))
                            } catch {
                              toast.error(t('leads.aiResponseError'))
                            } finally {
                              setIsTriggeringAi(false)
                            }
                          }}
                        >
                          {isTriggeringAi ? t('leads.triggering') : t('leads.triggerAiResponse')}
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={openLeadChat} className="gap-2">
                    <MessageSquareIcon className="h-4 w-4" />
                    Открыть чат
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="px-4 lg:px-6">
            <div className="grid gap-4 xl:grid-cols-2">
              <LeadTasks leadId={leadIdNum} />
              <LeadGoals leadId={leadIdNum} />
              <LeadActivityTimeline leadId={leadIdNum} />
              <LeadNotes leadId={leadIdNum} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
