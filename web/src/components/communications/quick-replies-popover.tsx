import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileTextIcon, SearchIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { fetchReplyTemplates, type ReplyTemplate, type ReplyTemplateChannel } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'

interface TemplateCategory {
  key: string
  label: string
  templates: ReplyTemplate[]
}

interface QuickRepliesPopoverProps {
  channel: ReplyTemplateChannel
  onSelectTemplate: (text: string) => void
}

export function QuickRepliesPopover({ channel, onSelectTemplate }: QuickRepliesPopoverProps) {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const orgSlug = user?.current_organization_slug ?? ''

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['reply-templates', orgSlug, channel],
    queryFn: () => fetchReplyTemplates(channel),
    enabled: open && !!orgSlug,
  })

  const categories = useMemo<TemplateCategory[]>(() => {
    const grouped = new Map<number, TemplateCategory>()
    for (const template of templates) {
      const existing = grouped.get(template.category)
      if (existing) {
        existing.templates.push(template)
      } else {
        grouped.set(template.category, {
          key: String(template.category),
          label: template.category_name || 'Без категории',
          templates: [template],
        })
      }
    }
    return [...grouped.values()].map((category) => ({
      ...category,
      templates: [...category.templates].sort((a, b) => a.order - b.order || a.title.localeCompare(b.title)),
    }))
  }, [templates])

  const filteredCategories = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return categories
    return categories
      .map((category) => ({
        ...category,
        templates: category.templates.filter((template) =>
          template.title.toLowerCase().includes(query) ||
          template.text.toLowerCase().includes(query) ||
          template.tags.some((tag) => tag.toLowerCase().includes(query)),
        ),
      }))
      .filter((category) => category.templates.length > 0)
  }, [categories, search])

  const handleSelect = (text: string) => {
    onSelectTemplate(text)
    setOpen(false)
  }

  const renderTemplateButton = (template: ReplyTemplate) => (
    <button
      key={template.id}
      onClick={() => handleSelect(template.text)}
      className="flex w-full flex-col gap-0.5 rounded-md border border-transparent p-2 text-left outline-none transition-all hover:border-border hover:bg-muted/80 focus-visible:ring-1 focus-visible:ring-primary"
    >
      <span className="text-xs font-semibold text-foreground">{template.title}</span>
      <p className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
        {template.text}
      </p>
    </button>
  )

  const firstCategoryKey = filteredCategories[0]?.key

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 border-dashed border-primary/40 text-primary hover:bg-primary/5"
        >
          <FileTextIcon className="h-4 w-4" />
          Шаблоны ответов
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-3 sm:w-96" align="start">
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b pb-2">
            <h4 className="text-sm font-semibold">Быстрые шаблоны</h4>
            <span className="text-[10px] text-muted-foreground">Вставка в сообщение</span>
          </div>

          <div className="relative">
            <SearchIcon className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Поиск по шаблонам..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 pl-8 text-xs"
            />
          </div>

          {isLoading ? (
            <div className="py-8 text-center text-xs text-muted-foreground">Загрузка...</div>
          ) : filteredCategories.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground">Шаблоны не найдены</div>
          ) : search ? (
            <ScrollArea className="h-60">
              <div className="space-y-2 pr-2">
                {filteredCategories.flatMap((category) => category.templates).map(renderTemplateButton)}
              </div>
            </ScrollArea>
          ) : (
            <Tabs defaultValue={firstCategoryKey ?? ''} className="w-full">
              <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 bg-muted p-1">
                {filteredCategories.map((category) => (
                  <TabsTrigger
                    key={category.key}
                    value={category.key}
                    className="h-7 px-2 text-[10px]"
                  >
                    {category.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              {filteredCategories.map((category) => (
                <TabsContent key={category.key} value={category.key} className="mt-2 outline-none">
                  <ScrollArea className="h-60">
                    <div className="space-y-2 pr-2">
                      {category.templates.map(renderTemplateButton)}
                    </div>
                  </ScrollArea>
                </TabsContent>
              ))}
            </Tabs>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
