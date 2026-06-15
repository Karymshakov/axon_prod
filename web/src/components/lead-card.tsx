import { MailIcon, PhoneIcon, FileTextIcon, DollarSignIcon, CalendarDaysIcon, HandIcon, InstagramIcon, MessageSquareIcon } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import type { MouseEvent } from 'react'
import { getContactChannelLabel, resolveLeadContactChannel, type Lead } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

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

export function LeadCard({ lead, onOpen, onOpenChat }: LeadCardProps) {
  const navigate = useNavigate()
  const channel = resolveLeadContactChannel(lead)

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    return new Date(dateString).toLocaleDateString('ru-RU', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
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

  return (
    <Card className="cursor-pointer transition-shadow hover:shadow-md" onClick={handleOpen}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <h4 className="font-semibold truncate">{lead.contact_person || 'Без имени'}</h4>
              {lead.ai_paused ? (
                <span className="flex h-5 items-center gap-0.5 rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white shrink-0" title="ИИ приостановлен — ручное управление">
                  <HandIcon className="h-3 w-3" />
                </span>
              ) : null}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={(e) => {
              e.stopPropagation()
              navigate({ to: '/leads/$leadId', params: { leadId: lead.id.toString() } })
            }}
            aria-label="Открыть карточку лида"
            title="Открыть карточку"
          >
            <FileTextIcon className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-wrap gap-1 mt-2">
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
          {lead.instagram_intent_tier ? (
            <InstagramIntentBadge tier={lead.instagram_intent_tier} />
          ) : null}
        </div>

        <div className="mt-3 space-y-1.5">
          {lead.email ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <MailIcon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{lead.email}</span>
            </div>
          ) : null}
          {lead.phone ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <PhoneIcon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{lead.phone}</span>
            </div>
          ) : null}
          {lead.estimated_value ? (
            <div className="flex items-center gap-2 text-sm font-medium text-green-600">
              <DollarSignIcon className="h-3.5 w-3.5 shrink-0" />
              <span>{formatCurrency(lead.estimated_value)}</span>
            </div>
          ) : null}
        </div>

        {lead.check_in_date ? (
          <div className="flex items-center gap-2 text-sm text-blue-600">
            <CalendarDaysIcon className="h-3.5 w-3.5 shrink-0" />
            <span>Заезд: {formatDate(lead.check_in_date)}</span>
          </div>
        ) : null}

        {lead.last_contacted ? (
          <div className="mt-3 pt-3 border-t text-xs text-muted-foreground">
            Последний контакт: {formatDate(lead.last_contacted)}
          </div>
        ) : null}

      </CardContent>
    </Card>
  )
}
