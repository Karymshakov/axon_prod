import React, { useState, useEffect } from 'react'
import { 
  UserIcon, 
  CalendarIcon, 
  UsersIcon, 
  BedIcon, 
  UtensilsIcon, 
  SaveIcon, 
  ClipboardIcon, 
  XIcon,
  GitMerge
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  getLeadContactChannelsLabel,
  getLeadStatusLabel,
  resolveLeadContactChannels,
  updateLead,
  type Lead,
} from '@/lib/api'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { LeadSourceBadge } from '@/components/lead-source-badge'
import { useLeadDiscoverySources } from '@/hooks/use-lead-discovery-sources'
import { MergeLeadDialog } from './merge-lead-dialog'

interface LeadDetailsSidebarProps {
  lead: Lead
  onClose?: () => void
  showResetAiMemory?: boolean
  onResetAiMemory?: () => void
  isResettingAiMemory?: boolean
  onMergeSuccess?: (targetLeadId: number) => void
}

export function LeadDetailsSidebar({
  lead,
  onClose,
  showResetAiMemory,
  onResetAiMemory,
  isResettingAiMemory,
  onMergeSuccess,
}: LeadDetailsSidebarProps) {
  const queryClient = useQueryClient()
  const discoverySourceOptions = useLeadDiscoverySources()
  const [isSaving, setIsSaving] = useState(false)
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false)

  // Local editable state fields
  const [contactPerson, setContactPerson] = useState('')
  const [checkInDate, setCheckInDate] = useState('')
  const [checkOutDate, setCheckOutDate] = useState('')
  const [guestCount, setGuestCount] = useState<number | ''>('')
  const [roomPreference, setRoomPreference] = useState('')
  const [mealPlan, setMealPlan] = useState<Lead['meal_plan']>('')
  const [notes, setNotes] = useState('')
  const [discoverySource, setDiscoverySource] = useState<Lead['discovery_source']>('')
  const [discoverySourceDetail, setDiscoverySourceDetail] = useState('')
  const discoverySourceLabel = discoverySourceOptions.find((option) => option.value === discoverySource)?.label
  const contactChannels = resolveLeadContactChannels(lead)
  const isMergedProfile = contactChannels.length > 1

  // Initialize state when lead changes
  useEffect(() => {
    setContactPerson(lead.contact_person || '')
    setCheckInDate(lead.check_in_date || '')
    setCheckOutDate(lead.check_out_date || '')
    setGuestCount(lead.guest_count !== null && lead.guest_count !== undefined ? lead.guest_count : '')
    setRoomPreference(lead.room_type_preference || '')
    setMealPlan((lead.meal_plan || '') as Lead['meal_plan'])
    setNotes(lead.notes || '')
    setDiscoverySource(lead.discovery_source || '')
    setDiscoverySourceDetail(lead.discovery_source_detail || '')
  }, [lead])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    try {
      await updateLead(lead.id, {
        contact_person: contactPerson,
        check_in_date: checkInDate || null,
        check_out_date: checkOutDate || null,
        guest_count: guestCount === '' ? null : Number(guestCount),
        room_type_preference: roomPreference,
        meal_plan: mealPlan,
        notes: notes,
        discovery_source: discoverySource,
        discovery_source_detail: discoverySourceDetail,
      })
      
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', lead.id] })
      toast.success('Параметры гостя успешно сохранены')
    } catch (err) {
      console.error(err)
      toast.error('Не удалось сохранить изменения')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex h-full flex-col border-l bg-card text-card-foreground">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3 shrink-0 bg-muted/10">
        <div className="flex items-center gap-2">
          <UserIcon className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Данные гостя</h3>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full hover:bg-muted" onClick={onClose}>
            <XIcon className="h-4 w-4" />
          </Button>
        )}
      </div>

      <ScrollArea className="flex-1 min-h-0 bg-background/50">
        <form onSubmit={handleSave} className="space-y-5 p-4 pb-24">
            {/* Main Info */}
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">ФИО гостя</label>
                <Input 
                  value={contactPerson}
                  onChange={(e) => setContactPerson(e.target.value)}
                  className="mt-1 h-9 text-xs focus-visible:ring-primary/45"
                  placeholder="ФИО клиента"
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Канал обращения</label>
                <div className="mt-1 rounded-md border bg-muted/40 px-3 py-2 text-xs font-medium text-foreground">
                  {getLeadContactChannelsLabel(lead)}
                </div>
                <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                  {isMergedProfile
                    ? 'Объединённый профиль: сообщения из всех каналов находятся в одной карточке.'
                    : 'Канал определяется автоматически по чату гостя.'}
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Откуда узнал</label>
                  <LeadSourceBadge source={discoverySource} label={discoverySourceLabel} className="h-4 text-[9px]" />
                </div>
                <select
                  value={discoverySource}
                  onChange={(e) => setDiscoverySource(e.target.value as Lead['discovery_source'])}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 mt-1"
                >
                  <option value="" className="bg-background text-foreground">Не указано</option>
                  {discoverySourceOptions.map(opt => (
                    <option key={opt.value} value={opt.value} className="bg-background text-foreground">
                      {opt.label}
                    </option>
                  ))}
                </select>
                <Input
                  value={discoverySourceDetail}
                  onChange={(e) => setDiscoverySourceDetail(e.target.value)}
                  className="mt-2 h-9 text-xs focus-visible:ring-primary/45"
                  placeholder="Деталь: имя друга, кампания, площадка"
                />
              </div>

              {lead.phone && (
                <div>
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Телефон</span>
                  <p className="text-sm font-semibold mt-0.5 text-foreground">{lead.phone}</p>
                </div>
              )}

              <div>
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Канал общения и Этап</span>
                <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                  {lead.telegram_chat_id && <Badge className="bg-blue-500 hover:bg-blue-600 text-white font-medium text-[9px] px-2 py-0.5 rounded">Telegram</Badge>}
                  {lead.whatsapp_phone && <Badge className="bg-green-600 hover:bg-green-700 text-white font-medium text-[9px] px-2 py-0.5 rounded">WhatsApp</Badge>}
                  {lead.instagram_user_id && <Badge className="bg-pink-600 hover:bg-pink-700 text-white font-medium text-[9px] px-2 py-0.5 rounded">Instagram</Badge>}
                  <Badge variant="outline" className="text-[9px] px-2 py-0.5 rounded">Этап: {getLeadStatusLabel(lead.status)}</Badge>
                </div>
              </div>
            </div>

            <hr className="border-border" />

            {/* Booking Info */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Детали бронирования</h4>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground">Заезд</label>
                  <Input 
                    type="date"
                    value={checkInDate}
                    onChange={(e) => setCheckInDate(e.target.value)}
                    className="mt-1 text-xs"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground">Выезд</label>
                  <Input 
                    type="date"
                    value={checkOutDate}
                    onChange={(e) => setCheckOutDate(e.target.value)}
                    className="mt-1 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-medium text-muted-foreground flex items-center gap-1.5">
                  <UsersIcon className="h-3.5 w-3.5" /> Кол-во гостей
                </label>
                <Input 
                  type="number"
                  min={1}
                  value={guestCount}
                  onChange={(e) => setGuestCount(e.target.value === '' ? '' : Number(e.target.value))}
                  className="mt-1 text-xs"
                  placeholder="Например, 2"
                />
              </div>

              <div>
                <label className="text-[10px] font-medium text-muted-foreground flex items-center gap-1.5">
                  <BedIcon className="h-3.5 w-3.5" /> Категория номера
                </label>
                <Input 
                  value={roomPreference}
                  onChange={(e) => setRoomPreference(e.target.value)}
                  className="mt-1 text-xs"
                  placeholder="Люкс, Стандарт, Семейный"
                />
              </div>

              <div>
                <label className="text-[10px] font-medium text-muted-foreground flex items-center gap-1.5">
                  <UtensilsIcon className="h-3.5 w-3.5" /> Питание
                </label>
                <select
                  value={mealPlan}
                  onChange={(e) => setMealPlan(e.target.value as Lead['meal_plan'])}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 mt-1"
                >
                  <option value="" className="bg-background text-foreground">Не указано</option>
                  <option value="none" className="bg-background text-foreground">Без питания (RO)</option>
                  <option value="breakfast" className="bg-background text-foreground">Завтрак (BB)</option>
                  <option value="lunch" className="bg-background text-foreground">Обед</option>
                  <option value="dinner" className="bg-background text-foreground">Ужин</option>
                  <option value="half_board_bl" className="bg-background text-foreground">Полупансион: завтрак+обед (HB)</option>
                  <option value="half_board_bd" className="bg-background text-foreground">Полупансион: завтрак+ужин (HB)</option>
                  <option value="full_board" className="bg-background text-foreground">Полный пансион (FB)</option>
                </select>
              </div>
            </div>

            <hr className="border-border" />

            {/* Internal Notes */}
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <ClipboardIcon className="h-4 w-4" /> Заметки менеджера (внутренние)
              </label>
              <Textarea 
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Внутренний комментарий, детали бронирования, пожелания гостя..."
                className="min-h-20 text-xs resize-none"
              />
            </div>

            {/* Save Button */}
            <div className="pt-1 flex flex-col gap-2">
              <Button type="submit" disabled={isSaving} className="w-full gap-1.5 h-9 text-xs">
                <SaveIcon className="h-3.5 w-3.5" />
                {isSaving ? 'Сохранение...' : 'Сохранить изменения'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setMergeDialogOpen(true)}
                className="w-full gap-1.5 h-9 text-xs text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-900/60 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-950/20"
              >
                <GitMerge className="h-3.5 w-3.5" />
                {isMergedProfile ? 'Добавить ещё один профиль' : 'Объединить с другим гостем'}
              </Button>
            </div>
        </form>
      </ScrollArea>

      <MergeLeadDialog
        open={mergeDialogOpen}
        onOpenChange={setMergeDialogOpen}
        sourceLead={lead}
        onSuccess={onMergeSuccess}
      />
    </div>
  )
}
