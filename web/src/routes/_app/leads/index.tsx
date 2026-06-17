import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, useMemo } from 'react'
import { PlusIcon, PencilIcon, TrashIcon, LayoutGridIcon, LayoutListIcon, SearchIcon, XIcon, InstagramIcon, MessageSquareIcon, PhoneIcon } from 'lucide-react'
import {
  CONTACT_CHANNEL_OPTIONS,
  fetchLeads,
  fetchLeadStats,
  fetchPipelineStages,
  deleteLead,
  updateLead,
  getLeadStatusLabel,
  getContactChannelLabel,
  resolveLeadContactChannel,
  type Lead,
} from '@/lib/api'
import { useLeadDiscoverySources } from '@/hooks/use-lead-discovery-sources'
import { LeadSourceBadge } from '@/components/lead-source-badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { LeadCard, InstagramIntentBadge } from '@/components/lead-card'
import { LeadDialog } from '@/components/lead-dialog'
import { LeadDetailsSidebar } from '@/components/lead-details-sidebar'
import { toast } from 'sonner'
import { ConfirmationDialog } from '@/components/confirmation-dialog'
import { useAuth } from '@/contexts/auth-context'
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
} from '@dnd-kit/core'
import { useDroppable, useDraggable } from '@dnd-kit/core'

export const Route = createFileRoute('/_app/leads/')({
  component: LeadsPage,
})

const getStatusColor = (statusKey: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
  const colorMap: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    new: 'default',
    attempted: 'secondary',
    contacted: 'outline',
    unqualified: 'destructive',
    nurturing: 'secondary',
    converted: 'default',
  }
  return colorMap[statusKey] || 'default'
}

type LeadsViewMode = 'table' | 'kanban'

const KANBAN_STAGE_TONES = [
  {
    accent: 'bg-blue-500',
    header: 'border-blue-200 bg-blue-50/70 text-blue-950 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-100',
    drop: 'border-blue-300 bg-blue-50/60 dark:border-blue-800 dark:bg-blue-950/20',
  },
  {
    accent: 'bg-violet-500',
    header: 'border-violet-200 bg-violet-50/70 text-violet-950 dark:border-violet-900/50 dark:bg-violet-950/20 dark:text-violet-100',
    drop: 'border-violet-300 bg-violet-50/60 dark:border-violet-800 dark:bg-violet-950/20',
  },
  {
    accent: 'bg-amber-500',
    header: 'border-amber-200 bg-amber-50/70 text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-100',
    drop: 'border-amber-300 bg-amber-50/60 dark:border-amber-800 dark:bg-amber-950/20',
  },
  {
    accent: 'bg-emerald-500',
    header: 'border-emerald-200 bg-emerald-50/70 text-emerald-950 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-100',
    drop: 'border-emerald-300 bg-emerald-50/60 dark:border-emerald-800 dark:bg-emerald-950/20',
  },
  {
    accent: 'bg-slate-500',
    header: 'border-slate-200 bg-slate-50/80 text-slate-950 dark:border-slate-800 dark:bg-slate-950/25 dark:text-slate-100',
    drop: 'border-slate-300 bg-slate-50/60 dark:border-slate-700 dark:bg-slate-950/20',
  },
]

function getKanbanStageTone(statusKey: string, index: number) {
  const knownToneByKey: Record<string, number> = {
    new: 0,
    attempted: 1,
    contacted: 1,
    nurturing: 2,
    converted: 3,
    won: 3,
    done: 3,
    unqualified: 4,
    lost: 4,
  }
  return KANBAN_STAGE_TONES[knownToneByKey[statusKey] ?? (index % KANBAN_STAGE_TONES.length)]
}

function getLeadsViewStorageKey(userId: number | undefined) {
  if (!userId) return null
  return `leads:view:${userId}`
}

function getLegacyLeadsViewStorageKey(userId: number | undefined, orgSlug: string | null | undefined) {
  if (!userId) return null
  return `leads:view:${userId}:${orgSlug || 'default'}`
}

