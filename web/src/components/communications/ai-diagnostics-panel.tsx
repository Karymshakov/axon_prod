import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import type { LeadActivity } from '@/lib/api'

type DiagnosticStep = {
  code?: string
  label?: string
  detail?: string
  status?: 'info' | 'success' | 'warning' | 'error'
  at?: string
}

type ActivityDiagnostics = {
  message_excerpt?: string
  final_result?: 'processing' | 'replied' | 'skipped' | 'delayed' | 'failed'
  final_summary?: string
  steps?: DiagnosticStep[]
}

type Props = {
  activities: LeadActivity[]
  channelLabel: string
}

const outcomeStyles: Record<string, string> = {
  processing: 'bg-slate-500 text-white hover:bg-slate-500',
  replied: 'bg-emerald-600 text-white hover:bg-emerald-600',
  skipped: 'bg-amber-500 text-white hover:bg-amber-500',
  delayed: 'bg-blue-600 text-white hover:bg-blue-600',
  failed: 'bg-rose-600 text-white hover:bg-rose-600',
}

const stepDotStyles: Record<string, string> = {
  info: 'bg-slate-400',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  error: 'bg-rose-500',
}

function formatTime(value?: string) {
  if (!value) return '—'
  return new Date(value).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function outcomeLabel(value?: string) {
  switch (value) {
    case 'replied':
      return 'Ответ отправлен'
    case 'skipped':
      return 'Пропущено'
    case 'delayed':
      return 'Отложено'
    case 'failed':
      return 'Ошибка'
    default:
      return 'Обработка'
  }
}

export function AiDiagnosticsPanel({ activities, channelLabel }: Props) {
  const inboundWithDiagnostics = activities
    .filter((activity) => activity.activity_type.endsWith('_received') && activity.metadata?.ai_diagnostics)
    .slice()
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  if (inboundWithDiagnostics.length === 0) {
    return (
      <div className="border-b bg-slate-50/70 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-medium">AI-диагностика</p>
            <p className="text-xs text-muted-foreground">
              Новые входящие сообщения {channelLabel} будут показывать здесь текстовый след обработки AI.
            </p>
          </div>
          <Badge variant="outline">Ожидание входящего сообщения</Badge>
        </div>
      </div>
    )
  }

  return (
    <div className="border-b bg-slate-50/70 px-4 py-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">AI-диагностика</p>
          <p className="text-xs text-muted-foreground">
            История обработки для последних входящих сообщений {channelLabel}.
          </p>
        </div>
        <Badge variant="outline">Последние {inboundWithDiagnostics.length} входящих</Badge>
      </div>

      <Accordion type="single" collapsible className="space-y-2">
        {inboundWithDiagnostics.map((activity) => {
          const diagnostics = activity.metadata?.ai_diagnostics as ActivityDiagnostics
          const result = diagnostics?.final_result || 'processing'
          const steps = diagnostics?.steps || []
          const excerpt = diagnostics?.message_excerpt || 'Inbound message'

          return (
            <AccordionItem key={activity.id} value={`diag-${activity.id}`} className="overflow-hidden rounded-lg border bg-white px-3">
              <AccordionTrigger className="py-3 text-left hover:no-underline">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={outcomeStyles[result] || outcomeStyles.processing}>
                      {outcomeLabel(result)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{formatDateTime(activity.created_at)}</span>
                  </div>
                  <p className="line-clamp-2 break-words text-sm font-medium">“{excerpt}”</p>
                  {diagnostics?.final_summary ? (
                    <p className="line-clamp-2 break-words pr-6 text-xs text-muted-foreground">{diagnostics.final_summary}</p>
                  ) : null}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-3">
                <div className="max-h-56 space-y-3 overflow-y-auto rounded-md border bg-slate-50 p-3">
                  {steps.map((step, index) => (
                    <div key={`${activity.id}-${index}`} className="flex items-start gap-3">
                      <div className="flex flex-col items-center gap-1 pt-1">
                        <span className={`h-2.5 w-2.5 rounded-full ${stepDotStyles[step.status || 'info'] || stepDotStyles.info}`} />
                        {index < steps.length - 1 ? <span className="min-h-5 w-px bg-border" /> : null}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-muted-foreground">{formatTime(step.at)}</p>
                        <p className="text-sm font-medium">{step.label || 'Шаг записан'}</p>
                        {step.detail ? <p className="text-sm text-muted-foreground break-words">{step.detail}</p> : null}
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          )
        })}
      </Accordion>
    </div>
  )
}
