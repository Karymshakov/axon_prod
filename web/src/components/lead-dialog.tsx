import { useLanguage } from '@/contexts/language-context'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { TrashIcon } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import {
  createLead,
  deleteLead,
  fetchPipelineStages,
  fetchSegments,
  getLeadStatusLabel,
  updateLead,
  type Lead,
} from '@/lib/api'
import { DatePicker } from '@/components/date-picker'
import { useLeadDiscoverySources } from '@/hooks/use-lead-discovery-sources'

const NONE_VALUE = '__none'

const MEAL_PLAN_OPTIONS: Array<{ value: NonNullable<Lead['meal_plan']>; label: string }> = [
  { value: 'none', label: 'Без питания' },
  { value: 'breakfast', label: 'Завтрак' },
  { value: 'lunch', label: 'Обед' },
  { value: 'dinner', label: 'Ужин' },
  { value: 'half_board_bl', label: 'Полупансион: завтрак + обед' },
  { value: 'half_board_bd', label: 'Полупансион: завтрак + ужин' },
  { value: 'full_board', label: 'Полный пансион' },
]

const leadSchema = z.object({
  contact_person: z.string().optional(),
  email: z.string().optional(),
  phone: z.string().optional(),
  segment: z.string().min(1),
  status: z.string().min(1),
  discovery_source: z.string().optional(),
  discovery_source_detail: z.string().optional(),
  check_in_date: z.date().nullable().optional(),
  check_out_date: z.date().nullable().optional(),
  guest_count: z.number().nullable().optional(),
  room_type_preference: z.string().optional(),
  meal_plan: z.string().optional(),
  problem_description: z.string().optional(),
  next_steps: z.string().optional(),
  preferred_contact_time: z.string().optional(),
  notes: z.string().optional(),
})

type LeadFormData = z.infer<typeof leadSchema>

interface LeadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  lead: Lead | null
  defaultSegment?: string
  onClose: () => void
}

function toApiDate(value?: Date | null) {
  return value ? value.toISOString().split('T')[0] : null
}