function readStoredLeadsView(userId: number | undefined, orgSlug: string | null | undefined): LeadsViewMode | null {
  if (typeof window === 'undefined') return null

  const storageKey = getLeadsViewStorageKey(userId)
  const legacyStorageKey = getLegacyLeadsViewStorageKey(userId, orgSlug)
  const savedView = storageKey ? window.localStorage.getItem(storageKey) : null
  const legacySavedView = legacyStorageKey ? window.localStorage.getItem(legacyStorageKey) : null
  const view = savedView || legacySavedView

  return view === 'table' || view === 'kanban' ? view : null
}

function DraggableLeadCard({
  lead,
  onEdit,
  onOpen,
  onOpenChat,
  discoverySourceLabel,
}: {
  lead: Lead
  onEdit: (lead: Lead) => void
  onOpen: (lead: Lead) => void
  onOpenChat: (lead: Lead) => void
  discoverySourceLabel?: string
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `lead-${lead.id}`,
    data: { lead },
  })

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        opacity: isDragging ? 0.45 : 1,
        transition: isDragging ? undefined : 'transform 200ms cubic-bezier(0.2, 0, 0, 1), opacity 140ms ease',
      }
    : undefined

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`touch-none will-change-transform ${isDragging ? 'scale-[0.98]' : 'transition-transform duration-200 ease-out'}`}
    >
      <LeadCard
        lead={lead}
        onEdit={onEdit}
        onOpen={onOpen}
        onOpenChat={onOpenChat}
        discoverySourceLabel={discoverySourceLabel}
      />
    </div>
  )
}

