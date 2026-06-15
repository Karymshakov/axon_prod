import { useState } from 'react'
import { FileTextIcon, SearchIcon, PlusIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'

interface Template {
  id: string
  title: string
  text: string
}

interface TemplateCategory {
  key: string
  label: string
  templates: Template[]
}

const TEMPLATES: TemplateCategory[] = [
  {
    key: 'general',
    label: 'Общие',
    templates: [
      {
        id: 'g1',
        title: 'Приветствие',
        text: 'Здравствуйте! Рады приветствовать вас. Чем мы можем помочь вам сегодня?'
      },
      {
        id: 'g2',
        title: 'Завершение диалога',
        text: 'Если у вас возникнут еще какие-либо вопросы, мы с радостью ответим на них. Хорошего дня!'
      }
    ]
  },
  {
    key: 'checkin',
    label: 'Заселение',
    templates: [
      {
        id: 'c1',
        title: 'Правила заселения',
        text: 'Стандартное время заезда в наш отель — с 14:00, выезда — до 12:00. При себе необходимо иметь паспорт. Возможен ранний заезд по предварительному согласованию при наличии свободных номеров.'
      },
      {
        id: 'c2',
        title: 'Необходимые документы',
        text: 'Для заселения гражданам РФ потребуется паспорт РФ на каждого гостя. Для детей до 14 лет — оригинал свидетельства о рождении. Для иностранных граждан — паспорт, виза (при необходимости) и миграционная карта.'
      }
    ]
  },
  {
    key: 'pricing',
    label: 'Цены & Услуги',
    templates: [
      {
        id: 'p1',
        title: 'Способы оплаты',
        text: 'Вы можете оплатить проживание банковской картой на сайте при бронировании, переводом на расчетный счет или наличными/картой на стойке регистрации при заселении.'
      },
      {
        id: 'p2',
        title: 'Питание (Завтрак)',
        text: 'Завтрак проходит по системе «Шведский стол» в нашем ресторане с 07:30 до 10:30 по будням и с 08:00 до 11:00 по выходным. Стоимость завтрака, если он не включен в тариф — 900 рублей с человека.'
      }
    ]
  },
  {
    key: 'location',
    label: 'Адрес & Проезд',
    templates: [
      {
        id: 'l1',
        title: 'Адрес и контакты',
        text: 'Наш адрес: г. Москва, ул. Примерная, д. 15. Стойка регистрации работает круглосуточно. Телефон для связи: +7 (495) 123-45-67.'
      },
      {
        id: 'l2',
        title: 'Как добраться',
        text: 'Мы находимся в 5 минутах ходьбы от станции метро «Парк Культуры». Выход №3, далее прямо по улице до перекрестка, затем направо. Для гостей на автомобиле есть бесплатная охраняемая парковка.'
      }
    ]
  }
]

interface QuickRepliesPopoverProps {
  onSelectTemplate: (text: string) => void
}

export function QuickRepliesPopover({ onSelectTemplate }: QuickRepliesPopoverProps) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)

  const handleSelect = (text: string) => {
    onSelectTemplate(text)
    setOpen(false)
  }

  // Filter templates based on search query
  const filteredCategories = TEMPLATES.map(category => {
    const filteredTemplates = category.templates.filter(
      t => 
        t.title.toLowerCase().includes(search.toLowerCase()) || 
        t.text.toLowerCase().includes(search.toLowerCase())
    )
    return {
      ...category,
      templates: filteredTemplates
    }
  }).filter(category => category.templates.length > 0)

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
            <h4 className="font-semibold text-sm">Быстрые шаблоны</h4>
            <span className="text-[10px] text-muted-foreground">Нажмите для вставки в чат</span>
          </div>

          <div className="relative">
            <SearchIcon className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Поиск по шаблонам..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>

          {search ? (
            <ScrollArea className="h-60">
              <div className="space-y-3 pr-2">
                {filteredCategories.length === 0 ? (
                  <div className="text-center text-xs text-muted-foreground py-8">
                    Шаблоны не найдены
                  </div>
                ) : (
                  filteredCategories.flatMap(cat => cat.templates).map(template => (
                    <button
                      key={template.id}
                      onClick={() => handleSelect(template.text)}
                      className="w-full text-left p-2 rounded-md hover:bg-muted border border-transparent hover:border-border transition-all flex flex-col gap-0.5 outline-none focus-visible:ring-1 focus-visible:ring-primary"
                    >
                      <span className="text-xs font-semibold text-foreground">{template.title}</span>
                      <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                        {template.text}
                      </p>
                    </button>
                  ))
                )}
              </div>
            </ScrollArea>
          ) : (
            <Tabs defaultValue="general" className="w-full">
              <TabsList className="w-full grid grid-cols-4 h-8 p-0.5 bg-muted">
                {TEMPLATES.map(cat => (
                  <TabsTrigger 
                    key={cat.key} 
                    value={cat.key} 
                    className="text-[10px] py-1 px-1 h-full"
                  >
                    {cat.label}
                  </TabsTrigger>
                ))}
              </TabsList>
              
              {TEMPLATES.map(category => (
                <TabsContent key={category.key} value={category.key} className="mt-2 outline-none">
                  <ScrollArea className="h-60">
                    <div className="space-y-2 pr-2">
                      {category.templates.map(template => (
                        <button
                          key={template.id}
                          onClick={() => handleSelect(template.text)}
                          className="w-full text-left p-2 rounded-md hover:bg-muted/80 border border-transparent hover:border-border transition-all flex flex-col gap-0.5 outline-none focus-visible:ring-1 focus-visible:ring-primary"
                        >
                          <span className="text-xs font-semibold text-foreground">{template.title}</span>
                          <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                            {template.text}
                          </p>
                        </button>
                      ))}
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
