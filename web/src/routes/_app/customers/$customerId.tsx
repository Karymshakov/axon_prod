import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeftIcon, MailIcon, PhoneIcon, SendIcon, MessageCircleIcon } from 'lucide-react'
import { useState } from 'react'
import { useLanguage } from '@/contexts/language-context'
import { fetchCustomer, fetchLeadActivities, sendTelegramToCustomer, sendInstagramToCustomer, sendWhatsAppToCustomer, type LeadActivity } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'

export const Route = createFileRoute('/_app/customers/$customerId')({
  component: CustomerDetailPage,
})

function CustomerDetailPage() {
  const { t } = useLanguage()
  const { customerId } = Route.useParams()
  const customerIdNum = parseInt(customerId, 10)
  const [telegramDialogOpen, setTelegramDialogOpen] = useState(false)
  const [telegramMessage, setTelegramMessage] = useState('')
  const [instagramDialogOpen, setInstagramDialogOpen] = useState(false)
  const [instagramMessage, setInstagramMessage] = useState('')
  const [whatsappDialogOpen, setWhatsappDialogOpen] = useState(false)
  const [whatsappMessage, setWhatsappMessage] = useState('')
  const queryClient = useQueryClient()

  const { data: customer, isLoading } = useQuery({
    queryKey: ['customer', customerIdNum],
    queryFn: () => fetchCustomer(customerIdNum),
  })

  // Fetch activities from linked lead
  const { data: activities = [] } = useQuery({
    queryKey: ['lead-activities', customer?.lead_id],
    queryFn: () => fetchLeadActivities(customer!.lead_id!),
    enabled: !!customer?.lead_id,
  })

  const sendTelegramMutation = useMutation({
    mutationFn: (message: string) => sendTelegramToCustomer(customerIdNum, message),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-activities', customer?.lead_id] })
      setTelegramDialogOpen(false)
      setTelegramMessage('')
      toast.success(t('customers.sendTelegramSuccess'))
    },
    onError: (error: any) => {
      toast.error(error?.data?.error || t('customers.sendTelegramError'))
    },
  })

  const sendInstagramMutation = useMutation({
    mutationFn: (message: string) => sendInstagramToCustomer(customerIdNum, message),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-activities', customer?.lead_id] })
      setInstagramDialogOpen(false)
      setInstagramMessage('')
      toast.success(t('customers.sendInstagramSuccess'))
    },
    onError: (error: any) => {
      toast.error(error?.data?.error || t('customers.sendInstagramError'))
    },
  })

  const sendWhatsAppMutation = useMutation({
    mutationFn: (message: string) => sendWhatsAppToCustomer(customerIdNum, message),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-activities', customer?.lead_id] })
      setWhatsappDialogOpen(false)
      setWhatsappMessage('')
      toast.success(t('customers.sendWhatsAppSuccess'))
    },
    onError: (error: any) => {
      toast.error(error?.data?.error || t('customers.sendWhatsAppError'))
    },
  })

  const getStatusColor = (status: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    const colorMap: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      active: 'default',
      inactive: 'secondary',
    }
    return colorMap[status] || 'default'
  }

  const getActivityIcon = (type: string) => {
    if (type.includes('telegram')) return '💬'
    if (type.includes('instagram')) return '📸'
    if (type.includes('whatsapp')) return '📱'
    if (type.includes('status')) return '🔄'
    if (type.includes('note')) return '📝'
    if (type.includes('task')) return '✅'
    return '📋'
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-muted-foreground">{t('customers.loadingDetails')}</p>
      </div>
    )
  }

  if (!customer) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-muted-foreground">{t('customers.notFound')}</p>
        <Link to="/customers">
          <Button variant="link">{t('customers.backToCustomers')}</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
          {/* Header */}
          <div className="px-4 lg:px-6">
            <div className="flex flex-col gap-3">
              <Link to="/customers">
                <Button variant="ghost" size="sm">
                  <ArrowLeftIcon className="h-4 w-4 mr-2" />
                  {t('customers.backToCustomers')}
                </Button>
              </Link>

              <div className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-bold">{customer.contact_person || 'Unnamed Customer'}</h1>

                  {/* Contact details inline */}
                  <div className="flex items-center gap-3 mt-1 text-sm">
                    {customer.email ? (
                      <a href={`mailto:${customer.email}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors">
                        <MailIcon className="h-3.5 w-3.5" />
                        <span>{customer.email}</span>
                      </a>
                    ) : null}
                    {customer.phone ? (
                      <a href={`tel:${customer.phone}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors">
                        <PhoneIcon className="h-3.5 w-3.5" />
                        <span>{customer.phone}</span>
                      </a>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant={getStatusColor(customer.customer_status)}>
                      {customer.customer_status_display}
                    </Badge>
                    {customer.segment_display ? (
                      <Badge variant="outline">{customer.segment_display}</Badge>
                    ) : null}
                    {customer.source ? (
                      <Badge variant="outline">{customer.source}</Badge>
                    ) : null}
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {customer.has_telegram ? (
                    <Button onClick={() => setTelegramDialogOpen(true)} size="sm">
                      <SendIcon className="h-4 w-4 mr-2" />
                      Telegram
                    </Button>
                  ) : null}
                  {customer.has_instagram ? (
                    <Button onClick={() => setInstagramDialogOpen(true)} variant="outline" size="sm">
                      <SendIcon className="h-4 w-4 mr-2" />
                      Instagram
                    </Button>
                  ) : null}
                  {customer.has_whatsapp ? (
                    <Button onClick={() => setWhatsappDialogOpen(true)} variant="outline" size="sm">
                      <MessageCircleIcon className="h-4 w-4 mr-2" />
                      WhatsApp
                    </Button>
                  ) : null}
                </div>

              </div>
            </div>
          </div>

          {/* Content */}
          <div className="px-4 lg:px-6">
            <div className="grid gap-4 md:grid-cols-2">
              {/* Communication Channels */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">{t('customers.communicationChannels')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {customer.telegram_username ? (
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Telegram</span>
                      <span>@{customer.telegram_username}</span>
                    </div>
                  ) : null}
                  {customer.instagram_username ? (
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Instagram</span>
                      <span>@{customer.instagram_username}</span>
                    </div>
                  ) : null}
                  {customer.whatsapp_phone ? (
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">WhatsApp</span>
                      <span>{customer.whatsapp_phone}</span>
                    </div>
                  ) : null}
                  {!customer.telegram_username && !customer.instagram_username && !customer.whatsapp_phone ? (
                    <p className="text-sm text-muted-foreground">{t('customers.noChannels')}</p>
                  ) : null}
                </CardContent>
              </Card>

              {/* Notes */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">{t('customers.customerNotes')}</CardTitle>
                </CardHeader>
                <CardContent>
                  {customer.notes ? (
                    <p className="text-sm whitespace-pre-wrap">{customer.notes}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">{t('customers.noNotes')}</p>
                  )}
                </CardContent>
              </Card>

              {/* Activity Timeline */}
              {customer.lead_id ? (
                <Card className="md:col-span-2">
                  <CardHeader>
                    <CardTitle className="text-lg">{t('customers.activityHistory')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {activities.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-4">{t('customers.noActivityHistory')}</p>
                    ) : (
                      <div className="space-y-3 max-h-[400px] overflow-y-auto">
                        {activities.slice(0, 20).map((activity: LeadActivity) => (
                          <div key={activity.id} className="flex gap-3 text-sm">
                            <span className="text-lg">{getActivityIcon(activity.activity_type)}</span>
                            <div className="flex-1 min-w-0">
                              <p className="text-foreground">{activity.description}</p>
                              <p className="text-xs text-muted-foreground">
                                {new Date(activity.created_at).toLocaleString()}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {/* Telegram Message Dialog */}
      <Dialog open={telegramDialogOpen} onOpenChange={setTelegramDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('customers.telegramDialogTitle')}</DialogTitle>
            <DialogDescription>
              {t('leads.sendMessageTo')} {customer.contact_person} {t('leads.viaTelegram')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="telegram-message" className="text-sm font-medium">
                {t('leads.message')}
              </label>
              <Textarea
                id="telegram-message"
                placeholder={t('leads.messagePlaceholder')}
                value={telegramMessage}
                onChange={(e) => setTelegramMessage(e.target.value)}
                rows={6}
                maxLength={4096}
              />
              <p className="text-xs text-muted-foreground">
                {telegramMessage.length} / 4096 characters
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setTelegramDialogOpen(false)
                setTelegramMessage('')
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => sendTelegramMutation.mutate(telegramMessage)}
              disabled={sendTelegramMutation.isPending || !telegramMessage.trim()}
            >
              {sendTelegramMutation.isPending ? t('leads.sending') : t('leads.sendMessage')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Instagram Message Dialog */}
      <Dialog open={instagramDialogOpen} onOpenChange={setInstagramDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('customers.instagramDialogTitle')}</DialogTitle>
            <DialogDescription>
              {t('leads.sendMessageTo')} {customer.contact_person} {t('leads.viaInstagram')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="instagram-message" className="text-sm font-medium">
                {t('leads.message')}
              </label>
              <Textarea
                id="instagram-message"
                placeholder={t('leads.messagePlaceholder')}
                value={instagramMessage}
                onChange={(e) => setInstagramMessage(e.target.value)}
                rows={6}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setInstagramDialogOpen(false)
                setInstagramMessage('')
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => sendInstagramMutation.mutate(instagramMessage)}
              disabled={sendInstagramMutation.isPending || !instagramMessage.trim()}
            >
              {sendInstagramMutation.isPending ? t('leads.sending') : t('leads.sendMessage')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* WhatsApp Message Dialog */}
      <Dialog open={whatsappDialogOpen} onOpenChange={setWhatsappDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('customers.whatsappDialogTitle')}</DialogTitle>
            <DialogDescription>
              {t('leads.sendMessageTo')} {customer.contact_person} {t('leads.viaWhatsApp')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="whatsapp-message" className="text-sm font-medium">
                {t('leads.message')}
              </label>
              <Textarea
                id="whatsapp-message"
                placeholder={t('leads.messagePlaceholder')}
                value={whatsappMessage}
                onChange={(e) => setWhatsappMessage(e.target.value)}
                rows={6}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setWhatsappDialogOpen(false)
                setWhatsappMessage('')
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => sendWhatsAppMutation.mutate(whatsappMessage)}
              disabled={sendWhatsAppMutation.isPending || !whatsappMessage.trim()}
            >
              {sendWhatsAppMutation.isPending ? t('leads.sending') : t('leads.sendMessage')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
