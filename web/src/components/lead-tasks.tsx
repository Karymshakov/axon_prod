import { useState } from 'react'
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

const TASK_TYPE_LABELS: Record<string, string> = {
  call: 'Звонок',
  email: 'Email',
  meeting: 'Встреча',
  follow_up: 'Следующий контакт',
  send_info: 'Отправить информацию',
  send_case_study: 'Отправить пример',
  request_meeting: 'Запросить встречу',
  send_proposal: 'Отправить предложение',
  other: 'Другое',
}

export function LeadTasks({ leadId }: LeadTasksProps) {
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
      toast.success('Задача добавлена')
    },
    onError: () => {
      toast.error('Не удалось добавить задачу')
    },
  })

  const completeMutation = useMutation({
    mutationFn: completeTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', leadId] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', leadId] })
      toast.success('Задача выполнена')
    },
    onError: () => {
      toast.error('Не удалось выполнить задачу')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', leadId] })
      toast.success('Задача удалена')
    },
    onError: () => {
      toast.error('Не удалось удалить задачу')
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
      toast.error('Введите название задачи')
      return
    }
    if (!dueDate) {
      toast.error('Выберите дату')
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
              Задачи менеджера
            </CardTitle>
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <PlusIcon className="h-4 w-4 mr-1" />
              Добавить задачу
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Загружаем задачи...</p>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">Задач пока нет.</p>
          ) : (
            <>
              {/* Pending tasks */}
              {pendingTasks.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Активные ({pendingTasks.length})</h4>
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
                            aria-label="Выполнить задачу"
                          >
                            <CheckCircleIcon className="h-4 w-4" />
                          </Button>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-medium">{task.title}</p>
                              <Badge variant="outline" className="text-xs">
                                {TASK_TYPE_LABELS[task.task_type] ?? task.task_type_display}
                              </Badge>
                              {task.is_overdue ? (
                                <Badge variant="destructive" className="text-xs">
                                  <AlertCircleIcon className="h-3 w-3 mr-1" />
                                  Просрочена
                                </Badge>
                              ) : null}
                            </div>
                            {task.description ? (
                              <p className="text-sm text-muted-foreground mt-1">
                                {task.description}
                              </p>
                            ) : null}
                            <p className="text-xs text-muted-foreground mt-1">
                              Срок: {formatDate(task.due_date)}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0"
                            onClick={() => deleteMutation.mutate(task.id)}
                            disabled={deleteMutation.isPending}
                            aria-label="Удалить задачу"
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
                    Выполненные ({completedTasks.length})
                  </h4>
                  <div className="space-y-2">
                    {completedTasks.map((task: Task) => (
                      <div key={task.id} className="rounded-lg border p-3 opacity-60">
                        <div className="flex items-start gap-2">
                          <CheckCircleIcon className="h-5 w-5 shrink-0 text-green-600 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium line-through">{task.title}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              Выполнена: {formatDate(task.completed_at!)}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0"
                            onClick={() => deleteMutation.mutate(task.id)}
                            disabled={deleteMutation.isPending}
                            aria-label="Удалить задачу"
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
            <DialogTitle>Новая задача</DialogTitle>
            <DialogDescription>
              Задача появится в карточке лида и поможет не потерять следующий шаг.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="task-title" className="text-sm font-medium">
                Название
              </label>
              <Input
                id="task-title"
                placeholder="Например: уточнить даты и количество гостей"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="task-type" className="text-sm font-medium">
                Тип задачи
              </label>
              <Select value={taskType} onValueChange={(v) => setTaskType(v as typeof taskType)}>
                <SelectTrigger id="task-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="call">Звонок</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="meeting">Встреча</SelectItem>
                  <SelectItem value="follow_up">Следующий контакт</SelectItem>
                  <SelectItem value="other">Другое</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label htmlFor="due-date" className="text-sm font-medium">
                Срок
              </label>
              <DatePicker
                value={dueDate ? dueDate.toISOString().split('T')[0] : undefined}
                onChange={(dateStr) => setDueDate(dateStr ? new Date(dateStr + 'T00:00:00') : null)}
                placeholder="Выберите дату"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="task-description" className="text-sm font-medium">
                Описание
              </label>
              <Textarea
                id="task-description"
                placeholder="Что именно нужно сделать менеджеру"
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
              Отмена
            </Button>
            <Button
              onClick={handleCreateTask}
              disabled={createMutation.isPending}
            >
              Создать задачу
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
