import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Search, Check, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import {
  fetchLeads,
  mergeLead,
  getContactChannelLabel,
  resolveLeadContactChannel,
  type Lead,
} from '@/lib/api'
import { toast } from 'sonner'

interface MergeLeadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sourceLead: Lead
  onSuccess?: (targetLeadId: number) => void
}

export function MergeLeadDialog({
  open,
  onOpenChange,
  sourceLead,
  onSuccess,
}: MergeLeadDialogProps) {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTarget, setSelectedTarget] = useState<Lead | null>(null)

  // Fetch all leads for search selection
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['leads-for-merge'],
    queryFn: () => fetchLeads(),
    enabled: open,
  })

  // Filter other leads by search query (excluding source lead itself)
  const filteredLeads = useMemo(() => {
    return leads.filter((l) => {
      if (l.id === sourceLead.id) return false
      
      if (!searchQuery.trim()) return true
      
      const query = searchQuery.toLowerCase()
      const nameMatch = (l.contact_person || '').toLowerCase().includes(query)
      const phoneMatch = (l.phone || '').toLowerCase().includes(query)
      const emailMatch = (l.email || '').toLowerCase().includes(query)
      const tgMatch = (l.telegram_username || '').toLowerCase().includes(query)
      const igMatch = (l.instagram_username || '').toLowerCase().includes(query)
      
      return nameMatch || phoneMatch || emailMatch || tgMatch || igMatch
    })
  }, [leads, sourceLead.id, searchQuery])

  const mergeMutation = useMutation({
    mutationFn: (targetId: number) => mergeLead(sourceLead.id, targetId),
    onSuccess: (data) => {
      toast.success('Лиды успешно объединены')
      
      // Invalidate queries
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead-stats'] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', sourceLead.id] })
      if (selectedTarget) {
        queryClient.invalidateQueries({ queryKey: ['lead-activities', selectedTarget.id] })
      }

      onOpenChange(false)
      setSelectedTarget(null)
      setSearchQuery('')
      
      if (onSuccess && data.target_lead_id) {
        onSuccess(data.target_lead_id)
      }
    },
    onError: (err: any) => {
      console.error(err)
      const errMsg = err?.response?.data?.error || 'Не удалось объединить лидов'
      toast.error(errMsg)
    },
  })

  const handleConfirmMerge = () => {
    if (!selectedTarget) return
    mergeMutation.mutate(selectedTarget.id)
  }

  const formatLeadDetails = (lead: Lead) => {
    const parts: string[] = []
    if (lead.phone) parts.push(lead.phone)
    if (lead.check_in_date) {
      parts.push(`Заезд: ${lead.check_in_date}`)
    }
    return parts.join(' · ')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] p-6 flex flex-col max-h-[90vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-base font-bold">Объединение дубликатов гостей</DialogTitle>
          <DialogDescription className="text-xs leading-normal">
            Вы можете перенести всю историю общения, заметки и задачи из текущей карточки в другую карточку этого же гостя.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col min-h-0 space-y-4 my-2">
          {/* Source lead indicator */}
          <div className="bg-muted/40 border rounded-lg p-3 text-xs">
            <span className="font-semibold text-muted-foreground block mb-1">ИСТОЧНИК (будет удален):</span>
            <div className="flex justify-between items-center">
              <div>
                <span className="font-bold text-foreground">{sourceLead.contact_person || 'Без имени'}</span>
                <span className="text-muted-foreground block mt-0.5">{formatLeadDetails(sourceLead)}</span>
              </div>
              <Badge variant="outline" className="text-[10px]">
                {getContactChannelLabel(resolveLeadContactChannel(sourceLead))}
              </Badge>
            </div>
          </div>

          {/* Search selection */}
          {!selectedTarget ? (
            <div className="flex-1 flex flex-col min-h-0 space-y-2">
              <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Выберите целевого гостя (куда перенести):</label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Поиск по имени, телефону или никнейму..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 h-9 text-xs"
                />
              </div>

              <ScrollArea className="flex-1 border rounded-lg bg-background">
                {isLoading ? (
                  <div className="flex items-center justify-center py-8 text-xs text-muted-foreground gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    Загрузка гостей...
                  </div>
                ) : filteredLeads.length === 0 ? (
                  <div className="text-center py-8 text-xs text-muted-foreground">
                    Гости не найдены
                  </div>
                ) : (
                  <div className="divide-y">
                    {filteredLeads.map((lead) => (
                      <button
                        key={lead.id}
                        type="button"
                        onClick={() => setSelectedTarget(lead)}
                        className="w-full text-left p-3 hover:bg-muted/50 transition flex justify-between items-center text-xs"
                      >
                        <div className="min-w-0 pr-4">
                          <span className="font-semibold text-foreground block truncate">
                            {lead.contact_person || 'Без имени'}
                          </span>
                          <span className="text-muted-foreground block truncate mt-0.5">
                            {formatLeadDetails(lead)}
                          </span>
                        </div>
                        <Badge variant="outline" className="text-[10px] shrink-0">
                          {getContactChannelLabel(resolveLeadContactChannel(lead))}
                        </Badge>
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </div>
          ) : (
            /* Confirm selection warning view */
            <div className="space-y-4">
              <div className="bg-amber-50 dark:bg-amber-950/25 border border-amber-200 dark:border-amber-900/50 rounded-lg p-4 text-xs flex gap-3 text-amber-800 dark:text-amber-400">
                <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-500" />
                <div>
                  <span className="font-bold block mb-1">Это действие нельзя отменить!</span>
                  Все сообщения из чата, задачи и заметки из карточки <span className="font-bold">{sourceLead.contact_person || 'Без имени'}</span> будут присоединены к карточке <span className="font-bold">{selectedTarget.contact_person || 'Без имени'}</span>. Текущая карточка будет безвозвратно удалена.
                </div>
              </div>

              <div className="bg-muted/40 border rounded-lg p-3 text-xs">
                <span className="font-semibold text-muted-foreground block mb-1">ЦЕЛЬ (сохранится и обновится):</span>
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-bold text-foreground">{selectedTarget.contact_person || 'Без имени'}</span>
                    <span className="text-muted-foreground block mt-0.5">{formatLeadDetails(selectedTarget)}</span>
                  </div>
                  <Badge variant="outline" className="text-[10px]">
                    {getContactChannelLabel(resolveLeadContactChannel(selectedTarget))}
                  </Badge>
                </div>
              </div>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSelectedTarget(null)}
                className="w-full text-xs"
              >
                Выбрать другого гостя
              </Button>
            </div>
          )}
        </div>

        <DialogFooter className="border-t pt-3 flex sm:justify-end gap-2 shrink-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              onOpenChange(false)
              setSelectedTarget(null)
              setSearchQuery('')
            }}
            className="text-xs"
            disabled={mergeMutation.isPending}
          >
            Отмена
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleConfirmMerge}
            disabled={!selectedTarget || mergeMutation.isPending}
            className="text-xs gap-1.5"
          >
            {mergeMutation.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Объединение...
              </>
            ) : (
              'Подтвердить объединение'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
