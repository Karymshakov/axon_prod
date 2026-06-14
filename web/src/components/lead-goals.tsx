import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { TargetIcon, CheckCircle2Icon, CircleIcon, SparklesIcon } from 'lucide-react'
import { fetchGoalsForLead, completeLeadGoal, initializeGoalsForLead } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'

interface LeadGoalsProps {
  leadId: number
}

const GOAL_LABELS: Record<string, string> = {
  collect_email: 'Получить email, если удобно',
  collect_phone: 'Получить телефон',
  collect_guest_name: 'Уточнить имя гостя',
  collect_discovery_source: 'Уточнить, откуда узнал',
  schedule_call: 'Согласовать следующий контакт',
  schedule_meeting: 'Согласовать встречу',
  send_proposal: 'Подготовить предложение',
  send_info: 'Отправить информацию',
  handle_objection: 'Ответить на сомнение гостя',
  close_deal: 'Подтвердить бронь',
  qualify_lead: 'Уточнить детали брони',
  get_decision_maker: 'Уточнить ответственного',
}

const PRIORITY_LABELS: Record<number, string> = {
  1: 'Низкий',
  2: 'Средний',
  3: 'Высокий',
}

export function LeadGoals({ leadId }: LeadGoalsProps) {
  const queryClient = useQueryClient()

  const { data: goals = [], isLoading } = useQuery({
    queryKey: ['lead-goals', leadId],
    queryFn: () => fetchGoalsForLead(leadId),
  })

  const completeGoalMutation = useMutation({
    mutationFn: (goalId: number) => completeLeadGoal(goalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-goals', leadId] })
      queryClient.invalidateQueries({ queryKey: ['lead', leadId] })
      toast.success('Цель выполнена')
    },
    onError: () => {
      toast.error('Не удалось выполнить цель')
    },
  })

  const initializeGoalsMutation = useMutation({
    mutationFn: () => initializeGoalsForLead(leadId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['lead-goals', leadId] })
      if (data.created > 0) {
        toast.success('Цели добавлены')
      } else {
        toast.info('Новых целей нет')
      }
    },
    onError: () => {
      toast.error('Не удалось предложить цели')
    },
  })

  const activeGoals = goals.filter(g => g.status === 'active')
  const completedGoals = goals.filter(g => g.status === 'completed')

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 3: return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
      case 2: return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
      case 1: return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  const getGoalLabel = (goal: { goal_type: string; goal_type_display?: string }) =>
    GOAL_LABELS[goal.goal_type] ?? goal.goal_type_display ?? goal.goal_type


  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <TargetIcon className="h-5 w-5" />
            Цели диалога
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Загружаем цели...</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <TargetIcon className="h-5 w-5" />
            Цели диалога
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => initializeGoalsMutation.mutate()}
            disabled={initializeGoalsMutation.isPending}
          >
            <SparklesIcon className="h-4 w-4 mr-1" />
            {initializeGoalsMutation.isPending ? 'Подбираем...' : 'Предложить цели'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {goals.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <TargetIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Целей пока нет</p>
            <p className="text-xs mt-1">Можно добавить AI-подсказки по следующему шагу разговора.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Active Goals */}
            {activeGoals.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-muted-foreground">Активные</h4>
                {activeGoals.map((goal) => (
                  <div
                    key={goal.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      if (!completeGoalMutation.isPending) completeGoalMutation.mutate(goal.id)
                    }}
                    onKeyDown={(event) => {
                      if ((event.key === 'Enter' || event.key === ' ') && !completeGoalMutation.isPending) {
                        event.preventDefault()
                        completeGoalMutation.mutate(goal.id)
                      }
                    }}
                    className="flex cursor-pointer items-center gap-3 rounded-lg border bg-card p-3 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    title="Нажмите, когда цель выполнена"
                  >
                    <CircleIcon className="h-5 w-5 shrink-0 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{getGoalLabel(goal)}</span>
                        <Badge variant="outline" className={`text-xs ${getPriorityColor(goal.priority)}`}>
                          {PRIORITY_LABELS[goal.priority] ?? goal.priority_display}
                        </Badge>
                      </div>
                      {(goal.description || goal.target_value) && (
                        <p className="text-xs text-muted-foreground truncate mt-0.5">{goal.description || goal.target_value}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Completed Goals */}
            {completedGoals.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-muted-foreground">Выполненные</h4>
                {completedGoals.slice(0, 3).map((goal) => (
                  <div
                    key={goal.id}
                    className="flex items-center gap-3 p-3 rounded-lg bg-muted/30"
                  >
                    <CheckCircle2Icon className="h-5 w-5 text-green-600" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-muted-foreground line-through">
                        {getGoalLabel(goal)}
                      </span>
                      {goal.achieved_value && (
                        <span className="text-xs text-muted-foreground ml-2">
                          ({goal.achieved_value})
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                {completedGoals.length > 3 && (
                  <p className="text-xs text-muted-foreground text-center">
                    +{completedGoals.length - 3} выполнено
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
