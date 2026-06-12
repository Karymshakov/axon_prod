import React, { useState, useEffect } from 'react'
import { 
  UserIcon, 
  CalendarIcon, 
  UsersIcon, 
  BedIcon, 
  UtensilsIcon, 
  SaveIcon, 
  BrainIcon, 
  AlertTriangleIcon, 
  ClipboardIcon, 
  RotateCcwIcon,
  XIcon
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { updateLead, type Lead } from '@/lib/api'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { LeadSourceBadge } from '@/components/lead-source-badge'

interface LeadDetailsSidebarProps {
  lead: Lead
  onClose?: () => void
  showResetAiMemory?: boolean
  onResetAiMemory?: () => void
  isResettingAiMemory?: boolean
}

export function LeadDetailsSidebar({
  lead,
  onClose,
  showResetAiMemory,
  onResetAiMemory,
  isResettingAiMemory,
}: LeadDetailsSidebarProps) {
  const queryClient = useQueryClient()
  const [isSaving, setIsSaving] = useState(false)

  // Local editable state fields
  const [contactPerson, setContactPerson] = useState('')
  const [checkInDate, setCheckInDate] = useState('')
  const [checkOutDate, setCheckOutDate] = useState('')
  const [guestCount, setGuestCount] = useState<number | ''>('')
  const [roomPreference, setRoomPreference] = useState('')
  const [mealPlan, setMealPlan] = useState<Lead['meal_plan']>('')
  const [notes, setNotes] = useState('')
  const [source, setSource] = useState('')

  // Initialize state when lead changes
  useEffect(() => {
    setContactPerson(lead.contact_person || '')
    setCheckInDate(lead.check_in_date || '')
    setCheckOutDate(lead.check_out_date || '')
    setGuestCount(lead.guest_count !== null && lead.guest_count !== undefined ? lead.guest_count : '')
    setRoomPreference(lead.room_type_preference || '')
    setMealPlan((lead.meal_plan || '') as Lead['meal_plan'])
    setNotes(lead.notes || '')
    setSource(lead.source || '')
  }, [lead])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    try {
      const updated = await updateLead(lead.id, {
        contact_person: contactPerson,
        check_in_date: checkInDate || null,
        check_out_date: checkOutDate || null,
        guest_count: guestCount === '' ? null : Number(guestCount),
        room_type_preference: roomPreference,
        meal_plan: mealPlan,
        notes: notes,
        source: source,
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

  // Formatting utility for date
  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  return (
    <div className="flex h-full flex-col border-l bg-card text-card-foreground">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <UserIcon className="h-5 w-5 text-primary" />
          <h3 className="font-semibold text-sm">Профиль гостя</h3>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full" onClick={onClose}>
            <XIcon className="h-4 w-4" />
          </Button>
        )}
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <form onSubmit={handleSave} className="space-y-6 p-4 pb-20">
          
          {/* Main Info */}
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">ФИО гостя</label>
              <Input 
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                className="mt-1"
                placeholder="ФИО клиента"
              />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Источник лида</label>
                <LeadSourceBadge source={lead.source} />
              </div>
              <Input 
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="mt-1"
                placeholder="Например, Реклама, Booking, Сайт..."
              />
            </div>
            {lead.phone && (
              <div>
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Телефон</span>
                <p className="text-sm font-medium mt-0.5">{lead.phone}</p>
              </div>
            )}
            <div>
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Канал общения</span>
              <div className="flex items-center gap-1.5 mt-1">
                {lead.telegram_chat_id && <Badge className="bg-blue-500 hover:bg-blue-600 text-white">Telegram</Badge>}
                {lead.whatsapp_phone && <Badge className="bg-green-600 hover:bg-green-700 text-white">WhatsApp</Badge>}
                {lead.instagram_user_id && <Badge className="bg-pink-600 hover:bg-pink-700 text-white">Instagram</Badge>}
                <Badge variant="outline">Этап: {lead.status}</Badge>
              </div>
            </div>
          </div>

          <hr className="border-border" />

          {/* Booking Info */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CalendarIcon className="h-4 w-4 text-muted-foreground" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Детали бронирования</h4>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Заезд</label>
                <Input 
                  type="date"
                  value={checkInDate}
                  onChange={(e) => setCheckInDate(e.target.value)}
                  className="mt-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Выезд</label>
                <Input 
                  type="date"
                  value={checkOutDate}
                  onChange={(e) => setCheckOutDate(e.target.value)}
                  className="mt-1 text-sm"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                <UsersIcon className="h-3.5 w-3.5" /> Кол-во гостей
              </label>
              <Input 
                type="number"
                min={1}
                value={guestCount}
                onChange={(e) => setGuestCount(e.target.value === '' ? '' : Number(e.target.value))}
                className="mt-1"
                placeholder="Например, 2"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                <BedIcon className="h-3.5 w-3.5" /> Категория номера
              </label>
              <Input 
                value={roomPreference}
                onChange={(e) => setRoomPreference(e.target.value)}
                className="mt-1"
                placeholder="Люкс, Стандарт, Семейный"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                <UtensilsIcon className="h-3.5 w-3.5" /> Питание
              </label>
              <Input 
                value={mealPlan}
                onChange={(e) => setMealPlan(e.target.value as Lead['meal_plan'])}
                className="mt-1"
                placeholder="Завтрак включен, Всё включено"
              />
            </div>
          </div>

          <hr className="border-border" />

          {/* AI Memory Context */}
          <div className="space-y-4 rounded-lg bg-muted/40 p-3 border border-dashed">
            <div className="flex items-center gap-2">
              <BrainIcon className="h-4 w-4 text-purple-600" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-purple-900">Что ИИ помнит о госте</h4>
            </div>

            {lead.problem_description && (
              <div className="space-y-1">
                <span className="text-xs font-semibold text-purple-800">Проблема / Запрос</span>
                <p className="text-xs text-muted-foreground leading-relaxed bg-white p-2 rounded border border-purple-100">
                  {lead.problem_description}
                </p>
              </div>
            )}

            {lead.current_objection && (
              <div className="space-y-1 bg-amber-50/70 p-2 rounded border border-amber-100">
                <div className="flex items-center gap-1 text-amber-800">
                  <AlertTriangleIcon className="h-3 w-3" />
                  <span className="text-xs font-semibold">Обнаружено возражение</span>
                </div>
                <p className="text-xs text-amber-900 font-medium mt-0.5">{lead.current_objection}</p>
                {lead.objection_count > 0 && (
                  <span className="text-[10px] text-amber-600 font-semibold block">Повторено раз: {lead.objection_count}</span>
                )}
              </div>
            )}

            {lead.next_steps && (
              <div className="space-y-1">
                <span className="text-xs font-semibold text-purple-800">Следующие шаги ИИ</span>
                <p className="text-xs text-muted-foreground leading-relaxed bg-white p-2 rounded border border-purple-100">
                  {lead.next_steps}
                </p>
              </div>
            )}

            {lead.preferred_contact_time && (
              <div className="space-y-0.5">
                <span className="text-xs font-semibold text-purple-800">Время контакта</span>
                <p className="text-xs text-muted-foreground">{lead.preferred_contact_time}</p>
              </div>
            )}

            {lead.agent_context && Object.keys(lead.agent_context).length > 0 && (
              <div className="space-y-1">
                <span className="text-xs font-semibold text-purple-800">Переменные контекста ИИ</span>
                <pre className="text-[10px] text-muted-foreground leading-tight bg-slate-900 text-slate-100 p-2 rounded overflow-x-auto max-h-32">
                  {JSON.stringify(lead.agent_context, null, 2)}
                </pre>
              </div>
            )}

            {showResetAiMemory && onResetAiMemory && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isResettingAiMemory}
                className="w-full gap-1 border-red-200 bg-white text-red-700 hover:bg-red-50 text-xs mt-2"
                onClick={onResetAiMemory}
              >
                <RotateCcwIcon className="h-3 w-3" />
                Сбросить контекст AI для гостя
              </Button>
            )}
          </div>

          <hr className="border-border" />

          {/* Internal Notes */}
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <ClipboardIcon className="h-4 w-4" /> Заметки менеджера (внутренние)
            </label>
            <Textarea 
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Добавьте внутренний комментарий, детали, пожелания или договоренности..."
              className="min-h-24 text-sm resize-none"
            />
          </div>

          {/* Save Button */}
          <div className="pt-2">
            <Button type="submit" disabled={isSaving} className="w-full gap-1.5">
              <SaveIcon className="h-4 w-4" />
              {isSaving ? 'Сохранение...' : 'Сохранить изменения'}
            </Button>
          </div>

        </form>
      </ScrollArea>
    </div>
  )
}