function DroppableColumn({
  statusKey,
  tone,
  children,
}: {
  statusKey: string
  tone: { drop: string }
  children: React.ReactNode
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${statusKey}`,
    data: { status: statusKey },
  })

  return (
    <div
      ref={setNodeRef}
      className={`flex max-h-[calc(100vh-245px)] min-h-[240px] min-w-0 flex-1 flex-col gap-1.5 overflow-y-auto rounded-md border border-dashed p-2 transition-all duration-200 ${
        isOver ? `${tone.drop} shadow-inner ring-2 ring-primary/25 scale-[1.01]` : 'border-border/70 bg-background/70'
      }`}
    >
      {children}
    </div>
  )
}

function LeadsPage() {
  const { t } = useLanguage()
  const { user } = useAuth()
  const [view, setView] = useState<LeadsViewMode>(() => (
    readStoredLeadsView(user?.id, user?.current_organization_slug) || 'table'
  ))
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [channelFilter, setChannelFilter] = useState('')
  const [discoveryFilter, setDiscoveryFilter] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingLead, setEditingLead] = useState<Lead | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [leadToDelete, setLeadToDelete] = useState<Lead | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [activeLead, setActiveLead] = useState<Lead | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const discoverySourceOptions = useLeadDiscoverySources()
  const viewStorageKey = useMemo(
    () => getLeadsViewStorageKey(user?.id),
    [user?.id],
  )

  useEffect(() => {
    const savedView = readStoredLeadsView(user?.id, user?.current_organization_slug)
    if (savedView) {
      setView(savedView)
      if (viewStorageKey) {
        window.localStorage.setItem(viewStorageKey, savedView)
      }
    }
  }, [user?.id, user?.current_organization_slug, viewStorageKey])

  const handleViewChange = (nextView: string) => {
    if (nextView !== 'table' && nextView !== 'kanban') return
    setView(nextView)
    if (viewStorageKey) {
      window.localStorage.setItem(viewStorageKey, nextView)
    }
  }

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  )

  const fetchParams = useMemo(() => {
    const params: Record<string, string> = {}
    if (searchQuery) params.search = searchQuery
    if (statusFilter && statusFilter !== 'all') params.status = statusFilter
    if (channelFilter && channelFilter !== 'all') params.contact_channel = channelFilter
    if (discoveryFilter && discoveryFilter !== 'all') params.discovery_source = discoveryFilter
    return params
  }, [searchQuery, statusFilter, channelFilter, discoveryFilter])

  const { data: stats } = useQuery({
    queryKey: ['lead-stats'],
    queryFn: () => fetchLeadStats(),
  })

  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['leads', fetchParams],
    queryFn: () => fetchLeads(fetchParams),
  })

  const { data: stages = [] } = useQuery({
    queryKey: ['pipeline-stages'],
    queryFn: () => fetchPipelineStages(),
  })

  const displayedLeads = useMemo(() => {
    return leads.filter((lead) => {
      if (channelFilter && channelFilter !== 'all') {
        const actualChannel = resolveLeadContactChannel(lead)
        if (actualChannel !== channelFilter) return false
      }
      if (discoveryFilter && discoveryFilter !== 'all') {
        if ((lead.discovery_source || '') !== discoveryFilter) return false
      }
      return true
    })
  }, [leads, channelFilter, discoveryFilter])

  const deleteMutation = useMutation({
    mutationFn: deleteLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      toast.success('Лид удален')
      setDeleteDialogOpen(false)
      setLeadToDelete(null)
    },
    onError: () => {
      toast.error('Не удалось удалить лид')
    },
  })

  const updateLeadMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateLead(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: ['leads'] })
      const previousLeads = queryClient.getQueriesData<Lead[]>({ queryKey: ['leads'] })

      queryClient.setQueriesData<Lead[]>({ queryKey: ['leads'] }, (currentLeads) => {
        if (!currentLeads) return currentLeads
        return currentLeads.map((lead) => (
          lead.id === id ? { ...lead, ...data } : lead
        ))
      })

      return { previousLeads }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      toast.success('Лид обновлен')
    },
    onError: (_error, _variables, context) => {
      context?.previousLeads.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data)
      })
      toast.error('Не удалось обновить лид')
    },
  })

  const handleAddLead = () => {
    setEditingLead(null)
    setDialogOpen(true)
  }

  const handleEditLead = (lead: Lead) => {
    setEditingLead(lead)
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    setDialogOpen(false)
    setEditingLead(null)
  }

  const handleDeleteClick = (lead: Lead) => {
    setLeadToDelete(lead)
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = () => {
    if (leadToDelete) {
      deleteMutation.mutate(leadToDelete.id)
    }
  }

  const handleLeadClick = (lead: Lead) => {
    setSelectedLead(lead)
    setSidebarOpen(true)
  }

  const openLeadChat = (lead: Lead) => {
    const channel = resolveLeadContactChannel(lead)
    navigate({
      to: '/communications',
      search: {
        leadId: String(lead.id),
        channel: channel || undefined,
      } as never,
    })
  }

  const handleCloseSidebar = () => {
    setSidebarOpen(false)
    setSelectedLead(null)
  }

  const handleEditFromSidebar = (lead: Lead) => {
    setSidebarOpen(false)
    setEditingLead(lead)
    setDialogOpen(true)
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString('ru-RU', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  const formatBooking = (lead: Lead) => {
    const parts: string[] = []
    if (lead.check_in_date) parts.push(`заезд ${formatDate(lead.check_in_date)}`)
    if (lead.check_out_date) parts.push(`выезд ${formatDate(lead.check_out_date)}`)
    if (lead.guest_count) parts.push(`${lead.guest_count} гост.`)
    if (lead.room_type_preference) parts.push(lead.room_type_preference)
    return parts.length ? parts.join(' · ') : '—'
  }

  const getLeadSummary = (lead: Lead) =>
    lead.problem_description || lead.latest_note || lead.notes || lead.next_steps || ''

  const mealPlanLabelMap: Record<string, string> = {
    breakfast: 'завтрак',
    lunch: 'обед',
    dinner: 'ужин',
    half_board_bl: 'завтрак + обед',
    half_board_bd: 'завтрак + ужин',
    full_board: 'полный пансион',
  }

  const getStageLabel = (statusKey: string) => getLeadStatusLabel(statusKey, stages)
  const getDiscoverySourceOptionLabel = (source: string | null | undefined) =>
    discoverySourceOptions.find((option) => option.value === source)?.label

  const renderChannelBadge = (lead: Lead) => {
    const channel = resolveLeadContactChannel(lead)
    if (!channel) {
      return <span className="text-xs text-muted-foreground">—</span>
    }

    const label = getContactChannelLabel(channel)
    const config = {
      instagram: {
        icon: <InstagramIcon className="h-3 w-3" />,
        className: 'bg-pink-50 text-pink-700 ring-pink-200 dark:bg-pink-950/25 dark:text-pink-400 dark:ring-pink-900/40',
      },
      telegram: {
        icon: <MessageSquareIcon className="h-3 w-3" />,
        className: 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950/25 dark:text-blue-400 dark:ring-blue-900/40',
      },
      whatsapp: {
        icon: <PhoneIcon className="h-3 w-3" />,
        className: 'bg-green-50 text-green-700 ring-green-200 dark:bg-green-950/25 dark:text-green-400 dark:ring-green-900/40',
      },
      manual: {
        icon: null,
        className: 'bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-950/25 dark:text-slate-400 dark:ring-slate-900/40',
      },
    }[channel]

    return (
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          openLeadChat(lead)
        }}
        className={`inline-flex max-w-full items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset transition hover:shadow-sm ${config.className}`}
        title={`Открыть чат: ${label}`}
        aria-label={`Открыть чат: ${label}`}
      >
        {config.icon}
        <span className="truncate">{label}</span>
      </button>
    )
  }

  const handleDragStart = (event: DragStartEvent) => {
    const lead = event.active.data.current?.lead as Lead
    setActiveLead(lead)
  }

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveLead(null)

    const { active, over } = event

    if (!over) return

    const leadId = active.data.current?.lead?.id
    const newStatus = over.data.current?.status

    if (!leadId || !newStatus) return

    const lead = leads.find((l) => l.id === leadId)
    if (!lead || lead.status === newStatus) return

    updateLeadMutation.mutate({ id: leadId, data: { status: newStatus } })
  }

  const leadsByStatus = stages
    .sort((a, b) => a.order - b.order)
    .map((stage) => ({
      key: stage.key,
      label: getLeadStatusLabel(stage.key, stages),
      leads: displayedLeads.filter((lead) => lead.status === stage.key),
      count: stats?.[stage.key as keyof typeof stats] || 0,
    }))

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActiveLead(null)}
    >
      <div className="flex flex-1 flex-col min-w-0 bg-muted/40">
        <div className="flex flex-1 flex-col gap-2 min-w-0">
          <div className="flex flex-col gap-3 py-3 md:gap-4 md:py-4">
            {/* Header */}
            <div className="px-4 lg:px-6">
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h1 className="text-xl sm:text-2xl font-bold">{t('leads.title')}</h1>
                    <p className="text-sm text-muted-foreground hidden sm:block">
                      {t('leads.subtitle')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <ToggleGroup type="single" value={view} onValueChange={handleViewChange}>
                      <ToggleGroupItem value="table" aria-label="Список">
                        <LayoutListIcon className="h-4 w-4" />
                      </ToggleGroupItem>
                      <ToggleGroupItem value="kanban" aria-label="Карточки">
                        <LayoutGridIcon className="h-4 w-4" />
                      </ToggleGroupItem>
                    </ToggleGroup>
                    <Button onClick={handleAddLead} className="bg-primary text-primary-foreground hover:bg-primary/90">
                      <PlusIcon className="h-4 w-4" />
                      <span className="hidden sm:inline">{t('leads.addLead')}</span>
                      <span className="sm:hidden">{t('common.add')}</span>
                    </Button>
                  </div>
                </div>
                {/* Search and Filters */}
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative w-full sm:w-[220px]">
                    <SearchIcon className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      placeholder={t('leads.searchPlaceholder')}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 h-9"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery('')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        <XIcon className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[140px] h-9">
                      <SelectValue placeholder={t('leads.allStatuses')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('leads.allStatuses')}</SelectItem>
                      {stages.map((stage) => (
                        <SelectItem key={stage.key} value={stage.key}>
                          {getStageLabel(stage.key)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Select value={channelFilter} onValueChange={setChannelFilter}>
                    <SelectTrigger className="w-[150px] h-9">
                      <SelectValue placeholder="Все каналы" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Все каналы</SelectItem>
                      {CONTACT_CHANNEL_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Select value={discoveryFilter} onValueChange={setDiscoveryFilter}>
                    <SelectTrigger className="w-[170px] h-9">
                      <SelectValue placeholder="Откуда узнал" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Любой источник</SelectItem>
                      {discoverySourceOptions.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {(Object.keys(fetchParams).length > 0) ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-9 px-2 text-muted-foreground"
                      onClick={() => {
                        setStatusFilter('')
                        setSearchQuery('')
                        setChannelFilter('')
                        setDiscoveryFilter('')
                      }}
                    >
                      <XIcon className="mr-1 h-3.5 w-3.5" />
                      Сбросить
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>


            {/* Views */}
            {view === 'table' ? (
              <div className="px-4 lg:px-6 min-w-0">
                <div className="rounded-md border overflow-x-auto bg-background">
                  <Table className="min-w-[980px] w-full table-fixed">
                    <colgroup>
                      <col className="w-[250px]" />
                      <col className="w-[130px]" />
                      <col className="w-[120px]" />
                      <col className="w-[250px]" />
                      <col className="w-[150px]" />
                      <col className="w-[130px]" />
                      <col className="w-[64px]" />
                    </colgroup>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Гость</TableHead>
                        <TableHead>Этап</TableHead>
                        <TableHead>Канал</TableHead>
                        <TableHead>Бронирование</TableHead>
                        <TableHead>Откуда узнал</TableHead>
                        <TableHead>Последний контакт</TableHead>
                        <TableHead className="text-right">Действия</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {isLoading ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                            {t('common.loading')}
                          </TableCell>
                        </TableRow>
                      ) : displayedLeads.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                            {t('leads.noLeadsDesc')}
                          </TableCell>
                        </TableRow>
                      ) : (
                        displayedLeads.map((lead) => (
                          <TableRow
                            key={lead.id}
                            className="cursor-pointer hover:bg-muted/50"
                            onClick={() => handleLeadClick(lead)}
                          >
                            <TableCell className="py-3 align-top">
                              <span className="block truncate font-medium text-primary underline underline-offset-2 decoration-primary/50 hover:decoration-primary cursor-pointer">
                                {lead.contact_person || '-'}
                              </span>
                              {getLeadSummary(lead) ? (
                                <span className="mt-1 block truncate text-xs text-muted-foreground" title={getLeadSummary(lead)}>
                                  {getLeadSummary(lead)}
                                </span>
                              ) : (
                                <span className="mt-1 block text-xs text-muted-foreground">Нет краткого запроса</span>
                              )}
                              {lead.instagram_intent_tier ? (
                                <div className="mt-0.5">
                                  <InstagramIntentBadge tier={lead.instagram_intent_tier} />
                                </div>
                              ) : null}
                            </TableCell>
                            <TableCell className="py-3 align-top" onClick={(e) => e.stopPropagation()}>
                              <Select
                                value={lead.status}
                                onValueChange={(value) => updateLeadMutation.mutate({ id: lead.id, data: { status: value } })}
                              >
                                <SelectTrigger className="w-auto h-8 border-0 shadow-none p-0 [&>svg]:hidden">
                                  <SelectValue>
                                    <div className="flex items-center gap-1">
                                      <Badge variant={getStatusColor(lead.status)}>
                                        {getStageLabel(lead.status)}
                                      </Badge>
                                      {lead.ai_paused && (
                                        <span className="flex h-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white">
                                          Ручной
                                        </span>
                                      )}
                                    </div>
                                  </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                  {stages.map((stage) => (
                                    <SelectItem key={stage.key} value={stage.key}>
                                      <Badge variant={getStatusColor(stage.key)}>
                                        {getStageLabel(stage.key)}
                                      </Badge>
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell className="py-3 align-top">
                              <div className="flex flex-col gap-1 items-start">
                                {renderChannelBadge(lead)}
                              </div>
                            </TableCell>
                            <TableCell className="py-3 align-top text-xs text-muted-foreground min-w-0">
                              <span className="block truncate" title={formatBooking(lead)}>{formatBooking(lead)}</span>
                              {lead.meal_plan && lead.meal_plan !== 'none' ? (
                                <span className="mt-1 block truncate">Питание: {mealPlanLabelMap[lead.meal_plan] || lead.meal_plan}</span>
                              ) : null}
                            </TableCell>
                            <TableCell className="py-3 align-top">
                              {lead.discovery_source ? (
                                <div className="flex flex-col gap-1 items-start">
                                  <LeadSourceBadge
                                    source={lead.discovery_source}
                                    label={getDiscoverySourceOptionLabel(lead.discovery_source)}
                                  />
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">—</span>
                              )}
                            </TableCell>
                            <TableCell className="py-3 align-top">{formatDate(lead.last_contacted)}</TableCell>
                            <TableCell className="py-3 text-right align-top">
                              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleEditLead(lead)}
                                  aria-label="Редактировать"
                                >
                                  <PencilIcon className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeleteClick(lead)}
                                  aria-label="Удалить"
                                >
                                  <TrashIcon className="h-4 w-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : (
              <div className="px-4 lg:px-6">
                <div className="flex gap-2.5 overflow-x-auto pb-2">
                  {leadsByStatus.map((column, index) => {
                    const tone = getKanbanStageTone(column.key, index)
                    return (
                    <div key={column.key} className="flex min-w-[215px] flex-shrink-0 flex-col gap-1.5 sm:min-w-[235px]">
                      <div className={`rounded-md border px-2.5 py-2 shadow-sm ${tone.header}`}>
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${tone.accent}`} />
                            <h3 className="truncate text-[13px] font-semibold">{column.label}</h3>
                          </div>
                          <span className="rounded-full bg-background/80 px-2 py-0.5 text-xs font-semibold text-muted-foreground">
                            {column.leads.length}
                          </span>
                        </div>
                      </div>
                      <DroppableColumn statusKey={column.key} tone={tone}>
                        {column.leads.length === 0 ? (
                          <p className="rounded-md border border-dashed bg-muted/30 px-3 py-5 text-center text-xs text-muted-foreground">
                            {t('leads.noLeads')}
                          </p>
                        ) : (
                          column.leads.map((lead) => (
                            <DraggableLeadCard
                              key={lead.id}
                              lead={lead}
                              onEdit={handleEditLead}
                              onOpen={handleLeadClick}
                              onOpenChat={openLeadChat}
                              discoverySourceLabel={getDiscoverySourceOptionLabel(lead.discovery_source)}

                            />
                          ))
                        )}
                      </DroppableColumn>
                    </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        <LeadDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          lead={editingLead}
          defaultSegment="individual"
          onClose={handleCloseDialog}
        />

        <ConfirmationDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          onConfirm={handleConfirmDelete}
          title={t('leads.deleteLead')}
          description={`${t('leads.deleteLeadDesc')}`}
          confirmText={t('common.delete')}
          variant="destructive"
        />

        <LeadDetailsSidebar
          lead={selectedLead}
          open={sidebarOpen}
          onClose={handleCloseSidebar}
          onEdit={handleEditFromSidebar}
          onOpenFull={(lead) => navigate({ to: '/leads/$leadId', params: { leadId: String(lead.id) } })}
        />
      </div>

      <DragOverlay>
        {activeLead ? (
          <LeadCard
            lead={activeLead}
            onEdit={() => {}}
            onOpen={() => {}}
            onOpenChat={() => {}}
            discoverySourceLabel={getDiscoverySourceOptionLabel(activeLead.discovery_source)}
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