export function LeadDialog({ open, onOpenChange, lead, defaultSegment = 'individual', onClose }: LeadDialogProps) {
  const { t } = useLanguage()
  const queryClient = useQueryClient()
  const isEditing = !!lead
  const discoverySourceOptions = useLeadDiscoverySources()

  const { data: segments = [] } = useQuery({
    queryKey: ['segments'],
    queryFn: fetchSegments,
  })

  const { data: pipelineStages = [] } = useQuery({
    queryKey: ['pipeline-stages'],
    queryFn: fetchPipelineStages,
  })

  const form = useForm<LeadFormData>({
    resolver: zodResolver(leadSchema),
    values: {
      contact_person: lead?.contact_person || '',
      email: lead?.email || '',
      phone: lead?.phone || '',
      segment: lead?.segment || defaultSegment,
      status: lead?.status || 'new',
      discovery_source: lead?.discovery_source || '',
      discovery_source_detail: lead?.discovery_source_detail || '',
      check_in_date: lead?.check_in_date ? new Date(`${lead.check_in_date}T00:00:00`) : null,
      check_out_date: lead?.check_out_date ? new Date(`${lead.check_out_date}T00:00:00`) : null,
      guest_count: lead?.guest_count ?? null,
      room_type_preference: lead?.room_type_preference || '',
      meal_plan: lead?.meal_plan || '',
      problem_description: lead?.problem_description || '',
      next_steps: lead?.next_steps || '',
      preferred_contact_time: lead?.preferred_contact_time || '',
      notes: lead?.notes || '',
    },
  })

  const createMutation = useMutation({
    mutationFn: createLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      queryClient.invalidateQueries({ queryKey: ['lead-source-stats'] })
      toast.success(t('leads.leadCreated'))
      onClose()
    },
    onError: () => {
      toast.error(t('leads.createLeadError'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Lead> }) => updateLead(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      queryClient.invalidateQueries({ queryKey: ['lead-source-stats'] })
      toast.success(t('leads.leadUpdated'))
      onClose()
    },
    onError: () => {
      toast.error(t('leads.updateLeadError'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      toast.success(t('leads.leadDeleted'))
      onClose()
    },
    onError: () => {
      toast.error(t('leads.deleteLeadError'))
    },
  })

  const onSubmit = (data: LeadFormData) => {
    const submitData = {
      ...data,
      discovery_source: data.discovery_source || '',
      discovery_source_detail: data.discovery_source_detail || '',
      check_in_date: toApiDate(data.check_in_date),
      check_out_date: toApiDate(data.check_out_date),
      guest_count: data.guest_count ?? null,
      meal_plan: data.meal_plan || '',
    }

    if (isEditing) {
      updateMutation.mutate({ id: lead.id, data: submitData as Partial<Lead> })
    } else {
      createMutation.mutate(submitData as any)
    }
  }

  const handleDelete = () => {
    if (lead) {
      deleteMutation.mutate(lead.id)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex h-full w-full flex-col overflow-hidden p-6 sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>{isEditing ? t('leads.editLead') : t('leads.addNewLead')}</SheetTitle>
          <SheetDescription>
            {isEditing ? t('leads.updateLeadInfo') : t('leads.addNewLeadDesc')}
          </SheetDescription>
        </SheetHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
            <div className="min-h-0 flex-1 space-y-6 overflow-y-auto pr-1">
              <section className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="contact_person"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Имя гостя</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Иван Иванов" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('common.phone')}</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="+7 999 123 45 67" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('common.email')}</FormLabel>
                        <FormControl>
                          <Input {...field} type="email" placeholder="ivan@example.com" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="preferred_contact_time"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Удобное время связи</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Сегодня после 18:00" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </section>

              <section className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="status"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('common.status')}</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Выберите статус" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {pipelineStages.map((stage) => (
                              <SelectItem key={stage.key} value={stage.key}>
                                {getLeadStatusLabel(stage.key, pipelineStages)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="segment"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Тип клиента</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Выберите тип" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {segments.map((seg) => (
                              <SelectItem key={seg.key} value={seg.key}>
                                {seg.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="discovery_source"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Откуда узнал</FormLabel>
                        <Select
                          onValueChange={(value) => field.onChange(value === NONE_VALUE ? '' : value)}
                          value={field.value || NONE_VALUE}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Не указано" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value={NONE_VALUE}>Не указано</SelectItem>
                            {discoverySourceOptions.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="discovery_source_detail"
                    render={({ field }) => (
                      <FormItem className="md:col-span-2">
                        <FormLabel>Детали источника</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Например: порекомендовала Анна, видел сторис, реклама в Instagram" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </section>

              <section className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="check_in_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Заезд</FormLabel>
                        <FormControl>
                          <DatePicker
                            value={field.value ? field.value.toISOString().split('T')[0] : undefined}
                            onChange={(dateStr) => field.onChange(dateStr ? new Date(`${dateStr}T00:00:00`) : null)}
                            placeholder="Выберите дату"
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="check_out_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Выезд</FormLabel>
                        <FormControl>
                          <DatePicker
                            value={field.value ? field.value.toISOString().split('T')[0] : undefined}
                            onChange={(dateStr) => field.onChange(dateStr ? new Date(`${dateStr}T00:00:00`) : null)}
                            placeholder="Выберите дату"
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="guest_count"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Гостей</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={1}
                            value={field.value ?? ''}
                            onChange={(event) => field.onChange(event.target.value === '' ? null : Number(event.target.value))}
                            placeholder="2"
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="room_type_preference"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Номер</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Стандарт, семейный, люкс" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="meal_plan"
                    render={({ field }) => (
                      <FormItem className="md:col-span-2">
                        <FormLabel>Питание</FormLabel>
                        <Select
                          onValueChange={(value) => field.onChange(value === NONE_VALUE ? '' : value)}
                          value={field.value || NONE_VALUE}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Не указано" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value={NONE_VALUE}>Не указано</SelectItem>
                            {MEAL_PLAN_OPTIONS.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </section>

              <section className="space-y-4">
                <FormField
                  control={form.control}
                  name="problem_description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('leads.summary')}</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Что хочет гость, какие даты и пожелания уже известны" rows={3} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="next_steps"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('leads.nextSteps')}</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Что нужно сделать дальше: уточнить даты, отправить цену, подтвердить оплату" rows={2} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('common.notes')}</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Внутренние заметки для команды" rows={3} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </section>
            </div>

            <SheetFooter className="shrink-0 gap-2 border-t pt-4">
              {isEditing ? (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                  className="mr-auto"
                >
                  <TrashIcon className="h-4 w-4" />
                  {t('common.delete')}
                </Button>
              ) : null}
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {isEditing ? t('leads.updateLead') : t('leads.createLead')}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  )
}
