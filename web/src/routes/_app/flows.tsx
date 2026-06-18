import { createFileRoute, Navigate } from '@tanstack/react-router'
import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  Handle,
  Position,
  BackgroundVariant,
  Panel,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  PlusIcon,
  Trash2Icon,
  ZapIcon,
  AlertTriangleIcon,
  PlayIcon,
  CheckCircle2Icon,
  XIcon,
  SaveIcon,
  SparklesIcon,
  GitBranchIcon,
  ArrowRightIcon,
  InfoIcon,
  BookOpenIcon,
  ChevronDownIcon,
  FileTextIcon,
  WrenchIcon,
  BotIcon,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Checkbox } from '@/components/ui/checkbox'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  fetchFlows,
  fetchFlow,
  createFlow,
  updateFlow,
  deleteFlow,
  activateFlow,
  createFlowCard,
  updateFlowCard,
  deleteFlowCard,
  createFlowConnection,
  deleteFlowConnection,
  fetchAITools,
  updateAITool,
  createAITool,
  deleteAITool,
  fetchAIModelConfig,
  updateAIModelConfig,
  fetchTransferConfig,
  updateTransferConfig,
  fetchPlaybooks,
  fetchAgents,
  updateAgent,
  type FlowCard,
  type ConversationFlow,
  type AITool,
  type AIModelConfig,
  type ManagerTransferConfig,
  type Playbook,
  type AgentConfig,
} from '@/lib/api'
import { Slider } from '@/components/ui/slider'
import { useAuth } from '@/contexts/auth-context'
import { useLanguage } from '@/contexts/language-context'

export const Route = createFileRoute('/_app/flows')({
  component: FlowsPage,
})

function canManageWorkspace(user: ReturnType<typeof useAuth>['user']) {
  return Boolean(
    user?.is_superadmin ||
    user?.is_admin ||
    user?.current_organization_role === 'owner' ||
    user?.current_organization_role === 'admin',
  )
}

// ─── Card type styles ──────────────────────────────────────────────────────────

const CARD_TYPE_CONFIG = {
  entry: {
    label: 'Вход',
    icon: ZapIcon,
    border: 'border-emerald-400',
    bg: 'bg-emerald-50',
    badge: 'bg-emerald-100 text-emerald-700 border-emerald-300',
    handleColor: '#10b981',
  },
  normal: {
    label: 'Сообщение',
    icon: ArrowRightIcon,
    border: 'border-sky-400',
    bg: 'bg-sky-50',
    badge: 'bg-sky-100 text-sky-700 border-sky-300',
    handleColor: '#0ea5e9',
  },
  escalation: {
    label: 'Эскалация',
    icon: AlertTriangleIcon,
    border: 'border-red-400',
    bg: 'bg-red-50',
    badge: 'bg-red-100 text-red-700 border-red-300',
    handleColor: '#ef4444',
  },
} as const

const PLACEHOLDERS = [
  { key: '{contact_person}', description: 'Имя контакта лида' },
  { key: '{check_in_date}', description: 'Дата заезда' },
  { key: '{check_out_date}', description: 'Дата выезда' },
  { key: '{num_guests}', description: 'Количество гостей' },
  { key: '{room_suggestion}', description: 'Рекомендация номера от ИИ' },
  { key: '{total_price}', description: 'Общая стоимость от ИИ' },
]

// ─── Custom Card Node ──────────────────────────────────────────────────────────

interface CardNodeData {
  card: FlowCard
  isSelected: boolean
  onSelect: (card: FlowCard) => void
  [key: string]: unknown
}

