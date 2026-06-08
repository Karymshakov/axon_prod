import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import { PlusIcon, PencilIcon, TrashIcon, LayoutGridIcon, LayoutListIcon, EyeIcon, SearchIcon, XIcon, InstagramIcon, MessageSquareIcon, PhoneIcon } from 'lucide-react'
import { fetchLeads, fetchLeadStats, fetchPipelineStages, deleteLead, updateLead, createLeadNote, type Lead } from '@/lib/api'
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
import { InlineNotesEditor } from '@/components/inline-notes-editor'
import { toast } from 'sonner'
import { ConfirmationDialog } from '@/components/confirmation-dialog'
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

function DraggableLeadCard({ lead, onEdit }: { lead: Lead; onEdit: (lead: Lead) => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `lead-${lead.id}`,
    data: { lead },
  })

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        opacity: isDragging ? 0.5 : 1,
      }
    : undefined

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <LeadCard lead={lead} onEdit={onEdit} />
    </div>
  )
}

function DroppableColumn({
  statusKey,
  children,
}: {
  statusKey: string
  children: React.ReactNode
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${statusKey}`,
    data: { status: statusKey },
  })

  return (
    <div
      ref={setNodeRef}
      className={`flex min-w-0 flex-col gap-3 rounded-lg border-2 border-dashed p-4 min-h-[200px] transition-colors ${
        isOver ? 'border-primary bg-primary/5' : ''
      }`}
    >
      {children}
    </div>
  )
}

function LeadsPage() {
  const { t } = useLanguage()
  const [view, setView] = useState<'table' | 'kanban'>('table')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingLead, setEditingLead] = useState<Lead | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [leadToDelete, setLeadToDelete] = useState<Lead | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [activeLead, setActiveLead] = useState<Lead | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

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
    return params
  }, [searchQuery, statusFilter])

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

  const deleteMutation = useMutation({
    mutationFn: deleteLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      toast.success('Lead deleted successfully')
      setDeleteDialogOpen(false)
      setLeadToDelete(null)
    },
    onError: () => {
      toast.error('Failed to delete lead')
    },
  })

  const updateLeadMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateLead(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      toast.success('Lead updated')
    },
    onError: () => {
      toast.error('Failed to update lead')
    },
  })

  const addNoteMutation = useMutation({
    mutationFn: ({ leadId, content }: { leadId: number; content: string }) =>
      createLeadNote({ lead: leadId, content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-notes'] })
      toast.success('Note added successfully')
    },
    onError: () => {
      toast.error('Failed to add note')
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

  const handleCloseSidebar = () => {
    setSidebarOpen(false)
    setSelectedLead(null)
  }

  const handleEditFromSidebar = (lead: Lead) => {
    setSidebarOpen(false)
    setEditingLead(lead)
    setDialogOpen(true)
  }

  const handleSaveNote = async (leadId: number, content: string) => {
    await addNoteMutation.mutateAsync({ leadId, content })
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString('ru-RU', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
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
      label: stage.name,
      leads: leads.filter((lead) => lead.status === stage.key),
      count: stats?.[stage.key as keyof typeof stats] || 0,
    }))

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
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
                    <ToggleGroup type="single" value={view} onValueChange={(v) => v && setView(v as 'table' | 'kanban')}>
                      <ToggleGroupItem value="table" aria-label="Table view">
                        <LayoutListIcon className="h-4 w-4" />
                      </ToggleGroupItem>
                      <ToggleGroupItem value="kanban" aria-label="Kanban view">
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
                          {stage.name}
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
                      }}
                    >
                      <XIcon className="mr-1 h-3.5 w-3.5" />
                      Clear
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>


            {/* Views */}
            {view === 'table' ? (
              <div className="px-4 lg:px-6 min-w-0">
                <div className="rounded-md border overflow-x-auto bg-background">
                  <Table className="table-fixed w-full">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[160px]">{t('common.name')}</TableHead>
                        <TableHead className="w-[130px]">{t('common.status')}</TableHead>
                        <TableHead className="w-[110px]">Source</TableHead>
                        <TableHead className="w-[280px]">{t('common.notes')}</TableHead>
                        <TableHead className="w-[130px]">{t('common.date')}</TableHead>
                        <TableHead className="w-[80px] text-right">{t('common.actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {isLoading ? (
                        <TableRow>
                          <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                            {t('common.loading')}
                          </TableCell>
                        </TableRow>
                      ) : leads.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                            {t('leads.noLeadsDesc')}
                          </TableCell>
                        </TableRow>
                      ) : (
                        leads.map((lead) => (
                          <TableRow
                            key={lead.id}
                            className="cursor-pointer hover:bg-muted/50"
                            onClick={() => handleLeadClick(lead)}
                          >
                            <TableCell>
                              <span className="block truncate font-medium text-primary underline underline-offset-2 decoration-primary/50 hover:decoration-primary cursor-pointer">
                                {lead.contact_person || '-'}
                              </span>
                              {lead.instagram_intent_tier ? (
                                <div className="mt-0.5">
                                  <InstagramIntentBadge tier={lead.instagram_intent_tier} />
                                </div>
                              ) : null}
                            </TableCell>
                            <TableCell onClick={(e) => e.stopPropagation()}>
                              <Select
                                value={lead.status}
                                onValueChange={(value) => updateLeadMutation.mutate({ id: lead.id, data: { status: value } })}
                              >
                                <SelectTrigger className="w-auto h-8 border-0 shadow-none p-0 [&>svg]:hidden">
                                  <SelectValue>
                                    <div className="flex items-center gap-1">
                                      <Badge variant={getStatusColor(lead.status)}>
                                        {stages.find((s) => s.key === lead.status)?.name || lead.status}
                                      </Badge>
                                      {lead.ai_paused && (
                                        <span className="flex h-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white">
                                          Manual
                                        </span>
                                      )}
                                    </div>
                                  </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                  {stages.map((stage) => (
                                    <SelectItem key={stage.key} value={stage.key}>
                                      <Badge variant={getStatusColor(stage.key)}>
                                        {stage.name}
                                      </Badge>
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell>
                              {lead.instagram_user_id ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-pink-50 px-2 py-0.5 text-[11px] font-medium text-pink-700 ring-1 ring-inset ring-pink-200">
                                  <InstagramIcon className="h-3 w-3" />
                                  Instagram
                                </span>
                              ) : lead.telegram_chat_id ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 ring-1 ring-inset ring-blue-200">
                                  <MessageSquareIcon className="h-3 w-3" />
                                  Telegram
                                </span>
                              ) : lead.whatsapp_phone ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-700 ring-1 ring-inset ring-green-200">
                                  <PhoneIcon className="h-3 w-3" />
                                  WhatsApp
                                </span>
                              ) : lead.source ? (
                                <span className="text-xs text-muted-foreground">{lead.source}</span>
                              ) : (
                                <span className="text-xs text-muted-foreground">—</span>
                              )}
                            </TableCell>
                            <TableCell className="align-top overflow-hidden" style={{ wordBreak: 'break-word', whiteSpace: 'normal' }} onClick={(e) => e.stopPropagation()}>
                              <InlineNotesEditor
                                value={lead.latest_note || ''}
                                onSave={(content) => handleSaveNote(lead.id, content)}
                                placeholder="Краткое описание разговора..."
                              />
                            </TableCell>
                            <TableCell>{formatDate(lead.last_contacted)}</TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => navigate({ to: '/leads/$leadId', params: { leadId: String(lead.id) } })}
                                  aria-label="View Details"
                                >
                                  <EyeIcon className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleEditLead(lead)}
                                  aria-label="Edit"
                                >
                                  <PencilIcon className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeleteClick(lead)}
                                  aria-label="Delete"
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
                <div className="flex gap-3 sm:gap-4 overflow-x-auto pb-2">
                  {leadsByStatus.map((column) => (
                    <div key={column.key} className="flex min-w-[240px] sm:min-w-[280px] flex-shrink-0 flex-col gap-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm sm:text-base font-semibold">{column.label}</h3>
                        <span className="text-xs sm:text-sm text-muted-foreground">
                          {column.leads.length}
                        </span>
                      </div>
                      <DroppableColumn statusKey={column.key}>
                        {column.leads.length === 0 ? (
                          <p className="text-center text-sm text-muted-foreground py-8">
                            {t('leads.noLeads')}
                          </p>
                        ) : (
                          column.leads.map((lead) => (
                            <DraggableLeadCard
                              key={lead.id}
                              lead={lead}
                              onEdit={handleEditLead}

                            />
                          ))
                        )}
                      </DroppableColumn>
                    </div>
                  ))}
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
        />
      </div>

      <DragOverlay>
        {activeLead ? <LeadCard lead={activeLead} onEdit={() => {}} /> : null}
      </DragOverlay>
    </DndContext>
  )
}
