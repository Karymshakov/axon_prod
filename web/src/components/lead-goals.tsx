import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { TargetIcon, CheckCircle2Icon, CircleIcon, SparklesIcon } from 'lucide-react'
import { fetchGoalsForLead, completeLeadGoal, initializeGoalsForLead } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { useLanguage } from '@/contexts/language-context'

interface LeadGoalsProps {
  leadId: number
}

export function LeadGoals({ leadId }: LeadGoalsProps) {
  const { t } = useLanguage()
  const queryClient = useQueryClient()

  const { data: goals = [], isLoading } = useQuery({
    queryKey: ['lead-goals', leadId],
    queryFn: () => fetchGoalsForLead(leadId),
  })

  const completeGoalMutation = useMutation({
    mutationFn: (goalId: number) => completeLeadGoal(goalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-goals', leadId] })
      toast.success(t('leads.goalCompleted'))
    },
    onError: () => {
      toast.error(t('leads.goalCompleteError'))
    },
  })

  const initializeGoalsMutation = useMutation({
    mutationFn: () => initializeGoalsForLead(leadId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['lead-goals', leadId] })
      if (data.created > 0) {
        toast.success(t('leads.goalsInitSuccess'))
      } else {
        toast.info(t('leads.noNewGoals'))
      }
    },
    onError: () => {
      toast.error(t('leads.goalInitError'))
    },
  })

  const activeGoals = goals.filter(g => g.status === 'active')
  const completedGoals = goals.filter(g => g.status === 'completed')

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 1: return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
      case 2: return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
      case 3: return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
      default: return 'bg-gray-100 text-gray-700'
    }
  }


  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <TargetIcon className="h-5 w-5" />
            {t('leads.conversationGoals')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{t('leads.loadingGoals')}</p>
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
            {t('leads.conversationGoals')}
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => initializeGoalsMutation.mutate()}
            disabled={initializeGoalsMutation.isPending}
          >
            <SparklesIcon className="h-4 w-4 mr-1" />
            {initializeGoalsMutation.isPending ? t('leads.initializingGoals') : t('leads.aiSuggest')}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {goals.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <TargetIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('leads.noGoals')}</p>
            <p className="text-xs mt-1">{t('leads.noGoalsDesc')}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Active Goals */}
            {activeGoals.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-muted-foreground">{t('leads.activeGoalsSection')}</h4>
                {activeGoals.map((goal) => (
                  <div
                    key={goal.id}
                    className="flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
                  >
                    <button
                      onClick={() => completeGoalMutation.mutate(goal.id)}
                      className="text-muted-foreground hover:text-primary transition-colors"
                      disabled={completeGoalMutation.isPending}
                      aria-label={`Mark "${goal.goal_type_display}" as complete`}
                    >
                      <CircleIcon className="h-5 w-5" />
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{goal.goal_type_display}</span>
                        <Badge variant="outline" className={`text-xs ${getPriorityColor(goal.priority)}`}>
                          {goal.priority_display}
                        </Badge>
                      </div>
                      {goal.notes && (
                        <p className="text-xs text-muted-foreground truncate mt-0.5">{goal.notes}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Completed Goals */}
            {completedGoals.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-muted-foreground">{t('leads.completedGoalsSection')}</h4>
                {completedGoals.slice(0, 3).map((goal) => (
                  <div
                    key={goal.id}
                    className="flex items-center gap-3 p-3 rounded-lg bg-muted/30"
                  >
                    <CheckCircle2Icon className="h-5 w-5 text-green-600" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-muted-foreground line-through">
                        {goal.goal_type_display}
                      </span>
                      {goal.current_value && (
                        <span className="text-xs text-muted-foreground ml-2">
                          ({goal.current_value})
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                {completedGoals.length > 3 && (
                  <p className="text-xs text-muted-foreground text-center">
                    +{completedGoals.length - 3} more completed
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