function CardNode({ data }: { data: CardNodeData }) {
  const { card, isSelected, onSelect } = data
  const cfg = CARD_TYPE_CONFIG[card.card_type]
  const Icon = cfg.icon

  return (
    <div
      className={`
        relative w-60 rounded-xl border-2 ${cfg.border} ${cfg.bg}
        backdrop-blur-sm cursor-pointer select-none
        transition-all duration-150
        ${isSelected ? 'ring-2 ring-black/10 ring-offset-2 ring-offset-transparent shadow-xl scale-105' : 'hover:brightness-95 shadow-md'}
      `}
      onClick={() => onSelect(card)}
    >
      {/* Source handle */}
      {card.card_type !== 'escalation' && (
        <Handle
          type="source"
          position={Position.Bottom}
          style={{ background: cfg.handleColor, width: 10, height: 10, border: '2px solid rgba(0,0,0,0.15)' }}
        />
      )}
      {/* Target handle */}
      {card.card_type !== 'entry' && (
        <Handle
          type="target"
          position={Position.Top}
          style={{ background: cfg.handleColor, width: 10, height: 10, border: '2px solid rgba(0,0,0,0.15)' }}
        />
      )}

      <div className="p-3">
        <div className="flex items-center gap-2 mb-2">
          <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-xs font-semibold text-foreground truncate flex-1">{card.title}</span>
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${cfg.badge}`}>
            {cfg.label}
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
          {card.message_template || <span className="italic opacity-50">Сообщение не задано</span>}
        </p>
        {card.playbook_names && card.playbook_names.length > 0 ? (
          <div className="flex items-center gap-1 mt-1.5 pt-1.5 border-t border-black/5">
            <BookOpenIcon className="h-2.5 w-2.5 text-violet-500 shrink-0" />
            <span className="text-[10px] text-violet-600 font-medium truncate">
              {card.playbook_names.length === 1
                ? card.playbook_names[0]
                : `${card.playbook_names[0]} +${card.playbook_names.length - 1}`}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}

const nodeTypes: NodeTypes = { card: CardNode }

// ─── Tools Panel ───────────────────────────────────────────────────────────────

type ToolLocale = 'en' | 'ru'

const STANDARD_TOOL_TRANSLATIONS: Record<string, Record<ToolLocale, Pick<AITool, 'display_name' | 'description'>>> = {
  get_room_options: {
    en: {
      display_name: 'Get Room Options',
      description:
        'Use for standard groups: couples, friends, colleagues, solo travelers. Never call this when the guest mentions children, kids, baby, toddler, son, daughter, or family.',
    },
    ru: {
      display_name: 'Получить варианты номеров',
      description:
        'Использовать для стандартных групп: пары, друзья, коллеги, соло-путешественники. Никогда не вызывать, если гость упоминает детей, kids, baby, toddler, son, daughter или family.',
    },
  },
  get_meal_plan_pricing: {
    en: {
      display_name: 'Get Meal Plan Pricing',
      description:
        "Look up meal plan prices for a specific room type. Call this after room selection and whenever the guest asks any question about food, meals, питание, dining, or what is included in the price. This is the only authoritative source for meal pricing. It returns total_price_per_night for each meal plan: the complete all-in nightly rate, room + meals combined. It is not an add-on fee. Do not subtract the room base price, never present a delta, and quote total_price_per_night directly.",
    },
    ru: {
      display_name: 'Получить цены на питание',
      description:
        'Узнать стоимость питания для конкретного типа номера. Вызывать после выбора номера и каждый раз, когда гость спрашивает про еду, питание, meals, dining или «что включено в стоимость». Это единственный авторитетный источник цен на питание. Инструмент возвращает total_price_per_night для каждого тарифа: полную цену за ночь, номер + питание вместе. Это не доплата. Не вычитать базовую цену номера, не показывать разницу, а называть total_price_per_night напрямую.',
    },
  },
  transfer_to_manager: {
    en: {
      display_name: 'Transfer to Manager',
      description:
        'Notify the hotel manager about a completed or escalated lead. Call when the booking is complete, the guest is a legal entity or requests an invoice/contract, there is a corporate/event/sports-camp request, a complaint/refund/conflict, a group over 10 must be transferred, or the guest asks something outside the knowledge base. If you tell the guest they will be transferred to a manager, this tool must be called in the same turn.',
    },
    ru: {
      display_name: 'Передать менеджеру',
      description:
        'Уведомить менеджера отеля о завершенной или эскалированной заявке. Вызывать, когда бронирование завершено, гость является юрлицом или просит счет/договор, есть запрос на корпоратив/мероприятие/спортивные сборы, жалоба/возврат/конфликт, группу больше 10 человек нужно передать менеджеру, или гость задает вопрос вне базы знаний. Если вы говорите гостю, что передаете его менеджеру, этот инструмент должен быть вызван в том же ходе.',
    },
  },
  get_room_images: {
    en: {
      display_name: 'Send Room Photos',
      description:
        'Send hotel room photos to the guest. Call this when the guest asks to see a room, asks what a room looks like, or requests photos. Infer the room category from context: 1-2 guests means standard_queen or standard_twin; 3-4 guests or comfort means comfort; family with confirmed children means family. Pass multiple categories when the guest asks to see all rooms.',
    },
    ru: {
      display_name: 'Отправить фото номеров',
      description:
        'Отправить гостю фотографии номеров. Вызывать, когда гость просит показать номер, спрашивает, как он выглядит, или просит фото. Категорию определять из контекста: 1-2 гостя — standard_queen или standard_twin; 3-4 гостя или «комфорт» — comfort; семья с подтвержденными детьми — family. Если гость просит показать все номера, передавать несколько категорий.',
    },
  },
  get_family_room: {
    en: {
      display_name: 'Get Family Room',
      description:
        'Use only when the guest mentions children, kids, baby, toddler, son, daughter, family, or any indication they are travelling with minors. Returns family room options only. guest_count should include adults only; do not count children under 6.',
    },
    ru: {
      display_name: 'Получить семейный номер',
      description:
        'Использовать только когда гость упоминает детей, kids, baby, toddler, son, daughter, family или есть любой признак, что он едет с несовершеннолетними. Возвращает только семейные варианты номеров. guest_count должен включать только взрослых; детей до 6 лет не считать.',
    },
  },
}

function localizeTool(tool: AITool, language: ToolLocale): AITool {
  const translation = STANDARD_TOOL_TRANSLATIONS[tool.name]?.[language]
  return translation ? { ...tool, ...translation } : tool
}

const STANDARD_FLOW_TRANSLATIONS: Record<string, Record<ToolLocale, Pick<ConversationFlow, 'name' | 'description'>>> = {
  'Hotel Individual Booking': {
    en: {
      name: 'Hotel Individual Booking',
      description: 'Guides a lead from first contact through room selection and booking confirmation.',
    },
    ru: {
      name: 'Индивидуальное бронирование отеля',
      description: 'Проводит лида от первого обращения через выбор номера до подтверждения бронирования.',
    },
  },
}

function localizeFlow<T extends ConversationFlow | null | undefined>(flow: T, language: ToolLocale): T {
  if (!flow) return flow
  const translation = STANDARD_FLOW_TRANSLATIONS[flow.name]?.[language]
  return translation ? { ...flow, ...translation } : flow
}

function ToolsPanel() {
  const qc = useQueryClient()
  const { language } = useLanguage()
  const [editingTool, setEditingTool] = useState<AITool | null>(null)
  const [draftDescription, setDraftDescription] = useState('')
  const [draftDisplayName, setDraftDisplayName] = useState('')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [deletingToolId, setDeletingToolId] = useState<number | null>(null)

  const { data: tools = [] } = useQuery({ queryKey: ['ai-tools'], queryFn: fetchAITools })
  const displayedTools = useMemo(
    () => tools.map((tool) => localizeTool(tool, language)),
    [tools, language],
  )
  const labels = language === 'ru'
    ? {
        saved: 'Инструмент сохранен',
        created: 'Инструмент создан',
        createError: 'Не удалось создать инструмент',
        deleted: 'Инструмент удален',
        enabledTitle: 'Включено — нажмите, чтобы отключить',
        disabledTitle: 'Отключено — нажмите, чтобы включить',
        edit: 'Редактировать',
        noTools: 'Инструменты не настроены',
        addTool: 'Добавить инструмент',
        editTool: 'Редактировать инструмент',
        displayName: 'Отображаемое имя',
        description: 'Описание',
        descriptionHint: 'сообщает AI, когда вызывать этот инструмент',
        cancel: 'Отмена',
        saving: 'Сохранение...',
        save: 'Сохранить',
        addToolTitle: 'Добавить инструмент',
        internalName: 'Внутреннее имя',
        internalNameHint: 'snake_case, совпадает с обработчиком Python',
        internalNamePlaceholder: 'напр. get_availability',
        displayNamePlaceholder: 'напр. Проверить доступность',
        descriptionPlaceholder: 'Опишите, когда AI должен вызывать этот инструмент и что он делает...',
        creating: 'Создание...',
        createTool: 'Создать инструмент',
        deleteTitle: 'Удалить инструмент?',
        deleteDesc: 'Это навсегда удалит этот инструмент. AI больше не сможет вызывать его. Это действие нельзя отменить.',
        delete: 'Удалить',
        deleteAria: 'Удалить инструмент',
      }
    : {
        saved: 'Tool saved',
        created: 'Tool created',
        createError: 'Failed to create tool',
        deleted: 'Tool deleted',
        enabledTitle: 'Enabled — click to disable',
        disabledTitle: 'Disabled — click to enable',
        edit: 'Edit',
        noTools: 'No tools configured',
        addTool: 'Add tool',
        editTool: 'Edit tool',
        displayName: 'Display name',
        description: 'Description',
        descriptionHint: 'tells AI when to call this tool',
        cancel: 'Cancel',
        saving: 'Saving...',
        save: 'Save',
        addToolTitle: 'Add tool',
        internalName: 'Internal name',
        internalNameHint: 'snake_case, matches the Python handler',
        internalNamePlaceholder: 'e.g. get_availability',
        displayNamePlaceholder: 'e.g. Check availability',
        descriptionPlaceholder: 'Describe when AI should call this tool and what it does...',
        creating: 'Creating...',
        createTool: 'Create tool',
        deleteTitle: 'Delete tool?',
        deleteDesc: 'This will permanently delete this tool. AI will no longer be able to call it. This action cannot be undone.',
        delete: 'Delete',
        deleteAria: 'Delete tool',
      }

  const patchMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateAITool>[1] }) =>
      updateAITool(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-tools'] })
      setEditingTool(null)
      toast.success(labels.saved)
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_enabled }: { id: number; is_enabled: boolean }) =>
      updateAITool(id, { is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-tools'] }),
  })

  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof createAITool>[0]) => createAITool(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-tools'] })
      setShowAddDialog(false)
      setNewName('')
      setNewDisplayName('')
      setNewDescription('')
      toast.success(labels.created)
    },
    onError: () => toast.error(labels.createError),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteAITool(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-tools'] })
      setDeletingToolId(null)
      toast.success(labels.deleted)
    },
  })

  const openEdit = (tool: AITool) => {
    setEditingTool(tool)
    setDraftDescription(tool.description)
    setDraftDisplayName(tool.display_name)
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-xl mx-auto space-y-2">
        {displayedTools.map((tool) => {
          const rawTool = tools.find((item) => item.id === tool.id) ?? tool
          return (
          <div
            key={tool.id}
            className="rounded-lg border border-border bg-background p-3 space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-foreground truncate">{tool.display_name}</p>
                <p className="text-[10px] text-muted-foreground font-mono mt-0.5">{tool.name}</p>
              </div>
              <button
                onClick={() => toggleMutation.mutate({ id: tool.id, is_enabled: !tool.is_enabled })}
                className={`shrink-0 h-5 w-9 rounded-full transition-colors ${
                  tool.is_enabled ? 'bg-emerald-500' : 'bg-muted-foreground/30'
                }`}
                title={tool.is_enabled ? labels.enabledTitle : labels.disabledTitle}
              >
                <span
                  className={`block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform mx-0.5 ${
                    tool.is_enabled ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-3">
              {tool.description}
            </p>

            <div className="flex gap-1.5">
              <Button
                variant="outline"
                size="sm"
                className="h-6 text-[11px] flex-1"
                onClick={() => openEdit(rawTool)}
              >
                {labels.edit}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-6 w-6 p-0 text-red-400 hover:text-red-600 hover:border-red-200 hover:bg-red-50"
                onClick={() => setDeletingToolId(tool.id)}
                aria-label={labels.deleteAria}
              >
                <Trash2Icon className="h-3 w-3" />
              </Button>
            </div>
          </div>
        )})}

        {tools.length === 0 && (
          <p className="text-xs text-muted-foreground/50 text-center py-6">{labels.noTools}</p>
        )}

        {/* Add tool button */}
        <Button
          variant="outline"
          className="w-full text-xs hover:border-indigo-400/60 hover:text-indigo-600"
          size="sm"
          onClick={() => setShowAddDialog(true)}
        >
          <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
          {labels.addTool}
        </Button>
        </div>
      </div>

      {/* Edit dialog */}
      <Dialog open={editingTool !== null} onOpenChange={(open) => { if (!open) setEditingTool(null) }}>
        <DialogContent className="max-w-md max-h-[75vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>{labels.editTool}</DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto space-y-4 pr-1">
            <div>
              <Label className="mb-1.5 block text-xs">{labels.displayName}</Label>
              <Input
                value={draftDisplayName}
                onChange={(e) => setDraftDisplayName(e.target.value)}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">
                {labels.description} <span className="text-muted-foreground">({labels.descriptionHint})</span>
              </Label>
              <Textarea
                value={draftDescription}
                onChange={(e) => setDraftDescription(e.target.value)}
                rows={6}
                className="text-xs font-mono leading-relaxed resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingTool(null)}>{labels.cancel}</Button>
            <Button
              onClick={() => editingTool && patchMutation.mutate({
                id: editingTool.id,
                data: { display_name: draftDisplayName, description: draftDescription },
              })}
              disabled={patchMutation.isPending}
            >
              {patchMutation.isPending ? labels.saving : labels.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add tool dialog */}
      <Dialog open={showAddDialog} onOpenChange={(open) => { if (!open) setShowAddDialog(false) }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{labels.addToolTitle}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="mb-1.5 block text-xs">
                {labels.internalName} <span className="text-muted-foreground">({labels.internalNameHint})</span>
              </Label>
              <Input
                placeholder={labels.internalNamePlaceholder}
                value={newName}
                onChange={(e) => setNewName(e.target.value.toLowerCase().replace(/\s+/g, '_'))}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">{labels.displayName}</Label>
              <Input
                placeholder={labels.displayNamePlaceholder}
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">
                {labels.description} <span className="text-muted-foreground">({labels.descriptionHint})</span>
              </Label>
              <Textarea
                placeholder={labels.descriptionPlaceholder}
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                rows={6}
                className="text-xs font-mono leading-relaxed resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>{labels.cancel}</Button>
            <Button
              onClick={() => createMutation.mutate({
                name: newName.trim(),
                display_name: newDisplayName.trim(),
                description: newDescription.trim(),
              })}
              disabled={!newName.trim() || !newDisplayName.trim() || !newDescription.trim() || createMutation.isPending}
            >
              {createMutation.isPending ? labels.creating : labels.createTool}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={deletingToolId !== null} onOpenChange={(open) => { if (!open) setDeletingToolId(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{labels.deleteTitle}</AlertDialogTitle>
            <AlertDialogDescription>
              {labels.deleteDesc}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{labels.cancel}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => { if (deletingToolId !== null) deleteMutation.mutate(deletingToolId) }}
            >
              {labels.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ─── Flow Canvas ───────────────────────────────────────────────────────────────

interface FlowCanvasProps {
  flow: ConversationFlow
  selectedCard: FlowCard | null
  onSelectCard: (card: FlowCard | null) => void
  onConnectionCreated: (sourceId: number, targetId: number, label: string, keyслов: string) => void
  onNodeMoved: (cardId: number, x: number, y: number) => void
  onDeleteCard: (cardId: number) => void
  onDeleteConnection: (connectionId: number) => void
}

function FlowCanvas({
  flow,
  selectedCard,
  onSelectCard,
  onConnectionCreated,
  onNodeMoved,
  onDeleteCard,
  onDeleteConnection,
}: FlowCanvasProps) {
  const [showConnectionDialog, setShowConnectionDialog] = useState(false)
  const [pendingConnection, setPendingConnection] = useState<{ sourceId: number; targetId: number } | null>(null)
  const [conditionLabel, setConditionLabel] = useState('')
  const [conditionKeyслов, setConditionKeyслов] = useState('')

  const cards = flow.cards ?? []
  const connections = flow.connections ?? []

  const initialNodes: Node[] = useMemo(
    () =>
      cards.map((card) => ({
        id: String(card.id),
        type: 'card',
        position: { x: card.position_x, y: card.position_y },
        data: { card, isSelected: selectedCard?.id === card.id, onSelect: onSelectCard },
      })),
    [cards, selectedCard, onSelectCard]
  )

  const initialEdges: Edge[] = useMemo(
    () =>
      connections.map((conn) => ({
        id: String(conn.id),
        source: String(conn.source_card),
        target: String(conn.target_card),
        label: conn.condition_label || undefined,
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#6366f1', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1', width: 18, height: 18 },
        labelStyle: { fill: '#4f46e5', fontSize: 11, fontFamily: 'inherit' },
        labelBgStyle: { fill: '#eef2ff', fillOpacity: 1, rx: 4 },
      })),
    [connections]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // Keep nodes in sync when flow data changes
  useEffect(() => {
    setNodes(initialNodes)
  }, [initialNodes, setNodes])

  useEffect(() => {
    setEdges(initialEdges)
  }, [initialEdges, setEdges])

  const onConnect = useCallback(
    (params: Connection) => {
      const sourceId = Number(params.source)
      const targetId = Number(params.target)
      if (!sourceId || !targetId) return
      setPendingConnection({ sourceId, targetId })
      setConditionLabel('')
      setConditionKeyслов('')
      setShowConnectionDialog(true)
    },
    []
  )

  const handleConfirmConnection = () => {
    if (!pendingConnection) return
    onConnectionCreated(pendingConnection.sourceId, pendingConnection.targetId, conditionLabel, conditionKeyслов)
    setShowConnectionDialog(false)
    setPendingConnection(null)
  }

  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeMoved(Number(node.id), node.position.x, node.position.y)
    },
    [onNodeMoved]
  )

  const onEdgesDelete = useCallback(
    (deletedEdges: Edge[]) => {
      deletedEdges.forEach((e) => onDeleteConnection(Number(e.id)))
    },
    [onDeleteConnection]
  )

  const onNodesDelete = useCallback(
    (deletedNodes: Node[]) => {
      deletedNodes.forEach((n) => onDeleteCard(Number(n.id)))
    },
    [onDeleteCard]
  )

  return (
    <>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeDragStop={onNodeDragStop}
        onEdgesDelete={onEdgesDelete}
        onNodesDelete={onNodesDelete}
        onPaneClick={() => onSelectCard(null)}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.35}
        deleteKeyCode={['Backspace', 'Delete']}
        proOptions={{ hideAttribution: true }}
        className="bg-slate-50"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#cbd5e1" />
        <Controls className="[&>button]:bg-background [&>button]:border-border [&>button]:text-muted-foreground [&>button:hover]:bg-muted" />
        <MiniMap
          nodeColor={(n) => {
            const card = cards.find((c) => String(c.id) === n.id)
            if (!card) return '#94a3b8'
            return card.card_type === 'entry' ? '#10b981' : card.card_type === 'escalation' ? '#ef4444' : '#0ea5e9'
          }}
          maskColor="rgba(248,250,252,0.7)"
          className="bg-background border border-border rounded-lg"
        />
        <Panel position="top-left" className="text-xs text-muted-foreground/50 mt-1 ml-1">
          {cards.length} карт(ы) · {connections.length} связей · Перетаскивайте для перемещения · Клавиша Delete удаляет
        </Panel>
      </ReactFlow>

      <Dialog open={showConnectionDialog} onOpenChange={setShowConnectionDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Настройка перехода</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="mb-1.5 block">Название условия <span className="text-muted-foreground text-xs">(необязательно)</span></Label>
              <Input
                placeholder='напр. "Интересуется", "Нужно больше инфо"'
                value={conditionLabel}
                onChange={(e) => setConditionLabel(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">Отображается на линии связи</p>
            </div>
            <div>
              <Label className="mb-1.5 block">Ключевые слова-триггеры <span className="text-muted-foreground text-xs">(необязательно)</span></Label>
              <Input
                placeholder="да, хочу, подтверждаю, забронировать"
                value={conditionKeyслов}
                onChange={(e) => setConditionKeyслов(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">Ключевые слова через запятую, которые активируют этот путь</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConnectionDialog(false)}>Отмена</Button>
            <Button onClick={handleConfirmConnection}>Создать связь</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ─── Card Editor Panel ─────────────────────────────────────────────────────────

interface CardEditorProps {
  card: FlowCard
  onSave: (data: Partial<FlowCard>) => void
  onDelete: () => void
  onClose: () => void
  isSaving: boolean
}

function CardEditor({ card, onSave, onDelete, onClose, isSaving }: CardEditorProps) {
  const [title, setTitle] = useState(card.title)
  const [cardType, setCardType] = useState<FlowCard['card_type']>(card.card_type)
  const [template, setTemplate] = useState(card.message_template)
  const [playbookIds, setPlaybookIds] = useState<number[]>(card.playbooks ?? [])
  const [playbooksOpen, setPlaybooksOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { data: playbooks = [] } = useQuery<Playbook[]>({ queryKey: ['playbooks'], queryFn: fetchPlaybooks })

  useEffect(() => {
    setTitle(card.title)
    setCardType(card.card_type)
    setTemplate(card.message_template)
    setPlaybookIds(card.playbooks ?? [])
  }, [card.id])

  const togglePlaybook = (id: number) => {
    setPlaybookIds((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    )
  }

  const insertPlaceholder = (key: string) => {
    const el = textareaRef.current
    if (!el) {
      setTemplate((t) => t + key)
      return
    }
    const start = el.selectionStart
    const end = el.selectionEnd
    const newVal = template.slice(0, start) + key + template.slice(end)
    setTemplate(newVal)
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(start + key.length, start + key.length)
    })
  }

  const handleSave = () => {
    onSave({ title, card_type: cardType, message_template: template, playbooks: playbookIds })
  }

  return (
    <div className="flex flex-col h-full bg-background border-l border-border w-80 shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-sm font-semibold text-foreground">Редактировать карточку</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <XIcon className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <Label className="mb-1.5 block text-xs">Название карточки</Label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Название карточки" />
        </div>

        <div>
          <Label className="mb-1.5 block text-xs">Тип карточки</Label>
          <Select value={cardType} onValueChange={(v) => setCardType(v as FlowCard['card_type'])}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="entry">Вход — Первое сообщение лиду</SelectItem>
              <SelectItem value="normal">Сообщение — Следующий шаг</SelectItem>
              <SelectItem value="escalation">Эскалация — Передача человеку</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label className="mb-1.5 block text-xs">Шаблон сообщения</Label>
          <Textarea
            ref={textareaRef}
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            placeholder="Введите ваше сообщение... используйте {placeholders} для динамического контента"
            rows={7}
            className="text-sm resize-none font-mono leading-relaxed"
          />
        </div>

        <div>
          <Label className="mb-1.5 block text-xs">
            Контекст сценария
            <span className="text-muted-foreground font-normal ml-1">(необязательно)</span>
          </Label>
          <Popover open={playbooksOpen} onOpenChange={setPlaybooksOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="w-full flex items-center justify-between h-9 px-3 rounded-md border border-input bg-background text-sm text-left hover:bg-muted/40 transition-colors"
              >
                <span className={playbookIds.length === 0 ? 'text-muted-foreground' : 'text-foreground'}>
                  {playbookIds.length === 0
                    ? 'Нет сценариев'
                    : `Выбрано сценариев: ${playbookIds.length}`}
                </span>
                <ChevronDownIcon className="h-4 w-4 text-muted-foreground shrink-0" />
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-72 p-1" align="start">
              {playbooks.length === 0 ? (
                <p className="text-xs text-muted-foreground px-3 py-2">Нет доступных сценариев</p>
              ) : (
                playbooks.map((pb) => (
                  <div
                    key={pb.id}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-md hover:bg-muted cursor-pointer"
                    onClick={() => togglePlaybook(pb.id)}
                  >
                    <Checkbox
                      checked={playbookIds.includes(pb.id)}
                      onCheckedChange={() => togglePlaybook(pb.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                    <span className="text-sm">{pb.name}</span>
                  </div>
                ))
              )}
            </PopoverContent>
          </Popover>
          {playbookIds.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {playbookIds.map((id) => {
                const pb = playbooks.find((p) => p.id === id)
                return pb ? (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 text-[10px] bg-violet-50 text-violet-700 border border-violet-200 rounded px-1.5 py-0.5"
                  >
                    {pb.name}
                    <button type="button" onClick={() => togglePlaybook(id)}>
                      <XIcon className="h-2.5 w-2.5" />
                    </button>
                  </span>
                ) : null
              })}
            </div>
          )}
          <p className="text-[11px] text-muted-foreground mt-1.5 leading-snug">
            Когда AI обрабатывает сообщения на этой карточке, только выбранные сценарии добавляются в контекст.
          </p>
        </div>

        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <InfoIcon className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground font-medium">Переменные</span>
          </div>
          <div className="grid grid-cols-1 gap-1">
            {PLACEHOLDERS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => insertPlaceholder(p.key)}
                className="flex items-center gap-2 text-left px-2 py-1.5 rounded-md hover:bg-muted transition-colors group"
              >
                <code className="text-[11px] text-indigo-600 font-mono bg-indigo-50 px-1.5 py-0.5 rounded shrink-0">
                  {p.key}
                </code>
                <span className="text-[11px] text-muted-foreground group-hover:text-foreground transition-colors truncate">
                  {p.description}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="border-t border-border p-4 space-y-2">
        <Button className="w-full" onClick={handleSave} disabled={isSaving}>
          <SaveIcon className="h-4 w-4 mr-2" />
          {isSaving ? 'Сохранение…' : 'Сохранить карточку'}
        </Button>
        <Button
          variant="outline"
          className="w-full text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
          onClick={onDelete}
        >
          <Trash2Icon className="h-4 w-4 mr-2" />
          Удалить карточку
        </Button>
      </div>
    </div>
  )
}

// ─── Global Prompt Panel ────────────────────────────────────────────────────────

interface GlobalPromptPanelProps {
  selectedFlowId: number | null
  flowDetail: ConversationFlow | undefined
}

function GlobalPromptPanel({ selectedFlowId, flowDetail }: GlobalPromptPanelProps) {
  const qc = useQueryClient()
  const [prompt, setPrompt] = useState('')
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (flowDetail) {
      setPrompt(flowDetail.global_prompt ?? '')
      setDirty(false)
    }
  }, [flowDetail?.id, flowDetail?.global_prompt])

  const saveMutation = useMutation({
    mutationFn: () => updateFlow(selectedFlowId!, { global_prompt: prompt }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flow', selectedFlowId] })
      qc.invalidateQueries({ queryKey: ['flows'] })
      setDirty(false)
      toast.success('Глобальный промпт сохранен')
    },
  })

  if (!selectedFlowId || !flowDetail) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <FileTextIcon className="h-10 w-10 text-muted-foreground/20 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Выберите или создайте поток, чтобы отредактировать его глобальный промпт</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-xl mx-auto space-y-5">
        <div>
          <h2 className="text-base font-semibold text-foreground">Глобальный промпт</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Эти инструкции добавляются в каждый шаг этого потока, когда активен режим ведения диалога по сценарию.
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">{flowDetail.name}</span>
            {flowDetail.is_active && (
              <span className="text-[10px] font-medium text-emerald-600 bg-emerald-50 border border-emerald-200 rounded px-1.5 py-0.5">Активен</span>
            )}
          </div>
          <Textarea
            value={prompt}
            onChange={(e) => { setPrompt(e.target.value); setDirty(true) }}
            placeholder="Напишите правила, которые применяются к каждому шагу в этом потоке — например, 'Всегда отвечать на русском', 'Никогда не упоминать цены, если не спросят'..."
            rows={10}
            className="text-sm resize-y font-mono leading-relaxed"
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">{prompt.length} символов</span>
            <Button
              size="sm"
              onClick={() => saveMutation.mutate()}
              disabled={!dirty || saveMutation.isPending}
            >
              <SaveIcon className="h-3.5 w-3.5 mr-1.5" />
              {saveMutation.isPending ? 'Сохранение…' : 'Сохранить'}
            </Button>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Примеры: <span className="text-foreground/70">"Всегда отвечать на русском."</span> · <span className="text-foreground/70">"Никогда не упоминать цены конкурентов."</span> · <span className="text-foreground/70">"Если гость грубит, оставайтесь спокойными и профессиональными."</span>
        </p>
      </div>
    </div>
  )
}

// ─── AI Model Panel ─────────────────────────────────────────────────────────────

const DEFAULTS: Pick<AIModelConfig, 'temperature' | 'max_tokens'> = { temperature: 0.7, max_tokens: 500 }

function AIModelPanel() {
  const qc = useQueryClient()
  const { data: config } = useQuery({ queryKey: ['ai-model-config'], queryFn: fetchAIModelConfig })

  const [temperature, setTemperature] = useState<number>(DEFAULTS.temperature)
  const [maxTokens, setMaxTokens] = useState<number>(DEFAULTS.max_tokens)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (config) {
      setTemperature(config.temperature)
      setMaxTokens(config.max_tokens)
      setDirty(false)
    }
  }, [config])

  const saveMutation = useMutation({
    mutationFn: () => updateAIModelConfig({ temperature, max_tokens: maxTokens }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-model-config'] })
      setDirty(false)
      toast.success('Настройки AI-модели сохранены')
    },
  })

  const handleReset = () => {
    setTemperature(DEFAULTS.temperature)
    setMaxTokens(DEFAULTS.max_tokens)
    setDirty(true)
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-xl mx-auto space-y-6">
        <div>
          <h2 className="text-base font-semibold text-foreground">Настройки AI-модели</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Эти настройки применяются к AI, который общается с гостями по всем каналам.
          </p>
        </div>

        {/* Temperature card */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">Температура</span>
            <span className="text-sm font-mono font-semibold text-foreground tabular-nums w-8 text-right">
              {temperature.toFixed(1)}
            </span>
          </div>
          <div className="space-y-2">
            <Slider
              min={0}
              max={1}
              step={0.1}
              value={[temperature]}
              onValueChange={([v]) => { setTemperature(v); setDirty(true) }}
            />
            <div className="flex justify-between">
              <span className="text-[10px] text-muted-foreground">Точный</span>
              <span className="text-[10px] text-muted-foreground">Творческий</span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Контролирует, насколько креативно и разнообразно звучит AI. Более низкие значения делают ответы более предсказуемыми и точными (хорошо для точности). Более высокие значения делают ответы более естественными и человечными. <span className="text-foreground/60">Рекомендуется: 0.7</span>
          </p>
        </div>

        {/* Max tokens card */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-foreground">Макс. длина ответа</span>
              <span className="text-xs text-muted-foreground ml-2">
                {maxTokens} токенов ≈ {Math.round(maxTokens * 0.75)} слов
              </span>
            </div>
            <span className="text-sm font-mono font-semibold text-foreground tabular-nums">
              {maxTokens}
            </span>
          </div>
          <div className="space-y-2">
            <Slider
              min={100}
              max={1000}
              step={50}
              value={[maxTokens]}
              onValueChange={([v]) => { setMaxTokens(v); setDirty(true) }}
            />
            <div className="flex justify-between">
              <span className="text-[10px] text-muted-foreground">Короткие</span>
              <span className="text-[10px] text-muted-foreground">Подробные</span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Контролирует максимальную длину ответов AI. Приблизительно 1 токен ≈ 1 слово. Короткие ответы кажутся более быстрыми и естественными для чата. <span className="text-foreground/60">Рекомендуется: 400–500 для бронирования отелей.</span>
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            onClick={handleReset}
            className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
          >
            Сбросить настройки
          </button>
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={!dirty || saveMutation.isPending}
            size="sm"
          >
            <SaveIcon className="h-3.5 w-3.5 mr-1.5" />
            {saveMutation.isPending ? 'Сохранение…' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Transfer Panel ─────────────────────────────────────────────────────────────

function TransferPanel() {
  const qc = useQueryClient()
  const { data: config } = useQuery({ queryKey: ['transfer-config'], queryFn: fetchTransferConfig })

  const [channel, setChannel] = useState<ManagerTransferConfig['channel']>('telegram')
  const [recipientId, setRecipientId] = useState('')
  const [managerName, setManagerName] = useState('')
  const [notificationTemplate, setNotificationTemplate] = useState('')
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (config) {
      setChannel(config.channel)
      setRecipientId(config.recipient_id)
      setManagerName(config.manager_name)
      setNotificationTemplate(config.notification_template)
      setDirty(false)
    }
  }, [config])

  const saveMutation = useMutation({
    mutationFn: () => updateTransferConfig({ channel, recipient_id: recipientId, manager_name: managerName, notification_template: notificationTemplate }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transfer-config'] })
      setDirty(false)
      toast.success('Настройки передачи сохранены')
    },
  })

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-xl mx-auto space-y-6">
        <div>
          <h2 className="text-base font-semibold text-foreground">Уведомление менеджера</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Когда AI нужно передать бронирование или эскалировать диалог, он уведомит этого контакта.
          </p>
        </div>

        {/* Channel */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <span className="text-sm font-medium text-foreground">Канал связи</span>
          <div className="flex gap-3 mt-3">
            {(['telegram', 'whatsapp'] as const).map((ch) => (
              <button
                key={ch}
                onClick={() => { setChannel(ch); setDirty(true) }}
                className={`flex-1 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                  channel === ch
                    ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                    : 'border-border bg-background text-muted-foreground hover:text-foreground hover:border-border/80'
                }`}
              >
                {ch === 'telegram' ? '✈️ Telegram' : '📱 WhatsApp'}
              </button>
            ))}
          </div>
        </div>

        {/* Recipient */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">
              {channel === 'telegram' ? 'Telegram Chat ID (пользователь или группа)' : 'Номер WhatsApp'}
            </label>
            <input
              type="text"
              value={recipientId}
              onChange={(e) => { setRecipientId(e.target.value); setDirty(true) }}
              placeholder={channel === 'telegram' ? 'напр. -1001234567890 (группа) или 123456789 (пользователь)' : 'напр. +996700123456'}
              className="w-full h-9 px-3 rounded-md border border-input bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {channel === 'telegram' ? (
              <div className="text-[11px] text-muted-foreground mt-1.5 space-y-1">
                <p><span className="font-medium">Групповой чат:</span> Добавьте бота в свою группу, затем перешлите любое сообщение из этой группы боту <span className="font-mono">@getidsbot</span> — он ответит числовым ID группы (отрицательное число, начинающееся с <span className="font-mono">-100</span>).</p>
                <p><span className="font-medium">Личный чат:</span> Откройте Telegram, отправьте сообщение боту <span className="font-mono">@userinfobot</span>, и он ответит вашим личным числовым ID.</p>
                <p>Сообщения отправляются через вашего настроенного Telegram-бота (Настройки → Интеграции → Telegram).</p>
              </div>
            ) : (
              <p className="text-[11px] text-muted-foreground mt-1.5">Укажите код страны.</p>
            )}
          </div>

          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">Имя менеджера</label>
            <input
              type="text"
              value={managerName}
              onChange={(e) => { setManagerName(e.target.value); setDirty(true) }}
              placeholder="напр. Максим"
              className="w-full h-9 px-3 rounded-md border border-input bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="text-[11px] text-muted-foreground mt-1.5">
              Используется в сообщении-подтверждении, отправляемом гостю.
            </p>
          </div>
        </div>

        {/* Шаблон уведомления */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="text-sm font-medium text-foreground">Шаблон уведомления</span>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Настройте сообщение, отправляемое менеджеру. Оставьте пустым, чтобы использовать формат по умолчанию.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setNotificationTemplate(
                  '📋 Новый запрос\nПричина: {reason}\n\n👤 Гость: {guest_name}\n📞 Телефон: {guest_phone}\n🔗 Контакт: {contact_id}\n💬 Канал: {platform}\n\n🗓 Детали бронирования:\n  Заезд: {checkin_date}\n  Выезд: {checkout_date}\n  Ночей: {nights}\n  Гостей: {guest_count}\n  Номер: {room_description}\n  Питание: {meal_plan}\n  Итого: {total_price}\n\n📝 Примечания: {notes}'
                )
                setDirty(true)
              }}
              className="shrink-0 text-[11px] text-indigo-600 hover:text-indigo-700 hover:underline"
            >
              Вставить пример
            </button>
          </div>
          <textarea
            value={notificationTemplate}
            onChange={(e) => { setNotificationTemplate(e.target.value); setDirty(true) }}
            placeholder="Оставьте пустым, чтобы использовать формат сообщения по умолчанию."
            rows={9}
            className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
          />
          <div className="rounded-md bg-muted/50 border border-border px-3 py-2.5">
            <p className="text-[11px] font-medium text-foreground mb-1.5">Доступные переменные</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {[
                ['{reason}', 'Причина передачи'],
                ['{guest_name}', 'Имя гостя'],
                ['{guest_phone}', 'Телефон гостя'],
                ['{guest_email}', 'Email гостя'],
                ['{platform}', 'Канал (Telegram/WhatsApp)'],
                ['{contact_id}', 'ID чата/телефона гостя'],
                ['{telegram_handle}', 'Ник Telegram @handle'],
                ['{instagram_handle}', 'Ник Instagram @handle'],
                ['{checkin_date}', 'Дата заезда'],
                ['{checkout_date}', 'Дата выезда'],
                ['{nights}', 'Количество ночей'],
                ['{guest_count}', 'Количество гостей'],
                ['{room_description}', 'Название номера'],
                ['{meal_plan}', 'Питание'],
                ['{price_per_night}', 'Цена за ночь'],
                ['{total_price}', 'Итоговая стоимость'],
                ['{notes}', 'Дополнительные примечания'],
              ].map(([variable, desc]) => (
                <div key={variable} className="flex items-baseline gap-1.5">
                  <code className="text-[10px] font-mono text-indigo-600 shrink-0">{variable}</code>
                  <span className="text-[10px] text-muted-foreground truncate">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={!dirty || saveMutation.isPending}
            size="sm"
          >
            <SaveIcon className="h-3.5 w-3.5 mr-1.5" />
            {saveMutation.isPending ? 'Сохранение…' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

// ─── Agent Canvas ─────────────────────────────────────────────────────────────

const AGENT_INTENTS = ['booking', 'faq', 'undecided', 'greeting', 'off_topic']

interface AgentNodeData {
  label: string
  subtitle: string
  playbookNames: string[]
  onEdit?: () => void
  onGoToFlows?: () => void
  [key: string]: unknown
}

function IntentRouterNode() {
  return (
    <div className="w-56 rounded-2xl border-2 p-4 shadow-md select-none bg-white cursor-pointer hover:brightness-95 transition-all" style={{ borderColor: '#6366f1' }}>
      <Handle type="source" position={Position.Bottom} style={{ background: '#6366f1', width: 10, height: 10 }} />
      <div className="text-indigo-900 font-bold text-sm mb-0.5">⚡ Маршрутизатор намерений</div>
      <div className="text-indigo-400 text-[11px] mb-3">Автоматически — классифицирует каждое сообщение</div>
      <div className="flex flex-wrap gap-1">
        {AGENT_INTENTS.map((intent) => (
          <span key={intent} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-200">
            {intent}
          </span>
        ))}
      </div>
    </div>
  )
}

function BookingAgentNode({ data }: { data: AgentNodeData }) {
  return (
    <div
      className="w-52 rounded-2xl border-2 p-3 shadow-lg select-none cursor-pointer hover:brightness-110 transition-all"
      style={{ background: '#eff6ff', borderColor: '#3b82f6' }}
      onDoubleClick={data.onGoToFlows}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#3b82f6', width: 10, height: 10 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#3b82f6', width: 8, height: 8, opacity: 0 }} />
      <div className="text-blue-900 font-bold text-sm mb-0.5">🗓 {data.label}</div>
      <div className="text-blue-500 text-[11px] mb-2">{data.subtitle}</div>
      {data.playbookNames.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {data.playbookNames.map((n) => (
            <span key={n} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 border border-blue-200">{n}</span>
          ))}
        </div>
      )}
      <button
        className="text-[11px] text-blue-600 hover:text-blue-800 flex items-center gap-1 mt-1"
        onClick={(e) => { e.stopPropagation(); data.onGoToFlows?.() }}
      >
        <ArrowRightIcon className="h-3 w-3" /> Редактировать поток
      </button>
    </div>
  )
}

function CSAgentNode({ data }: { data: AgentNodeData }) {
  return (
    <div
      className="w-52 rounded-2xl border-2 p-3 shadow-lg select-none cursor-pointer hover:brightness-95 transition-all"
      style={{ background: '#f5f3ff', borderColor: '#8b5cf6' }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#8b5cf6', width: 10, height: 10 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#8b5cf6', width: 8, height: 8, opacity: 0 }} />
      <div className="text-violet-900 font-bold text-sm mb-0.5">💬 {data.label}</div>
      <div className="text-violet-500 text-[11px] mb-2">{data.subtitle}</div>
      {data.playbookNames.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {data.playbookNames.map((n) => (
            <span key={n} className="text-[10px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 border border-violet-200">{n}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function ConsultantAgentNode({ data }: { data: AgentNodeData }) {
  return (
    <div
      className="w-52 rounded-2xl border-2 p-3 shadow-lg select-none cursor-pointer hover:brightness-95 transition-all"
      style={{ background: '#ecfdf5', borderColor: '#10b981' }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#10b981', width: 10, height: 10 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#10b981', width: 8, height: 8, opacity: 0 }} />
      <div className="text-emerald-900 font-bold text-sm mb-0.5">🧠 {data.label}</div>
      <div className="text-emerald-600 text-[11px] mb-2">{data.subtitle}</div>
      {data.playbookNames.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {data.playbookNames.map((n) => (
            <span key={n} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 border border-emerald-200">{n}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function SharedContextNode() {
  return (
    <div className="w-52 rounded-2xl border-2 p-3 shadow-md select-none" style={{ background: '#fffbeb', borderColor: '#f59e0b' }}>
      <Handle type="target" position={Position.Top} style={{ background: '#f59e0b', width: 10, height: 10 }} />
      <div className="text-amber-900 font-bold text-sm mb-0.5">📦 Общий контекст</div>
      <div className="text-amber-600 text-[11px] mb-2">Состояние бронирования, видимое всем агентам</div>
      <div className="space-y-0.5">
        {['current_agent', 'booking_step', 'room_type', 'checkin_date', 'meal_plan'].map((field) => (
          <div key={field} className="text-[10px] text-amber-700/80 font-mono">{field}</div>
        ))}
      </div>
    </div>
  )
}

const AGENT_NODE_TYPES = {
  intentRouter: IntentRouterNode,
  bookingAgent: BookingAgentNode,
  csAgent: CSAgentNode,
  consultantAgent: ConsultantAgentNode,
  sharedContext: SharedContextNode,
}

const AVAILABLE_TOOLS = ['get_room_options', 'get_family_room', 'get_room_images', 'transfer_to_manager']

const AGENT_ICONS: Record<string, string> = { router: '⚡', cs: '💬', consultant: '🧠', booking: '🗓' }

interface AgentEditorPanelProps {
  agent: AgentConfig
  playbooks: Playbook[]
  onSave: (data: Partial<Pick<AgentConfig, 'system_prompt' | 'playbooks' | 'tools'>>) => void
  onClose: () => void
  isSaving: boolean
}

function AgentEditorPanel({ agent, playbooks, onSave, onClose, isSaving }: AgentEditorPanelProps) {
  const [prompt, setPrompt] = useState(agent.system_prompt)
  const [selectedPlaybooks, setSelectedPlaybooks] = useState<number[]>(agent.playbooks)
  const [selectedTools, setSelectedTools] = useState<string[]>(agent.tools)

  // Reset when agent changes
  useEffect(() => {
    setPrompt(agent.system_prompt)
    setSelectedPlaybooks(agent.playbooks)
    setSelectedTools(agent.tools)
  }, [agent.id])

  function togglePlaybook(id: number) {
    setSelectedPlaybooks((prev) => prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id])
  }

  function toggleTool(name: string) {
    setSelectedTools((prev) => prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name])
  }

  return (
    <div className="w-80 shrink-0 flex flex-col border-l border-border bg-muted/30 overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">{AGENT_ICONS[agent.name] ?? '🤖'}</span>
          <span className="text-sm font-semibold text-foreground">{agent.display_name}</span>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
          <XIcon className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 px-4 py-3 space-y-4 overflow-y-auto">
        {/* System Prompt */}
        <div>
          <Label className="text-xs font-semibold mb-1.5 block">Системный промпт</Label>
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={10}
            className="text-xs font-mono resize-none"
            placeholder="Опишите роль и поведение агента..."
          />
        </div>

        {/* Playbooks */}
        {playbooks.length > 0 && (
          <div>
            <Label className="text-xs font-semibold mb-1.5 block">Сценарии</Label>
            <div className="space-y-1.5">
              {playbooks.map((pb) => (
                <label key={pb.id} className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={selectedPlaybooks.includes(pb.id)}
                    onCheckedChange={() => togglePlaybook(pb.id)}
                  />
                  <span className="text-xs text-foreground">{pb.name}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Tools */}
        <div>
          <Label className="text-xs font-semibold mb-1.5 block">Инструменты</Label>
          <div className="space-y-1.5">
            {AVAILABLE_TOOLS.map((toolName) => (
              <label key={toolName} className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={selectedTools.includes(toolName)}
                  onCheckedChange={() => toggleTool(toolName)}
                />
                <span className="text-xs font-mono text-foreground">{toolName}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-border shrink-0">
        <Button
          className="w-full h-8 text-xs"
          onClick={() => onSave({ system_prompt: prompt, playbooks: selectedPlaybooks, tools: selectedTools })}
          disabled={isSaving}
        >
          <SaveIcon className="h-3.5 w-3.5 mr-1.5" />
          {isSaving ? 'Сохранение…' : 'Сохранить изменения'}
        </Button>
      </div>
    </div>
  )
}

interface AgentsPanelProps {
  onNavigateToFlows: () => void
}

function AgentsPanel({ onNavigateToFlows }: AgentsPanelProps) {
  const qc = useQueryClient()
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: fetchAgents })
  const { data: playbooks = [] } = useQuery({ queryKey: ['playbooks'], queryFn: fetchPlaybooks })
  const [activeAgentName, setActiveAgentName] = useState<'router' | 'cs' | 'consultant' | 'booking'>('cs')
  const [panelOpen, setPanelOpen] = useState(false)

  const EDITABLE_NODES = new Set(['router', 'cs', 'consultant', 'booking'])

  const handleNodeClick = useCallback((_: unknown, node: { id: string }) => {
    if (EDITABLE_NODES.has(node.id)) {
      setActiveAgentName(node.id as 'router' | 'cs' | 'consultant' | 'booking')
      setPanelOpen(true)
    }
  }, [])

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateAgent>[1] }) => updateAgent(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agents'] })
      toast.success('Агент сохранен')
    },
    onError: () => toast.error('Не удалось сохранить агента'),
  })

  const getAgent = (name: string) => agents.find((a) => a.name === name)

  const buildNodes = useCallback(() => {
    const booking = getAgent('booking')
    const cs = getAgent('cs')
    const consultant = getAgent('consultant')

    return [
      {
        id: 'router',
        type: 'intentRouter',
        position: { x: 230, y: 30 },
        data: {},
        draggable: false,
      },
      {
        id: 'booking',
        type: 'bookingAgent',
        position: { x: 0, y: 280 },
        data: {
          label: booking?.display_name ?? 'Агент бронирования',
          subtitle: 'Следует вашим карточкам потока',
          playbookNames: booking?.playbook_names ?? [],
          onGoToFlows: onNavigateToFlows,
        } as AgentNodeData,
        draggable: false,
      },
      {
        id: 'cs',
        type: 'csAgent',
        position: { x: 238, y: 280 },
        data: {
          label: cs?.display_name ?? 'Агент поддержки клиентов',
          subtitle: 'Обрабатывает FAQ и общие вопросы',
          playbookNames: cs?.playbook_names ?? [],
        } as AgentNodeData,
        draggable: false,
      },
      {
        id: 'consultant',
        type: 'consultantAgent',
        position: { x: 476, y: 280 },
        data: {
          label: consultant?.display_name ?? 'Агент-консультант',
          subtitle: 'Помогает сомневающимся гостям выбрать',
          playbookNames: consultant?.playbook_names ?? [],
        } as AgentNodeData,
        draggable: false,
      },
      {
        id: 'shared',
        type: 'sharedContext',
        position: { x: 238, y: 510 },
        data: {},
        draggable: false,
      },
    ]
  }, [agents, onNavigateToFlows])

  const buildEdges = useCallback(() => [
    { id: 'r-b', source: 'router', target: 'booking', animated: true, style: { stroke: '#60a5fa' }, label: 'бронирование / приветствие' },
    { id: 'r-cs', source: 'router', target: 'cs', animated: true, style: { stroke: '#a78bfa' }, label: 'faq / оффтоп' },
    { id: 'r-con', source: 'router', target: 'consultant', animated: true, style: { stroke: '#34d399' }, label: 'не определился' },
    { id: 'cs-b', source: 'cs', target: 'booking', style: { stroke: '#a78bfa', strokeDasharray: '5,5' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#a78bfa' }, label: 'возврат' },
    { id: 'con-b', source: 'consultant', target: 'booking', style: { stroke: '#34d399', strokeDasharray: '5,5' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#34d399' }, label: 'возврат' },
    { id: 'b-ctx', source: 'booking', target: 'shared', style: { stroke: '#fbbf24', strokeDasharray: '3,3' }, label: '' },
    { id: 'cs-ctx', source: 'cs', target: 'shared', style: { stroke: '#fbbf24', strokeDasharray: '3,3' }, label: '' },
    { id: 'con-ctx', source: 'consultant', target: 'shared', style: { stroke: '#fbbf24', strokeDasharray: '3,3' }, label: '' },
  ], [])

  const nodes = useMemo(() => buildNodes(), [buildNodes])
  const edges = useMemo(() => buildEdges(), [buildEdges])
  const onNodesChange = useCallback(() => {}, [])
  const onEdgesChange = useCallback(() => {}, [])

  return (
    <div className="flex flex-1 min-w-0 min-h-0 bg-slate-50">
      {/* Canvas */}
      <div className="flex-1 min-w-0">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          nodeTypes={AGENT_NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.5}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} color="#cbd5e1" gap={24} size={1} />
          <Controls showInteractive={false} className="[&>button]:bg-background [&>button]:border-border [&>button]:text-muted-foreground [&>button:hover]:bg-muted" />
          <Panel position="top-left" className="m-3">
            <div className="bg-background border border-border rounded-xl px-3 py-2 shadow-sm">
              <div className="text-foreground text-xs font-semibold">Мультиагентная архитектура</div>
              <div className="text-muted-foreground text-[11px]">Нажмите на узел для редактирования</div>
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {/* Editor panel */}
      {panelOpen && (() => {
        const activeAgent = agents.find((a) => a.name === activeAgentName) ?? null
        return activeAgent ? (
          <AgentEditorPanel
            agent={activeAgent}
            playbooks={playbooks}
            onSave={(data) => updateMutation.mutate({ id: activeAgent.id, data })}
            onClose={() => setPanelOpen(false)}
            isSaving={updateMutation.isPending}
          />
        ) : null
      })()}
    </div>
  )
}

function FlowsPage() {
  const { user } = useAuth()
  if (!canManageWorkspace(user)) {
    return <Navigate to="/dashboard" />
  }
  return <FlowsPageContent />
}

function FlowsPageContent() {
  const qc = useQueryClient()
  const { t } = useLanguage()
  const [leftTab, setLeftTab] = useState<'flows' | 'tools' | 'ai-model' | 'transfer' | 'global-prompt' | 'agents'>('flows')
  const [selectedFlowId, setSelectedFlowId] = useState<number | null>(null)
  const [selectedCard, setSelectedCard] = useState<FlowCard | null>(null)
  const [showNewFlowDialog, setShowNewFlowDialog] = useState(false)
  const [showDeleteFlowDialog, setShowDeleteFlowDialog] = useState(false)
  const [newFlowName, setNewFlowName] = useState('')
  const [newFlowDesc, setNewFlowDesc] = useState('')

  const { data: flows = [] } = useQuery({
    queryKey: ['flows'],
    queryFn: fetchFlows,
  })

  const { data: flowDetail } = useQuery({
    queryKey: ['flow', selectedFlowId],
    queryFn: () => fetchFlow(selectedFlowId!),
    enabled: selectedFlowId !== null,
  })


  // Auto-select first flow
  useEffect(() => {
    if (flows.length > 0 && selectedFlowId === null) {
      setSelectedFlowId(flows[0].id)
    }
  }, [flows, selectedFlowId])

  const createFlowMutation = useMutation({
    mutationFn: (data: { name: string; description: string }) => createFlow(data),
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: ['flows'] })
      setSelectedFlowId(flow.id)
      setShowNewFlowDialog(false)
      setNewFlowName('')
      setNewFlowDesc('')
      toast.success('Поток создан')
    },
  })

  const deleteFlowMutation = useMutation({
    mutationFn: deleteFlow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flows'] })
      setSelectedFlowId(flows.find((f) => f.id !== selectedFlowId)?.id ?? null)
      toast.success('Поток удален')
    },
  })

  const activateFlowMutation = useMutation({
    mutationFn: activateFlow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flows'] })
      toast.success('Поток активирован')
    },
  })

  const addCardMutation = useMutation({
    mutationFn: ({ flowId, data }: { flowId: number; data: Partial<FlowCard> }) =>
      createFlowCard(flowId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flow', selectedFlowId] })
    },
  })

  const updateCardMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<FlowCard> }) =>
      updateFlowCard(id, data),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ['flow', selectedFlowId] })
      setSelectedCard(updated)
      toast.success('Карточка сохранена')
    },
  })

  const deleteCardMutation = useMutation({
    mutationFn: deleteFlowCard,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flow', selectedFlowId] })
      setSelectedCard(null)
      toast.success('Карточка удалена')
    },
  })

  const createConnectionMutation = useMutation({
    mutationFn: ({ flowId, data }: { flowId: number; data: Parameters<typeof createFlowConnection>[1] }) =>
      createFlowConnection(flowId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flow', selectedFlowId] })
    },
  })

  const deleteConnectionMutation = useMutation({
    mutationFn: deleteFlowConnection,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flow', selectedFlowId] })
    },
  })

  const handleAddCard = () => {
    if (!selectedFlowId) return
    const cards = flowDetail?.cards ?? []
    const hasEntry = cards.some((c) => c.card_type === 'entry')
    addCardMutation.mutate({
      flowId: selectedFlowId,
      data: {
        card_type: hasEntry ? 'normal' : 'entry',
        title: hasEntry ? 'Новый шаг' : 'Приветствие',
        message_template: '',
        position_x: 100 + cards.length * 60,
        position_y: 100 + cards.length * 120,
      },
    })
  }

  const handleNodeMoved = useCallback(
    (cardId: number, x: number, y: number) => {
      updateFlowCard(cardId, { position_x: x, position_y: y })
    },
    []
  )

  const handleConnectionCreated = useCallback(
    (sourceId: number, targetId: number, label: string, keyслов: string) => {
      if (!selectedFlowId) return
      createConnectionMutation.mutate({
        flowId: selectedFlowId,
        data: { source_card: sourceId, target_card: targetId, condition_label: label, condition_keywords: keyслов },
      })
    },
    [selectedFlowId, createConnectionMutation]
  )

  return (
    <div className="flex h-screen flex-col min-w-0 bg-background text-foreground overflow-hidden">
      {/* ── Page Header + Tab Bar ── */}
      <div className="shrink-0 border-b border-border px-4 lg:px-6 pt-5 pb-0">
        <Tabs value={leftTab} onValueChange={(v) => setLeftTab(v as typeof leftTab)}>
          <TabsList className="h-auto bg-transparent p-0 gap-1">
            <TabsTrigger value="flows" className="gap-1.5 data-[state=active]:shadow-sm">
              <GitBranchIcon className="h-3.5 w-3.5" />
              Потоки
            </TabsTrigger>
            <TabsTrigger value="tools" className="gap-1.5 data-[state=active]:shadow-sm">
              <WrenchIcon className="h-3.5 w-3.5" />
              Инструменты
            </TabsTrigger>
            <TabsTrigger value="ai-model" className="gap-1.5 data-[state=active]:shadow-sm">
              <SparklesIcon className="h-3.5 w-3.5" />
              AI-модель
            </TabsTrigger>
            <TabsTrigger value="transfer" className="gap-1.5 data-[state=active]:shadow-sm">
              <ArrowRightIcon className="h-3.5 w-3.5" />
              Передача
            </TabsTrigger>
            <TabsTrigger value="global-prompt" className="gap-1.5 data-[state=active]:shadow-sm">
              <FileTextIcon className="h-3.5 w-3.5" />
              Промпт
            </TabsTrigger>
            <TabsTrigger value="agents" className="gap-1.5 data-[state=active]:shadow-sm">
              <BotIcon className="h-3.5 w-3.5" />
              Агенты
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* ── Content Area ── */}
      <div className="flex flex-1 min-h-0 min-w-0 overflow-hidden">

        {/* Flows tab */}
        {leftTab === 'flows' && (
          <>
            {/* Flow list sidebar */}
            <div className="w-56 shrink-0 flex flex-col border-r border-border bg-muted/20 overflow-hidden">
              <div className="flex-1 overflow-y-auto px-3 pt-3 space-y-1">
                {flows.map((flow) => (
                  <div
                    key={flow.id}
                    onClick={() => setSelectedFlowId(flow.id)}
                    className={`group relative flex flex-col px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
                      selectedFlowId === flow.id
                        ? 'bg-indigo-50 border border-indigo-200'
                        : 'hover:bg-muted/60 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {flow.is_active && (
                        <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
                      )}
                      <span className="text-xs font-medium text-foreground truncate flex-1">{flow.name}</span>
                      <span className="text-[10px] text-muted-foreground shrink-0">{flow.card_count}c</span>
                    </div>
                    {flow.is_active && (
                      <span className="text-[10px] text-emerald-600 mt-0.5 ml-3.5">{t('flows.active')}</span>
                    )}
                  </div>
                ))}
                {flows.length === 0 && (
                  <p className="text-xs text-muted-foreground/50 text-center py-6">Потоков пока нет</p>
                )}
              </div>
              <div className="p-3 border-t border-border">
                <Button
                  variant="outline"
                  className="w-full text-xs hover:border-indigo-400/60 hover:text-indigo-600"
                  size="sm"
                  onClick={() => setShowNewFlowDialog(true)}
                >
                  <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
                  Новый поток
                </Button>
              </div>
            </div>

            {/* Canvas */}
            <div className="flex flex-col flex-1 min-w-0">
              {flowDetail ? (
                <>
                  <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border bg-muted/30 shrink-0">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h2 className="text-sm font-semibold text-foreground truncate">{flowDetail.name}</h2>
                        {flowDetail.is_active && (
                          <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300 text-[10px] h-4 px-1.5">
                            <CheckCircle2Icon className="h-2.5 w-2.5 mr-1" />
                            Активен
                          </Badge>
                        )}
                      </div>
                      {flowDetail.description && (
                        <p className="text-[11px] text-muted-foreground truncate">{flowDetail.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs"
                        onClick={handleAddCard}
                        disabled={addCardMutation.isPending}
                      >
                        <PlusIcon className="h-3.5 w-3.5 mr-1" />
                        Добавить шаг
                      </Button>
                      {!flowDetail.is_active && (
                        <Button
                          size="sm"
                          className="h-7 text-xs bg-emerald-700 hover:bg-emerald-600"
                          onClick={() => activateFlowMutation.mutate(flowDetail.id)}
                          disabled={activateFlowMutation.isPending}
                        >
                          <PlayIcon className="h-3.5 w-3.5 mr-1" />
                          Активировать
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400"
                        onClick={() => setShowDeleteFlowDialog(true)}
                      >
                        <Trash2Icon className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex flex-1 min-h-0 min-w-0 overflow-hidden">
                    <div className="flex-1 min-w-0 overflow-hidden">
                      <FlowCanvas
                        flow={flowDetail}
                        selectedCard={selectedCard}
                        onSelectCard={setSelectedCard}
                        onConnectionCreated={handleConnectionCreated}
                        onNodeMoved={handleNodeMoved}
                        onDeleteCard={(id) => deleteCardMutation.mutate(id)}
                        onDeleteConnection={(id) => deleteConnectionMutation.mutate(id)}
                      />
                    </div>
                    {selectedCard && (
                      <CardEditor
                        card={selectedCard}
                        onSave={(data) => updateCardMutation.mutate({ id: selectedCard.id, data })}
                        onDelete={() => deleteCardMutation.mutate(selectedCard.id)}
                        onClose={() => setSelectedCard(null)}
                        isSaving={updateCardMutation.isPending}
                      />
                    )}
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center">
                    <SparklesIcon className="h-12 w-12 text-indigo-400/30 mx-auto mb-4" />
                    <h3 className="text-sm font-medium text-muted-foreground mb-1">
                      {flows.length === 0 ? 'Потоков пока нет' : 'Выберите поток'}
                    </h3>
                    <p className="text-xs text-muted-foreground/60 mb-4">
                      {flows.length === 0
                        ? 'Создайте диалоговый поток для определения последовательности работы AI'
                        : 'Выберите поток в левой панели'}
                    </p>
                    {flows.length === 0 && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-indigo-300 text-indigo-600 hover:bg-indigo-50"
                        onClick={() => setShowNewFlowDialog(true)}
                      >
                        <PlusIcon className="h-4 w-4 mr-1.5" />
                        Создать первый поток
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {leftTab === 'tools' && <ToolsPanel />}
        {leftTab === 'ai-model' && <AIModelPanel />}
        {leftTab === 'transfer' && <TransferPanel />}
        {leftTab === 'global-prompt' && <GlobalPromptPanel selectedFlowId={selectedFlowId} flowDetail={flowDetail} />}
        {leftTab === 'agents' && <AgentsPanel onNavigateToFlows={() => setLeftTab('flows')} />}
      </div>

      {/* ── Delete Flow Confirmation ── */}
      <AlertDialog open={showDeleteFlowDialog} onOpenChange={setShowDeleteFlowDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить поток?</AlertDialogTitle>
            <AlertDialogDescription>
              Это навсегда удалит поток &quot;{flowDetail?.name}&quot;, а также все его карточки и переходы. Это действие нельзя отменить.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => {
                if (flowDetail) deleteFlowMutation.mutate(flowDetail.id)
                setShowDeleteFlowDialog(false)
              }}
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── New Flow Dialog ── */}
      <Dialog open={showNewFlowDialog} onOpenChange={setShowNewFlowDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Создать новый поток</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="mb-1.5 block">Название потока</Label>
              <Input
                placeholder="напр. Индивидуальное бронирование отеля"
                value={newFlowName}
                onChange={(e) => setNewFlowName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newFlowName.trim()) {
                    createFlowMutation.mutate({ name: newFlowName.trim(), description: newFlowDesc.trim() })
                  }
                }}
              />
            </div>
            <div>
              <Label className="mb-1.5 block">Описание <span className="text-muted-foreground text-xs">(необязательно)</span></Label>
              <Textarea
                placeholder="Опишите, что делает этот поток…"
                value={newFlowDesc}
                onChange={(e) => setNewFlowDesc(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewFlowDialog(false)}>Отмена</Button>
            <Button
              onClick={() => createFlowMutation.mutate({ name: newFlowName.trim(), description: newFlowDesc.trim() })}
              disabled={!newFlowName.trim() || createFlowMutation.isPending}
            >
              Создать поток
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
