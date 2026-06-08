import { useQuery } from '@tanstack/react-query'
import { ActivityIcon } from 'lucide-react'
import { fetchLeadActivities, type LeadActivity } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useLanguage } from '@/contexts/language-context'

interface LeadActivityTimelineProps {
  leadId: number
}

export function LeadActivityTimeline({ leadId }: LeadActivityTimelineProps) {
  const { t } = useLanguage()
  const { data: activities = [], isLoading } = useQuery({
    queryKey: ['lead-activities', leadId],
    queryFn: () => fetchLeadActivities(leadId),
  })

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'status_change': return '🔄'
      case 'note_added': return '💬'
      case 'lead_created': return '✨'
      case 'lead_updated': return '📝'
      case 'task_created': return '📋'
      case 'task_completed': return '✅'
      case 'telegram_sent': return '📤'
      case 'telegram_received': return '📥'
      case 'instagram_sent': return '📤'
      case 'instagram_received': return '📥'
      case 'whatsapp_sent': return '📤'
      case 'whatsapp_received': return '📥'
      default: return '•'
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ActivityIcon className="h-4 w-4" />
          {t('leads.activityTimeline')}
        </CardTitle>
      </CardHeader>
      <CardContent className="max-h-[500px] overflow-y-auto">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t('leads.loadingActivity')}</p>
        ) : activities.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('leads.noActivity')}</p>
        ) : (
          <div className="space-y-4">
            {activities.map((activity: LeadActivity, index: number) => (
              <div key={activity.id} className="flex gap-3">
                {/* Timeline connector */}
                <div className="flex flex-col items-center">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-muted bg-background text-xs">
                    {getActivityIcon(activity.activity_type)}
                  </div>
                  {index < activities.length - 1 ? (
                    <div className="w-px flex-1 bg-border mt-1" />
                  ) : null}
                </div>

                {/* Activity content */}
                <div className="flex-1 pb-4 min-w-0">
                  <p className="text-sm font-medium">{activity.activity_type_display}</p>
                  <p className="text-sm text-muted-foreground">{activity.description}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatDate(activity.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
