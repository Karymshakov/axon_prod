import { useLanguage } from '@/contexts/language-context'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { TrashIcon } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { createLead, updateLead, deleteLead, fetchSegments, fetchPipelineStages, SOURCE_OPTIONS, type Lead } from '@/lib/api'
import { useQuery } from '@tanstack/react-query'
import { DatePicker } from '@/components/date-picker'

const leadSchema = z.object({
  // Contact Details
  contact_person: z.string().optional(),
  job_title: z.string().optional(),
  email: z.string().optional(),
  secondary_email: z.string().optional(),
  phone: z.string().optional(),
  mobile_phone: z.string().optional(),
  office_phone: z.string().optional(),
  website: z.string().optional(),
  linkedin_url: z.string().optional(),
  // Location
  address: z.string().optional(),
  city: z.string().optional(),
  state_province: z.string().optional(),
  postal_code: z.string().optional(),
  country: z.string().optional(),
  timezone: z.string().optional(),
  // Lead Management
  segment: z.string().min(1),
  status: z.string().min(1),
  source: z.string().optional(),
  estimated_value: z.string().optional(),
  notes: z.string().optional(),
  last_contacted: z.date().nullable().optional(),
  // Summary & Next Steps
  problem_description: z.string().optional(),
  next_steps: z.string().optional(),
  // Communication Tracking
  preferred_contact_method: z.string().optional(),
  preferred_contact_time: z.string().optional(),
  language: z.string().optional(),
  do_not_contact: z.boolean().optional(),
  email_bounced: z.boolean().optional(),
  // Sales Process
  next_follow_up_date: z.date().nullable().optional(),
  expected_close_date: z.date().nullable().optional(),
  lost_reason: z.string().optional(),
  competitor: z.string().optional(),
  referral_source: z.string().optional(),
  campaign_source: z.string().optional(),
  // Social
  telegram_chat_id: z.string().optional(),
  telegram_username: z.string().optional(),
})

type LeadFormData = z.infer<typeof leadSchema>

interface LeadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  lead: Lead | null
  defaultSegment?: string
  onClose: () => void
}

