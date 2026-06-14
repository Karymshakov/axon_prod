import { MailIcon, PhoneIcon, FileTextIcon, DollarSignIcon, CalendarDaysIcon, HandIcon, InstagramIcon, MessageSquareIcon } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import type { MouseEvent } from 'react'
import { getContactChannelLabel, resolveLeadContactChannel, type Lead } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LeadSourceBadge } from '@/components/lead-source-badge'

export const INTENT_TIER_CONFIG = {
  booking_intent: { label: 'Намерение забронировать', className: 'bg-green-100 text-green-800 border-green-200' },
  soft_interest: { label: 'Мягкий интерес', className: 'bg-yellow-100 text-yellow-800 border-yellow-200' },
  not_relevant: { label: 'Не актуально', className: 'bg-gray-100 text-gray-600 border-gray-200' },
} as const

export function InstagramIntentBadge({ tier }: { tier: NonNullable<Lead['instagram_intent_tier']> }) {
  const cfg = INTENT_TIER_CONFIG[tier]
  return (
    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 h-4 font-medium ${cfg.className}`}>
      {cfg.label}
    </Badge>
  )
}

interface LeadCardProps {
  lead: Lead
  onEdit: (lead: Lead) => void
  onOpen?: (lead: Lead) => void
  onOpenChat?: (lead: Lead) => void
  discoverySourceLabel?: string
}

export function LeadCard({ lead, onOpen, onOpenChat, discoverySourceLabel }: LeadCardProps) {
  const navigate = useNavigate()
  const channel = resolveLeadContactChannel(lead)

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    return new Date(dateString).toLocaleDateString('ru-RU', {
      month: 'short',
      day: 'numeric',
    })
  }

  const formatCurrency = (value: string | null) => {
    if (!value) return null
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(parseFloat(value))
  }

  const handleOpen = () => {
    if (onOpen) {
      onOpen(lead)
      return
    }
    navigate({ to: '/leads/$leadId', params: { leadId: lead.id.toString() } })
  }

  const handleOpenChat = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    if (onOpenChat) {
      onOpenChat(lead)
    }
  }

  const hasOverdue = lead.has_overdue_task
  const hasActive = lead.has_active_task
  const hasFollowup = lead.has_planned_followup

  return (
    <Card
      className="cursor-pointer transition-all duration-200 hover:shadow-md border border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-background"
      onClick={handleOpen}
    >
      <CardContent className="p-3 space-y-2">
        {/* Top line: Name & Value / AI Paused */}
        <div className="flex items-start justify-between gap-1.5">
          <div className="min-w-0 flex-1 flex items-center gap-1.5">
            <h4 className="font-semibold text-sm truncate text-foreground" title={lead.contact_person || 'Без имени'}>
              {lead.contact_person || 'Без имени'}
            </h4>
            {lead.ai_paused && (
              <span className="flex h-4 items-center justify-center rounded-full bg-amber-500 px-1 text-[9px] font-bold text-white shrink-0" title="AI на паузе — ручное управление">
                Ручное
              </span>
            )}
          </div>
          {lead.estimated_value && (
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 shrink-0">
              {formatCurrency(lead.estimated_value)}
            </span>
          )}
        </div>

        {/* Contact info (Phone / Check-in) */}
        {(lead.phone || lead.check_in_date) && (
          <div className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            {lead.phone && (
              <div className="flex items-center gap-1">
                <PhoneIcon className="h-3 w-3 shrink-0" />
                <span className="truncate">{lead.phone}</span>
              </div>
            )}
            {lead.check_in_date && (
              <div className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <CalendarDaysIcon className="h-3 w-3 shrink-0" />
                <span>Заезд: {formatDate(lead.check_in_date)}</span>
              </div>
            )}
          </div>
        )}

        {/* Channel & Source Badges */}
        <div className="flex flex-wrap gap-1">
          {channel === 'instagram' && (
            <button
              type="button"
              onClick={handleOpenChat}
              className="inline-flex h-5 items-center gap-1 rounded-full border border-pink-200 bg-pink-50 px-1.5 text-[9px] font-medium text-pink-700 transition hover:shadow-sm dark:border-pink-900/50 dark:bg-pink-950/20 dark:text-pink-400"
              title={`Открыть чат: ${getContactChannelLabel(channel)}`}
              aria-label={`Открыть чат: ${getContactChannelLabel(channel)}`}
            >
              <InstagramIcon className="h-3 w-3" />
              Insta
            </button>
          )}
          {channel === 'telegram' && (
            <button
              type="button"
              onClick={handleOpenChat}
              className="inline-flex h-5 items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-1.5 text-[9px] font-medium text-blue-700 transition hover:shadow-sm dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-400"
              title={`Открыть чат: ${getContactChannelLabel(channel)}`}
              aria-label={`Открыть чат: ${getContactChannelLabel(channel)}`}
            >
              <MessageSquareIcon className="h-3 w-3" />
              TG
            </button>
          )}
          {channel === 'whatsapp' && (
            <button
              type="button"
              onClick={handleOpenChat}
              className="inline-flex h-5 items-center gap-1 rounded-full border border-green-200 bg-green-50 px-1.5 text-[9px] font-medium text-green-700 transition hover:shadow-sm dark:border-green-900/50 dark:bg-green-950/20 dark:text-green-400"
              title={`Открыть чат: ${getContactChannelLabel(channel)}`}
              aria-label={`Открыть чат: ${getContactChannelLabel(channel)}`}
            >
              <PhoneIcon className="h-3 w-3" />
              WA
            </button>
          )}
          {lead.instagram_intent_tier && (
            <InstagramIntentBadge tier={lead.instagram_intent_tier} />
          )}
          {lead.discovery_source && (
            <LeadSourceBadge source={lead.discovery_source} label={discoverySourceLabel} />
          )}
        </div>

        {/* Bottom bar: Manager & State Indicators */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] text-muted-foreground">
          {/* Manager name */}
          <div className="flex items-center gap-1 min-w-0 flex-1">
            <span className="truncate" title={lead.assigned_to_name || 'Ответственный не назначен'}>
              👤 {lead.assigned_to_name || <span className="italic text-slate-400">Не назначен</span>}
            </span>
          </div>

          {/* Task indicators */}
          <div className="flex items-center gap-1 shrink-0 ml-2">
            {hasOverdue && (
              <span className="inline-flex items-center rounded bg-red-50 px-1 py-0.5 text-[9px] font-medium text-red-700 ring-1 ring-inset ring-red-600/10 dark:bg-red-400/10 dark:text-red-400 dark:ring-red-400/20" title="Есть просроченная задача">
                Просрочено
              </span>
            )}
            {hasActive && !hasOverdue && (
              <span className="inline-flex items-center rounded bg-blue-50 px-1 py-0.5 text-[9px] font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10 dark:bg-blue-400/10 dark:text-blue-400 dark:ring-blue-400/30" title="Есть активная задача">
                Задача
              </span>
            )}
            {hasFollowup && (
              <span className="inline-flex items-center rounded bg-purple-50 px-1 py-0.5 text-[9px] font-medium text-purple-700 ring-1 ring-inset ring-purple-700/10 dark:bg-purple-400/10 dark:text-purple-400 dark:ring-purple-400/30" title="Запланирован Follow-up">
                Follow-up
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
