import { AlertTriangleIcon, CalendarDaysIcon, CheckSquareIcon, FileTextIcon, HandIcon, InstagramIcon, MessageSquareIcon, PhoneIcon } from 'lucide-react'
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
}

export function LeadCard({ lead, onOpen, onOpenChat }: LeadCardProps) {
  const navigate = useNavigate()
  const channel = resolveLeadContactChannel(lead)
  const contactPhone = lead.phone || lead.mobile_phone || lead.whatsapp_phone
  const activeTasksCount = lead.active_tasks_count || 0
  const overdueTasksCount = lead.overdue_tasks_count || 0

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    return new Date(dateString).toLocaleDateString('ru-RU', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
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

  const stateBadges = [
    overdueTasksCount > 0 ? {
      key: 'overdue',
      title: `Просроченные задачи: ${overdueTasksCount}`,
      className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300',
      icon: <AlertTriangleIcon className="h-3 w-3" />,
      label: overdueTasksCount,
    } : null,
    activeTasksCount > 0 ? {
      key: 'tasks',
      title: `Активные задачи: ${activeTasksCount}`,
      className: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300',
      icon: <CheckSquareIcon className="h-3 w-3" />,
      label: activeTasksCount,
    } : null,
  ].filter(Boolean)
  const stateMarkerClass = overdueTasksCount > 0
    ? 'bg-red-500'
    : activeTasksCount > 0
      ? 'bg-amber-500'
      : 'bg-border'

  return (
    <Card className="group relative h-[132px] cursor-pointer overflow-hidden rounded-md border bg-card shadow-sm transition-[border-color,box-shadow,transform] duration-150 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md" onClick={handleOpen}>
      <span className={`absolute inset-y-0 left-0 w-1 ${stateMarkerClass}`} />
      <CardContent className="flex h-full flex-col p-2 pl-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <h4 className="truncate text-[13px] font-semibold leading-5">{lead.contact_person || 'Без имени'}</h4>
              {lead.ai_paused ? (
                <span className="flex h-4 items-center gap-0.5 rounded-full bg-amber-500 px-1 text-[9px] font-semibold text-white shrink-0" title="ИИ приостановлен — ручное управление">
                  <HandIcon className="h-3 w-3" />
                </span>
              ) : null}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0 text-muted-foreground opacity-70 transition group-hover:opacity-100 hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation()
              navigate({ to: '/leads/$leadId', params: { leadId: lead.id.toString() } })
            }}
            aria-label="Открыть карточку лида"
            title="Открыть карточку"
          >
            <FileTextIcon className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="mt-1.5 flex flex-wrap gap-1">
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

        {stateBadges.length > 0 ? (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {stateBadges.map((badge) => badge && (
              <span
                key={badge.key}
                title={badge.title}
                className={`inline-flex h-[18px] items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold leading-none ${badge.className}`}
              >
                {badge.icon}
                {badge.label}
              </span>
            ))}
          </div>
        ) : null}

        <div className="mt-auto grid gap-1 pt-1.5 text-xs text-muted-foreground">
          {contactPhone ? (
            <div className="flex min-w-0 items-center gap-1.5">
              <PhoneIcon className="h-3 w-3 shrink-0" />
              <span className="truncate">{contactPhone}</span>
            </div>
          ) : null}
          {lead.check_in_date ? (
            <div className="flex min-w-0 items-center gap-1.5 text-blue-600 dark:text-blue-400">
              <CalendarDaysIcon className="h-3 w-3 shrink-0" />
              <span className="truncate">Заезд: {formatDate(lead.check_in_date)}</span>
            </div>
          ) : null}
        </div>

      </CardContent>
    </Card>
  )
}