export function LeadDialog({ open, onOpenChange, lead, defaultSegment = 'individual', onClose }: LeadDialogProps) {
  const { t } = useLanguage()
  const queryClient = useQueryClient()
  const isEditing = !!lead

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
      // Contact Details
      contact_person: lead?.contact_person || '',
      job_title: lead?.job_title || '',
      email: lead?.email || '',
      secondary_email: lead?.secondary_email || '',
      phone: lead?.phone || '',
      mobile_phone: lead?.mobile_phone || '',
      office_phone: lead?.office_phone || '',
      website: lead?.website || '',
      linkedin_url: lead?.linkedin_url || '',
      // Location
      address: lead?.address || '',
      city: lead?.city || '',
      state_province: lead?.state_province || '',
      postal_code: lead?.postal_code || '',
      country: lead?.country || '',
      timezone: lead?.timezone || '',
      // Lead Management
      segment: lead?.segment || defaultSegment,
      status: lead?.status || 'new',
      source: lead?.source || '',
      estimated_value: lead?.estimated_value || '',
      notes: lead?.notes || '',
      last_contacted: lead?.last_contacted ? new Date(lead.last_contacted) : null,
      // Summary & Next Steps
      problem_description: lead?.problem_description || '',
      next_steps: lead?.next_steps || '',
      // Communication Tracking
      preferred_contact_method: lead?.preferred_contact_method || '',
      preferred_contact_time: lead?.preferred_contact_time || '',
      language: lead?.language || '',
      do_not_contact: lead?.do_not_contact || false,
      email_bounced: lead?.email_bounced || false,
      // Sales Process
      next_follow_up_date: lead?.next_follow_up_date ? new Date(lead.next_follow_up_date) : null,
      expected_close_date: lead?.expected_close_date ? new Date(lead.expected_close_date) : null,
      lost_reason: lead?.lost_reason || '',
      competitor: lead?.competitor || '',
      referral_source: lead?.referral_source || '',
      campaign_source: lead?.campaign_source || '',
      // Social
      telegram_chat_id: lead?.telegram_chat_id || '',
      telegram_username: lead?.telegram_username || '',
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
    mutationFn: ({ id, data }: { id: number; data: Partial<Lead> }) =>
      updateLead(id, data as any),
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
      last_contacted: data.last_contacted
        ? data.last_contacted.toISOString().split('T')[0]
        : null,
      next_follow_up_date: data.next_follow_up_date
        ? data.next_follow_up_date.toISOString().split('T')[0]
        : null,
      expected_close_date: data.expected_close_date
        ? data.expected_close_date.toISOString().split('T')[0]
        : null,
    }

    if (isEditing) {
      updateMutation.mutate({ id: lead.id, data: submitData as any })
    } else {
      createMutation.mutate(submitData as any)
    }
  }

  const handleDelete = () => {
    if (lead) {
      deleteMutation.mutate(lead.id)
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    onOpenChange(newOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl flex flex-col max-h-[75vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle>{isEditing ? t('leads.editLead') : t('leads.addNewLead')}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? t('leads.updateLeadInfo')
              : t('leads.addNewLeadDesc')}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col min-h-0 flex-1">
          <div className="overflow-y-auto flex-1 space-y-4 pr-1">
            {/* Core Fields */}
            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="contact_person"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('leads.contactPerson')}</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Иван Иванов" />
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
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common.phone')}</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="+7 (999) 123-45-67" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="segment"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('leads.clientType')}</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Выберите тип клиента" />
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
                            {stage.name}
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
                name="source"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('leads.source')}</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value || ''}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Выберите источник" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {SOURCE_OPTIONS.map((opt) => (
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

            {/* Summary & Next Steps */}
            <FormField
              control={form.control}
              name="problem_description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('leads.summary')}</FormLabel>
                  <FormControl>
                    <Textarea
                      {...field}
                      placeholder="Краткое описание запроса лида..."
                      rows={3}
                    />
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
                    <Textarea
                      {...field}
                      placeholder="Планируемые действия по лиду..."
                      rows={2}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Collapsible Sections */}
            <Accordion type="multiple" className="w-full">
              {/* Contact Details */}
              <AccordionItem value="contact">
                <AccordionTrigger>{t('leads.contactDetails')}</AccordionTrigger>
                <AccordionContent>
                  <div className="grid gap-4 md:grid-cols-2 pt-2">
                    <FormField
                      control={form.control}
                      name="job_title"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.jobTitle')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Директор, менеджер и т.д." />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="secondary_email"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.secondaryEmail')}</FormLabel>
                          <FormControl>
                            <Input {...field} type="email" placeholder="dop@example.com" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="mobile_phone"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.mobilePhone')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="+7 (999) 123-45-67" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="office_phone"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.officePhone')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="+7 (999) 987-65-43" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="website"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.website')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="https://example.com" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="linkedin_url"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.linkedinUrl')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="https://linkedin.com/in/..." />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Location */}
              <AccordionItem value="location">
                <AccordionTrigger>{t('leads.location')}</AccordionTrigger>
                <AccordionContent>
                  <div className="grid gap-4 md:grid-cols-2 pt-2">
                    <FormField
                      control={form.control}
                      name="address"
                      render={({ field }) => (
                        <FormItem className="md:col-span-2">
                          <FormLabel>{t('leads.address')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="ул. Ленина, д. 1" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="city"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.city')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Москва" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="state_province"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.stateProvince')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Московская область" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="postal_code"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.postalCode')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="101000" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="country"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.country')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Россия" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="timezone"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.timezone')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Europe/Moscow" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Communication Tracking */}
              <AccordionItem value="communication">
                <AccordionTrigger>{t('leads.communicationPreferences')}</AccordionTrigger>
                <AccordionContent>
                  <div className="grid gap-4 md:grid-cols-2 pt-2">
                    <FormField
                      control={form.control}
                      name="preferred_contact_method"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.preferredContactMethod')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Email, телефон, Telegram" />
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
                          <FormLabel>{t('leads.preferredContactTime')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Утро, день, вечер" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="language"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.leadLanguage')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Русский, английский и т.д." />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <div className="flex items-center space-x-4">
                      <FormField
                        control={form.control}
                        name="do_not_contact"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox
                                checked={field.value}
                                onCheckedChange={field.onChange}
                              />
                            </FormControl>
                            <FormLabel className="!mt-0">{t('leads.doNotContact')}</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="email_bounced"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox
                                checked={field.value}
                                onCheckedChange={field.onChange}
                              />
                            </FormControl>
                            <FormLabel className="!mt-0">{t('leads.emailBounced')}</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Sales Process */}
              <AccordionItem value="sales">
                <AccordionTrigger>{t('leads.salesProcess')}</AccordionTrigger>
                <AccordionContent>
                  <div className="grid gap-4 md:grid-cols-2 pt-2">
                    <FormField
                      control={form.control}
                      name="campaign_source"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.campaignSource')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Google Реклама, Email-рассылка" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="referral_source"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.referralSource')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Кто порекомендовал" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="estimated_value"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.estimatedValue')}</FormLabel>
                          <FormControl>
                            <Input {...field} type="number" placeholder="50000" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="last_contacted"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.lastContactedLabel')}</FormLabel>
                          <FormControl>
                            <DatePicker
                              value={field.value ? field.value.toISOString().split('T')[0] : undefined}
                              onChange={(dateStr) => field.onChange(dateStr ? new Date(dateStr + 'T00:00:00') : null)}
                              placeholder="Выберите дату"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="next_follow_up_date"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.nextFollowUpDate')}</FormLabel>
                          <FormControl>
                            <DatePicker
                              value={field.value ? field.value.toISOString().split('T')[0] : undefined}
                              onChange={(dateStr) => field.onChange(dateStr ? new Date(dateStr + 'T00:00:00') : null)}
                              placeholder="Выберите дату"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="expected_close_date"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.expectedCloseDate')}</FormLabel>
                          <FormControl>
                            <DatePicker
                              value={field.value ? field.value.toISOString().split('T')[0] : undefined}
                              onChange={(dateStr) => field.onChange(dateStr ? new Date(dateStr + 'T00:00:00') : null)}
                              placeholder="Выберите дату"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="lost_reason"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.lostReason')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Причина отказа" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="competitor"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.competitor')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Какого конкурента выбрали" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Social/Messaging */}
              <AccordionItem value="social">
                <AccordionTrigger>{t('leads.socialMessaging')}</AccordionTrigger>
                <AccordionContent>
                  <div className="grid gap-4 md:grid-cols-2 pt-2">
                    <FormField
                      control={form.control}
                      name="telegram_username"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.telegramUsername')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="имя_пользователя (без @)" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="telegram_chat_id"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('leads.telegramChatId')}</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="123456789" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>

            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('common.notes')}</FormLabel>
                  <FormControl>
                    <Textarea
                      {...field}
                      placeholder="Дополнительные заметки о лиде..."
                      rows={3}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

          </div>
            <DialogFooter className="gap-2 pt-4 border-t shrink-0">
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
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
              >
                {t('common.cancel')}
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {isEditing ? t('leads.updateLead') : t('leads.createLead')}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
