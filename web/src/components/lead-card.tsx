import { MailIcon, PhoneIcon, EyeIcon, DollarSignIcon, CalendarDaysIcon, HandIcon } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import { type Lead } from '@/lib/api'
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
}

export function LeadCard({ lead }: LeadCardProps) {
  const navigate = useNavigate()

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

  return (
    <Card className="cursor-pointer transition-shadow hover:shadow-md" onClick={() => navigate({ to: '/leads/$leadId', params: { leadId: lead.id.toString() } })}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <h4 className="font-semibold truncate">{lead.contact_person || 'Без имени'}</h4>
              {lead.ai_paused ? (
                <span className="flex h-5 items-center gap-0.5 rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white shrink-0" title="AI приостановлен — ручное управление">
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
          >
            <EyeIcon className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-wrap gap-1 mt-2">
          {lead.instagram_user_id && (
            <Badge variant="outline" className="text-[9px] px-1 h-4 bg-pink-50 text-pink-700 border-pink-200 dark:bg-pink-950/20 dark:text-pink-400 dark:border-pink-900/50 gap-0.5">
              Insta
            </Badge>
          )}
          {lead.telegram_chat_id && (
            <Badge variant="outline" className="text-[9px] px-1 h-4 bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/20 dark:text-blue-400 dark:border-blue-900/50 gap-0.5">
              TG
            </Badge>
          )}
          {lead.whatsapp_phone && (
            <Badge variant="outline" className="text-[9px] px-1 h-4 bg-green-50 text-green-700 border-green-200 dark:bg-green-950/20 dark:text-green-400 dark:border-green-900/50 gap-0.5">
              WA
            </Badge>
          )}
          {lead.instagram_intent_tier ? (
            <InstagramIntentBadge tier={lead.instagram_intent_tier} />
          ) : null}
          {lead.source ? (
            <LeadSourceBadge source={lead.source} />
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
