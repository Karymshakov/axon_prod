import { useState } from 'react'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircleIcon, PlusIcon, TrashIcon, CalendarIcon, AlertCircleIcon } from 'lucide-react'
import { fetchTasks, createTask, completeTask, deleteTask, type Task } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DatePicker } from '@/components/date-picker'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'

interface LeadTasksProps {
  leadId: number
}

export function LeadTasks({ leadId }: LeadTasksProps) {
  const { t } = useLanguage()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [taskType, setTaskType] = useState<'call' | 'email' | 'meeting' | 'follow_up' | 'other'>('follow_up')
  const [dueDate, setDueDate] = useState<Date | null>(null)
  const queryClient = useQueryClient()

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['tasks', leadId],
    queryFn: () => fetchTasks(leadId),
  })

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', leadId] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', leadId] })
      setDialogOpen(false)
      resetForm()
      toast.success(t('leads.taskCreated'))
    },
    onError: () => {
      toast.error(t('leads.taskCreateError'))
    },
  })

  const completeMutation = useMutation({
    mutationFn: completeTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', leadId] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', leadId] })
      toast.success(t('leads.taskCompleted'))
    },
    onError: () => {
      toast.error(t('leads.taskCompleteError'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', leadId] })
      toast.success(t('leads.taskDeleted'))
    },
    onError: () => {
      toast.error(t('leads.taskDeleteError'))
    },
  })

  const resetForm = () => {
    setTitle('')
    setDescription('')
    setTaskType('follow_up')
    setDueDate(null)
  }

  const handleCreateTask = () => {
    if (!title.trim()) {
      toast.error(t('leads.enterTaskTitle'))
      return
    }
    if (!dueDate) {
      toast.error(t('leads.selectDueDate'))
      return
    }

    createMutation.mutate({
      lead: leadId,
      title,
      description,
      task_type: taskType,
      due_date: dueDate.toISOString().split('T')[0],
    })
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  }

  const pendingTasks = tasks.filter((t: Task) => t.status === 'pending')
  const completedTasks = tasks.filter((t: Task) => t.status === 'completed')

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarIcon className="h-4 w-4" />
              {t('leads.tasksAndReminders')}
            </CardTitle>
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <PlusIcon className="h-4 w-4 mr-1" />
              {t('leads.addTask')}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{t('leads.loadingTasks')}</p>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('leads.noTasks')}</p>
          ) : (
            <>
              {/* Pending tasks */}
              {pendingTasks.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">{t('leads.pending')} ({pendingTasks.length})</h4>
                  <div className="space-y-2">
                    {pendingTasks.map((task: Task) => (
                      <div
                        key={task.id}
                        className={`rounded-lg border p-3 ${task.is_overdue ? 'border-destructive bg-destructive/5' : ''}`}
                      >
                        <div className="flex items-start gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0 mt-0.5"
                            onClick={() => completeMutation.mutate(task.id)}
                            disabled={completeMutation.isPending}
                            aria-label="Complete task"
                          >
                            <CheckCircleIcon className="h-4 w-4" />
                          </Button>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-medium">{task.title}</p>
                              <Badge variant="outline" className="text-xs">
                                {task.task_type_display}
                              </Badge>
                              {task.is_overdue ? (
                                <Badge variant="destructive" className="text-xs">
                                  <AlertCircleIcon className="h-3 w-3 mr-1" />
                                  {t('leads.overdue')}
                                </Badge>
                              ) : null}
                            </div>
                            {task.description ? (
                              <p className="text-sm text-muted-foreground mt-1">
                                {task.description}
                              </p>
                            ) : null}
                            <p className="text-xs text-muted-foreground mt-1">
                              {t('leads.due')} {formatDate(task.due_date)}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0"
                            onClick={() => deleteMutation.mutate(task.id)}
                            disabled={deleteMutation.isPending}
                            aria-label="Delete task"
                          >
                            <TrashIcon className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Completed tasks */}
              {completedTasks.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">
                    {t('leads.completedGoalsSection')} ({completedTasks.length})
                  </h4>
                  <div className="space-y-2">
                    {completedTasks.map((task: Task) => (
                      <div key={task.id} className="rounded-lg border p-3 opacity-60">
                        <div className="flex items-start gap-2">
                          <CheckCircleIcon className="h-5 w-5 shrink-0 text-green-600 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium line-through">{task.title}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {t('leads.completedOn')} {formatDate(task.completed_at!)}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0"
                            onClick={() => deleteMutation.mutate(task.id)}
                            disabled={deleteMutation.isPending}
                            aria-label="Delete task"
                          >
                            <TrashIcon className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      {/* Add Task Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('leads.addNewTask')}</DialogTitle>
            <DialogDescription>
              {t('leads.taskDialogDesc')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="task-title" className="text-sm font-medium">
                {t('leads.taskTitle')}
              </label>
              <Input
                id="task-title"
                placeholder={t('leads.taskTitlePlaceholder')}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="task-type" className="text-sm font-medium">
                {t('leads.taskType')}
              </label>
              <Select value={taskType} onValueChange={(v) => setTaskType(v as typeof taskType)}>
                <SelectTrigger id="task-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="call">{t('leads.taskTypeCall')}</SelectItem>
                  <SelectItem value="email">{t('leads.taskTypeEmail')}</SelectItem>
                  <SelectItem value="meeting">{t('leads.taskTypeMeeting')}</SelectItem>
                  <SelectItem value="follow_up">{t('leads.taskTypeFollowUp')}</SelectItem>
                  <SelectItem value="other">{t('leads.taskTypeOther')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label htmlFor="due-date" className="text-sm font-medium">
                {t('leads.dueDateLabel')}
              </label>
              <DatePicker
                value={dueDate ? dueDate.toISOString().split('T')[0] : undefined}
                onChange={(dateStr) => setDueDate(dateStr ? new Date(dateStr + 'T00:00:00') : null)}
                placeholder={t('leads.selectDate')}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="task-description" className="text-sm font-medium">
                {t('leads.taskDescLabel')}
              </label>
              <Textarea
                id="task-description"
                placeholder={t('leads.taskDescPlaceholder')}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDialogOpen(false)
                resetForm()
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleCreateTask}
              disabled={createMutation.isPending}
            >
              {t('leads.createTask')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
