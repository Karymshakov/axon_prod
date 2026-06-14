import { useState, useRef, useEffect } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Check, X } from 'lucide-react'

interface InlineNotesEditorProps {
  value: string
  onSave: (value: string) => Promise<void>
  placeholder?: string
}

export function InlineNotesEditor({ value, onSave, placeholder = 'Добавить заметку...' }: InlineNotesEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value)
  const [isSaving, setIsSaving] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isEditing])

  const handleSave = async () => {
    if (editValue === value) {
      setIsEditing(false)
      return
    }

    setIsSaving(true)
    try {
      await onSave(editValue)
      setIsEditing(false)
    } catch (error) {
      // Error is handled by parent
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setEditValue(value)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleCancel()
    } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSave()
    }
  }

  if (isEditing) {
    return (
      <div className="flex flex-col gap-2 py-1" onClick={(e) => e.stopPropagation()}>
        <Textarea
          ref={textareaRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="min-h-[60px] resize-none text-sm"
          disabled={isSaving}
          data-cayu="Textarea:inline-note"
        />
        <div className="flex gap-1">
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving}
            data-cayu="Button:save-note"
          >
            <Check className="h-3 w-3" />
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleCancel}
            disabled={isSaving}
            data-cayu="Button:cancel-note"
          >
            <X className="h-3 w-3" />
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div
      className="cursor-pointer text-sm text-muted-foreground hover:text-foreground transition-colors py-1 min-h-[20px] break-words whitespace-normal"
      onClick={(e) => {
        e.stopPropagation()
        setIsEditing(true)
      }}
      data-cayu="InlineNoteDisplay"
    >
      {value || <span className="italic">{placeholder}</span>}
    </div>
  )
}
