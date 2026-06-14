import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MessageSquareIcon, PlusIcon, TrashIcon } from 'lucide-react'
import { fetchLeadNotes, createLeadNote, deleteLeadNote, type LeadNote } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from 'sonner'
import { useLanguage } from '@/contexts/language-context'

interface LeadNotesProps {
  leadId: number
}

export function LeadNotes({ leadId }: LeadNotesProps) {
  const { t } = useLanguage()
  const [newNote, setNewNote] = useState('')
  const queryClient = useQueryClient()

  const { data: notes = [], isLoading } = useQuery({
    queryKey: ['lead-notes', leadId],
    queryFn: () => fetchLeadNotes(leadId),
  })

  const createMutation = useMutation({
    mutationFn: createLeadNote,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-notes', leadId] })
      queryClient.invalidateQueries({ queryKey: ['lead-activities', leadId] })
      setNewNote('')
      toast.success(t('leads.noteAdded'))
    },
    onError: () => {
      toast.error(t('leads.noteAddError'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteLeadNote,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-notes', leadId] })
      toast.success(t('leads.noteDeleted'))
    },
    onError: () => {
      toast.error(t('leads.noteDeleteError'))
    },
  })

  const handleAddNote = () => {
    if (!newNote.trim()) {
      toast.error(t('leads.enterNote'))
      return
    }

    createMutation.mutate({
      lead: leadId,
      content: newNote,
    })
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquareIcon className="h-4 w-4" />
          {t('leads.notes')}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add new note */}
        <div className="space-y-2">
          <Textarea
            placeholder={t('leads.notePlaceholder')}
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            rows={3}
          />
          <Button
            onClick={handleAddNote}
            disabled={createMutation.isPending || !newNote.trim()}
            size="sm"
          >
            <PlusIcon className="h-4 w-4 mr-1" />
            {t('leads.addNote')}
          </Button>
        </div>

        {/* Notes list */}
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t('leads.loadingNotes')}</p>
        ) : notes.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('leads.noNotesYet')}</p>
        ) : (
          <div className="space-y-3">
            {notes.map((note: LeadNote) => (
              <div key={note.id} className="rounded-lg border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm whitespace-pre-wrap break-words">{note.content}</p>
                    <p className="text-xs text-muted-foreground mt-2">
                      {formatDate(note.created_at)}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    onClick={() => deleteMutation.mutate(note.id)}
                    disabled={deleteMutation.isPending}
                    aria-label="Удалить заметку"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
