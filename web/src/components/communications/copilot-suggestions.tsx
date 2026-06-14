import { useState } from 'react'
import { SparklesIcon, CopyIcon, CheckIcon, RefreshCwIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { generateCopilotSuggestion } from '@/lib/api'
import { toast } from 'sonner'

interface CopilotSuggestionsProps {
  leadId: number
  onSelectSuggestion: (text: string) => void
}

export function CopilotSuggestions({ leadId, onSelectSuggestion }: CopilotSuggestionsProps) {
  const [suggestion, setSuggestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    setIsLoading(true)
    setSuggestion('')
    try {
      const response = await generateCopilotSuggestion(leadId)
      if (response.suggestion) {
        setSuggestion(response.suggestion)
      } else {
        toast.error('ИИ не вернул вариантов ответа для этого диалога.')
      }
    } catch (err) {
      console.error(err)
      toast.error('Ошибка при генерации подсказки ИИ.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleApply = () => {
    onSelectSuggestion(suggestion)
    toast.success('Подсказка скопирована в поле ввода!')
  }

  const handleCopyToClipboard = () => {
    navigator.clipboard.writeText(suggestion)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast.success('Скопировано в буфер обмена')
  }

  return (
    <div className="rounded-lg border bg-gradient-to-r from-purple-50 to-indigo-50/50 p-3 dark:from-purple-950/20 dark:to-indigo-950/10 border-purple-100 dark:border-purple-900/40">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-purple-800 dark:text-purple-300">
          <SparklesIcon className="h-4 w-4 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider">ИИ-ассистент</span>
        </div>
        
        <Button 
          type="button"
          size="sm" 
          variant="ghost" 
          onClick={handleGenerate} 
          disabled={isLoading}
          className="h-7 text-xs text-purple-700 hover:text-purple-900 hover:bg-purple-100/60 dark:text-purple-300 gap-1"
        >
          <RefreshCwIcon className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
          {suggestion ? 'Обновить черновик' : 'Предложить ответ'}
        </Button>
      </div>

      {isLoading && (
        <div className="mt-2 text-xs text-purple-600/80 dark:text-purple-400 flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
          </span>
          ИИ анализирует историю диалога и контекст гостя...
        </div>
      )}

      {suggestion && !isLoading && (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-foreground bg-white/80 dark:bg-slate-900/40 p-2.5 rounded-md border border-purple-100/60 leading-relaxed font-medium break-words">
            {suggestion}
          </p>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              className="h-8 bg-purple-600 hover:bg-purple-700 text-white text-xs gap-1"
              onClick={handleApply}
            >
              Использовать в чате
            </Button>
            
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 text-xs gap-1"
              onClick={handleCopyToClipboard}
            >
              {copied ? <CheckIcon className="h-3 w-3 text-green-600" /> : <CopyIcon className="h-3 w-3" />}
              Копировать
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
