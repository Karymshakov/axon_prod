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
import { updateLead, type Lead, SOURCE_OPTIONS } from '@/lib/api'
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
  const [activeTab, setActiveTab] = useState<'info' | 'ai'>('info')
  const [showRawJson, setShowRawJson] = useState(false)

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
      <div className="flex items-center justify-between border-b px-4 py-3 shrink-0 bg-muted/10">
        <div className="flex items-center gap-2">
          <UserIcon className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Профиль гостя</h3>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full hover:bg-muted" onClick={onClose}>
            <XIcon className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Modern Tabs Navigation */}
      <div className="flex border-b bg-muted/30 p-1 gap-1 shrink-0">
        <button
          type="button"
          onClick={() => setActiveTab('info')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-md transition-all ${
            activeTab === 'info'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-background/20'
          }`}
        >
          <ClipboardIcon className="h-3.5 w-3.5" />
          Данные
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('ai')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-md transition-all ${
            activeTab === 'ai'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-background/20'
          }`}
        >
          <BrainIcon className="h-3.5 w-3.5 text-purple-600" />
          ИИ-Контекст
        </button>
      </div>

      <ScrollArea className="flex-1 min-h-0 bg-background/50">
        {activeTab === 'info' ? (
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
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Источник лида</label>
                  <LeadSourceBadge source={source} className="h-4 text-[9px]" />
                </div>
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 mt-1"
                >
                  <option value="" className="bg-background text-foreground">Не указан</option>
                  {SOURCE_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value} className="bg-background text-foreground">
                      {opt.label}
                    </option>
                  ))}
                  {!SOURCE_OPTIONS.some(opt => opt.value === source) && source !== '' && (
                    <option value={source} className="bg-background text-foreground">{source}</option>
                  )}
                </select>
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
                  <Badge variant="outline" className="text-[9px] px-2 py-0.5 rounded">Этап: {lead.status}</Badge>
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
            <div className="pt-1">
              <Button type="submit" disabled={isSaving} className="w-full gap-1.5 h-9 text-xs">
                <SaveIcon className="h-3.5 w-3.5" />
                {isSaving ? 'Сохранение...' : 'Сохранить изменения'}
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-5 p-4 pb-24">
            {/* AI memory state */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <BrainIcon className="h-4 w-4 text-purple-600" />
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-purple-900">Что ИИ помнит о госте</h4>
              </div>

              {lead.problem_description ? (
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-purple-800">Проблема / Запрос</span>
                  <p className="text-xs text-muted-foreground leading-relaxed bg-purple-50/20 p-2.5 rounded-lg border border-purple-100/50">
                    {lead.problem_description}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground italic">Проблема гостя еще не определена ИИ</p>
              )}

              {lead.current_objection && (
                <div className="space-y-1 bg-amber-50/70 p-2.5 rounded-lg border border-amber-200">
                  <div className="flex items-center gap-1.5 text-amber-850">
                    <AlertTriangleIcon className="h-4 w-4 text-amber-600" />
                    <span className="text-xs font-semibold">Обнаружено возражение</span>
                  </div>
                  <p className="text-xs text-amber-900 font-medium mt-0.5">{lead.current_objection_display || lead.current_objection}</p>
                  {lead.objection_count > 0 && (
                    <span className="text-[10px] text-amber-700 font-semibold block mt-0.5">Повторено раз: {lead.objection_count}</span>
                  )}
                </div>
              )}

              {lead.next_steps && (
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-purple-800">Следующие шаги ИИ</span>
                  <p className="text-xs text-muted-foreground leading-relaxed bg-purple-50/20 p-2.5 rounded-lg border border-purple-100/50">
                    {lead.next_steps}
                  </p>
                </div>
              )}

              {lead.preferred_contact_time && (
                <div className="space-y-0.5">
                  <span className="text-xs font-semibold text-purple-800">Удобное время контакта</span>
                  <p className="text-xs text-muted-foreground">{lead.preferred_contact_time}</p>
                </div>
              )}
            </div>

            <hr className="border-border" />

            {/* AI context variables */}
            <div className="space-y-3 rounded-lg bg-muted/40 p-3 border border-dashed">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-purple-800 flex items-center gap-1">
                  <BrainIcon className="h-3.5 w-3.5 text-purple-500" />
                  Контекст ИИ
                </span>
                {lead.agent_context && Object.keys(lead.agent_context).length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowRawJson(!showRawJson)}
                    className="text-[10px] text-purple-700 hover:text-purple-900 hover:underline font-semibold"
                  >
                    {showRawJson ? 'Скрыть JSON' : 'Показать JSON'}
                  </button>
                )}
              </div>

              {lead.agent_context && Object.keys(lead.agent_context).length > 0 ? (
                showRawJson ? (
                  <pre className="text-[10px] text-muted-foreground leading-tight bg-slate-950 text-slate-100 p-2 rounded-md overflow-x-auto max-h-36 border">
                    {JSON.stringify(lead.agent_context, null, 2)}
                  </pre>
                ) : (
                  <div className="grid grid-cols-1 gap-1.5">
                    {Object.entries(lead.agent_context).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between text-[11px] p-2 rounded bg-background border border-muted shadow-sm">
                        <span className="font-semibold text-purple-950 truncate max-w-[120px]" title={key}>{key}</span>
                        <span className="text-muted-foreground truncate max-w-[150px]" title={String(value)}>{String(value)}</span>
                      </div>
                    ))}
                  </div>
                )
              ) : (
                <p className="text-xs text-muted-foreground italic">Нет сохраненных переменных контекста</p>
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
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
