import { Lead, fetchLeadNotes, fetchPipelineStages, fetchSegments, getContactChannelLabel, getLeadStatusLabel, resolveLeadContactChannel, updateLead } from '@/lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/contexts/auth-context'
import { toast } from 'sonner'
import { LeadSourceBadge } from '@/components/lead-source-badge'
import { useLeadDiscoverySources } from '@/hooks/use-lead-discovery-sources'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, Pencil, CalendarDays, Users, BedDouble, Utensils } from 'lucide-react'

interface LeadDetailsSidebarProps {
  lead: Lead | null
  open: boolean
  onClose: () => void
  onEdit: (lead: Lead) => void
  onOpenFull?: (lead: Lead) => void
}

const STATUS_COLORS: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  new: 'default',
  attempted: 'secondary',
  contacted: 'outline',
  unqualified: 'destructive',
  nurturing: 'secondary',
  converted: 'default',
}

export function LeadDetailsSidebar({ lead, open, onClose, onEdit, onOpenFull }: LeadDetailsSidebarProps) {
  const discoverySourceOptions = useLeadDiscoverySources()
  const { data: notes = [] } = useQuery({
    queryKey: ['lead-notes', lead?.id],
    queryFn: () => fetchLeadNotes(lead!.id),
    enabled: open && !!lead?.id,
  })

  const { user } = useAuth()
  const queryClient = useQueryClient()

  const { data: stages = [] } = useQuery({
    queryKey: ['pipeline-stages'],
    queryFn: fetchPipelineStages,
    enabled: open,
  })

  const { data: segments = [] } = useQuery({
    queryKey: ['segments'],
    queryFn: fetchSegments,
    enabled: open,
  })

  const assignMutation = useMutation({
    mutationFn: (assignedTo: number | null) => updateLead(lead!.id, { assigned_to: assignedTo }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      queryClient.invalidateQueries({ queryKey: ['lead', lead!.id] })
      toast.success('Ответственный менеджер обновлен')
    },
    onError: () => {
      toast.error('Не удалось назначить менеджера')
    },
  })

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  }

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  }

  if (!lead) {
    return null
  }

  const telegramDisplay = lead.telegram_username
    ? `@${lead.telegram_username}`
    : lead.telegram_user_id || null
  const instagramDisplay = lead.instagram_username
    ? `@${lead.instagram_username}`
    : lead.instagram_user_id || null
  const stageName = getLeadStatusLabel(lead.status, stages)
  const segmentName = segments.find((segment) => segment.key === lead.segment)?.name
    || (lead.segment === 'individual' ? 'Индивидуальный' : lead.segment_display)
  const discoverySourceLabel = discoverySourceOptions.find((option) => option.value === lead.discovery_source)?.label

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto px-6">
        <SheetHeader>
          <div className="flex items-center justify-between gap-4">
            <SheetTitle className="flex-1">{lead.contact_person || 'Без имени'}</SheetTitle>
            <div className="flex items-center gap-2">
              {onOpenFull ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onOpenFull(lead)}
                  data-cayu="Button:open-lead-card"
                >
                  <FileText className="h-4 w-4" />
                  Карточка
                </Button>
              ) : null}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onEdit(lead)}
                data-cayu="Button:edit-lead"
                aria-label="Редактировать"
              >
                <Pencil className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <SheetDescription>{lead.email || ''}</SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4">

          {/* 1. Описание */}
          {lead.problem_description ? (
            <div>
              <div className="text-sm font-medium mb-1">Описание</div>
              <div className="text-sm text-muted-foreground whitespace-pre-wrap rounded-md border p-3 bg-muted/30">
                {lead.problem_description}
              </div>
            </div>
          ) : null}

          {/* 2. Детали бронирования */}
          {(lead.check_in_date || lead.check_out_date || lead.guest_count || lead.room_type_preference || lead.meal_plan) ? (
            <div className="rounded-lg border border-blue-200 bg-blue-50/60 p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-blue-800">
                <BedDouble className="h-4 w-4" />
                Детали бронирования
              </div>

              {(lead.check_in_date || lead.check_out_date) ? (
                <div className="flex items-start gap-2">
                  <CalendarDays className="h-4 w-4 mt-0.5 text-blue-500 shrink-0" />
                  <div className="text-sm">
                    <span className="text-muted-foreground">Даты: </span>
                    <span className="font-medium">
                      {lead.check_in_date ? formatDate(lead.check_in_date) : '?'}
                      {' — '}
                      {lead.check_out_date ? formatDate(lead.check_out_date) : '?'}
                    </span>
                    {lead.check_in_date && lead.check_out_date ? (
                      <span className="ml-2 text-xs text-blue-600 font-medium">
                        {Math.round((new Date(lead.check_out_date).getTime() - new Date(lead.check_in_date).getTime()) / 86400000)} ноч.
                      </span>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {lead.guest_count ? (
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-blue-500 shrink-0" />
                  <span className="text-sm">
                    <span className="text-muted-foreground">Гостей: </span>
                    <span className="font-medium">{lead.guest_count}</span>
                  </span>
                </div>
              ) : null}

              {lead.room_type_preference ? (
                <div className="flex items-center gap-2">
                  <BedDouble className="h-4 w-4 text-blue-500 shrink-0" />
                  <span className="text-sm">
                    <span className="text-muted-foreground">Номер: </span>
                    <span className="font-medium">{lead.room_type_preference}</span>
                  </span>
                </div>
              ) : null}

              {lead.meal_plan && lead.meal_plan !== 'none' ? (
                <div className="flex items-center gap-2">
                  <Utensils className="h-4 w-4 text-blue-500 shrink-0" />
                  <span className="text-sm">
                    <span className="text-muted-foreground">Питание: </span>
                    <span className="font-medium">
                      {lead.meal_plan === 'breakfast' ? 'Только завтрак' :
                       lead.meal_plan === 'lunch' ? 'Только обед' :
                       lead.meal_plan === 'dinner' ? 'Только ужин' :
                       lead.meal_plan === 'half_board_bl' ? 'Полупансион (Завтрак + Обед)' :
                       lead.meal_plan === 'half_board_bd' ? 'Полупансион (Завтрак + Ужин)' :
                       lead.meal_plan === 'full_board' ? 'Полный пансион' : lead.meal_plan}
                    </span>
                  </span>
                </div>
              ) : null}
            </div>
          ) : null}

          {/* 3. Следующие шаги */}
          {lead.next_steps ? (
            <div>
              <div className="text-sm font-medium mb-1">Следующие шаги</div>
              <div className="text-sm text-muted-foreground whitespace-pre-wrap rounded-md border p-3 bg-muted/30">
                {lead.next_steps}
              </div>
            </div>
          ) : null}

          {/* 4. Контактная информация */}
          <div className="rounded-md border divide-y text-sm">
            {lead.contact_person ? (
              <div className="flex items-center justify-between px-3 py-2">
                <span className="font-medium text-muted-foreground">Контакт</span>
                <span>{lead.contact_person}</span>
              </div>
            ) : null}
            {lead.phone ? (
              <div className="flex items-center justify-between px-3 py-2">
                <span className="font-medium text-muted-foreground">Телефон</span>
                <span>{lead.phone}</span>
              </div>
            ) : null}
            {lead.email ? (
              <div className="flex items-center justify-between px-3 py-2">
                <span className="font-medium text-muted-foreground">Email</span>
                <a href={`mailto:${lead.email}`} className="text-primary hover:underline truncate max-w-[60%]">{lead.email}</a>
              </div>
            ) : null}
            {telegramDisplay ? (
              <div className="flex items-center justify-between px-3 py-2">
                <span className="font-medium text-muted-foreground">Telegram</span>
                <span>{telegramDisplay}</span>
              </div>
            ) : null}
            {lead.whatsapp_phone ? (
              <div className="flex items-center justify-between px-3 py-2">
                <span className="font-medium text-muted-foreground">WhatsApp</span>
                <span>{lead.whatsapp_phone}</span>
              </div>
            ) : null}
            {instagramDisplay ? (
              <div className="flex items-center justify-between px-3 py-2">
                <span className="font-medium text-muted-foreground">Instagram</span>
                <span>{instagramDisplay}</span>
              </div>
            ) : null}
             <div className="flex items-center justify-between px-3 py-2">
               <span className="font-medium text-muted-foreground">Тип клиента</span>
               <Badge variant="outline">{segmentName}</Badge>
             </div>
             <div className="flex items-center justify-between px-3 py-2">
               <span className="font-medium text-muted-foreground">Канал обращения</span>
               <span>{getContactChannelLabel(resolveLeadContactChannel(lead))}</span>
             </div>
             {lead.discovery_source ? (
               <div className="flex items-center justify-between px-3 py-2">
                 <span className="font-medium text-muted-foreground">Откуда узнал</span>
                 <div className="flex max-w-[60%] flex-col items-end gap-1">
                   <LeadSourceBadge source={lead.discovery_source} label={discoverySourceLabel} />
                   {lead.discovery_source_detail ? (
                     <span className="text-right text-xs text-muted-foreground">{lead.discovery_source_detail}</span>
                   ) : null}
                 </div>
               </div>
             ) : null}
             <div className="flex items-center justify-between px-3 py-2">
               <span className="font-medium text-muted-foreground">Ответственный</span>
               <span className="font-medium">{lead.assigned_to_name || 'Не назначен'}</span>
             </div>
             <div className="flex items-center justify-between px-3 py-2">
               <span className="font-medium text-muted-foreground">Статус</span>
               <Badge variant={STATUS_COLORS[lead.status]}>{stageName}</Badge>
             </div>
           </div>

           {user && lead.assigned_to !== user.id && (
             <Button
               variant="outline"
               size="sm"
               className="w-full mt-2"
               onClick={() => assignMutation.mutate(user.id)}
               disabled={assignMutation.isPending}
             >
               Взять в работу
             </Button>
           )}

          {/* История заметок */}
          {notes.length > 0 ? (
            <div className="space-y-3 pt-4 border-t">
              <div className="text-sm font-medium">История заметок</div>
              <div className="space-y-3">
                {notes.map((note) => (
                  <div key={note.id} className="rounded-md border p-3 space-y-1">
                    <div className="text-xs text-muted-foreground">
                      {formatDateTime(note.created_at)}
                    </div>
                    <div className="text-sm whitespace-pre-wrap">{note.content}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {/* Временны́е метки */}
          <div className="space-y-2 pt-4 border-t">
            <div className="text-xs text-muted-foreground space-y-1">
              <div>Создан: {formatDate(lead.created_at)}</div>
              <div>Обновлён: {formatDate(lead.updated_at)}</div>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
