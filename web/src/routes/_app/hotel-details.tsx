// Hotel Details page — Media, Pricing, Hotel Info
import { createFileRoute } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import {
  UploadCloudIcon,
  SearchIcon,
  PencilIcon,
  Trash2Icon,
  ImageIcon,
  VideoIcon,
  FileTextIcon,
  TagIcon,
  BotIcon,
  XIcon,
  LinkIcon,
  PlusIcon,
  ImagesIcon,
  CheckIcon,
  PhoneIcon,
  ZapIcon,
  PaperclipIcon,
  Loader2Icon,
  DollarSignIcon,
  XCircleIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  RefreshCwIcon,
  InstagramIcon,
  CalendarClockIcon,
} from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
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
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import {
  fetchHotelMediaItems,
  uploadHotelMediaItem,
  updateHotelMediaItem,
  deleteHotelMediaItem,
  addPhotosToAlbum,
  deleteHotelMediaPhoto,
  type HotelMediaItem,
  fetchHotelProfile,
  updateHotelProfile,
  createHotelProfileLink,
  deleteHotelProfileLink,
  fetchHotelPolicies,
  createHotelPolicy,
  updateHotelPolicy,
  deleteHotelPolicy,
  fetchHotelFAQs,
  createHotelFAQ,
  updateHotelFAQ,
  deleteHotelFAQ,
  fetchHandoverContacts,
  createHandoverContact,
  updateHandoverContact,
  deleteHandoverContact,
  type HotelProfile,
  type HotelProfileLink,
  type HotelPolicy,
  type HotelFAQ,
  type HandoverContact,
  fetchPlaybooks,
  createPlaybook,
  updatePlaybook,
  deletePlaybook,
  processPlaybookFile,
  type Playbook,
  fetchReplyTemplateCategories,
  createReplyTemplateCategory,
  updateReplyTemplateCategory,
  deleteReplyTemplateCategory,
  createReplyTemplate,
  updateReplyTemplate,
  deleteReplyTemplate,
  type ReplyTemplate,
  type ReplyTemplateCategory,
  type ReplyTemplateChannel,
  fetchRoomPricing,
  createRoomPricing,
  updateRoomPricing,
  deleteRoomPricing,
  uploadRoomPricingExcel,
  type RoomPricing,
  type RoomPricingFormData,
  fetchRoomCombinations,
  fetchRoomCombinationRoomTypes,
  createCustomCombination,
  deleteCustomCombination,
  hideAutoCombination,
  saveRoomCombinationNote,
  saveCombinationType,
  type RoomCombinationGroup,
  type RoomCategory,
  fetchSocialContentItems,
  updateSocialContentItem,
  deleteSocialContentItem,
  markSocialContentReviewed,
  rebuildSocialContentFingerprints,
  syncInstagramSocialContent,
  type SocialContentItem,
  type SocialContentReviewStatus,
  type SocialContentStatus,
  type SocialContentType,
  type User,
} from '@/lib/api'
import { DatePicker } from '@/components/date-picker'
import { useAuth } from '@/contexts/auth-context'

export const Route = createFileRoute('/_app/hotel-details')({
  component: HotelDetailsPage,
})

function canEditHotelPricing(user: User | null | undefined) {
  return Boolean(
    user?.is_superadmin ||
    user?.is_admin ||
    user?.current_organization_role === 'owner' ||
    user?.current_organization_role === 'admin',
  )
}

const CATEGORIES = [
  { value: 'rooms', label: 'Номера' },
  { value: 'cafeteria', label: 'Кафе и Рестораны' },
  { value: 'pool', label: 'Бассейн' },
  { value: 'spa', label: 'Спа и Велнес' },
  { value: 'conference', label: 'Конференции и Мероприятия' },
  { value: 'exterior', label: 'Территория и Виды' },
  { value: 'lobby', label: 'Лобби и Общие зоны' },
  { value: 'other', label: 'Другое' },
]

const TAG_COLORS = [
  'bg-blue-100 text-blue-700 border-blue-200',
  'bg-green-100 text-green-700 border-green-200',
  'bg-purple-100 text-purple-700 border-purple-200',
  'bg-amber-100 text-amber-700 border-amber-200',
  'bg-rose-100 text-rose-700 border-rose-200',
]

function tagColor(tag: string): string {
  const idx = tag.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % TAG_COLORS.length
  return TAG_COLORS[idx]
}

interface MediaFormState {
  title: string
  description: string
  tags: string[]
  category: string
  room_category: RoomCategory | null
  media_type: 'photo' | 'video' | 'document'
  video_url: string
}

const EMPTY_FORM: MediaFormState = {
  title: '',
  description: '',
  tags: [],
  category: 'other',
  room_category: null,
  media_type: 'photo',
  video_url: '',
}

interface MediaGridProps {
  items: HotelMediaItem[]
  isLoading: boolean
  mediaType: 'photo' | 'video' | 'document'
  search: string
  category: string
  onEdit: (item: HotelMediaItem) => void
  onDelete: (item: HotelMediaItem) => void
  onUpload: () => void
}

function MediaGrid({ items, isLoading, mediaType, search, category, onEdit, onDelete, onUpload }: MediaGridProps) {
  const { language } = useLanguage()
  const filtered = items.filter((item) => {
    if (item.media_type !== mediaType) return false
    if (category && category !== 'all' && item.category !== category) return false
    if (search) {
      const q = search.toLowerCase()
      return (
        item.title.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.tags.some((t) => t.toLowerCase().includes(q))
      )
    }
    return true
  })

  const TypeIcon = mediaType === 'photo' ? ImageIcon : mediaType === 'video' ? VideoIcon : FileTextIcon

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-xl border bg-card animate-pulse">
            <div className="h-44 bg-muted rounded-t-xl" />
            <div className="p-4 space-y-2">
              <div className="h-4 bg-muted rounded w-3/4" />
              <div className="h-3 bg-muted rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {filtered.map((item) => (
        <MediaCard key={item.id} item={item} onEdit={onEdit} onDelete={onDelete} />
      ))}

      <button
        onClick={onUpload}
        className="group rounded-xl border-2 border-dashed border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30 transition-all min-h-[220px] flex flex-col items-center justify-center gap-3 p-6"
      >
        <div className="rounded-full bg-muted p-3 group-hover:bg-primary/10 transition-colors">
          <UploadCloudIcon className="h-6 w-6 text-muted-foreground group-hover:text-primary" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-muted-foreground group-hover:text-foreground">
            {language === 'ru' ? `Загрузить ${mediaType === 'photo' ? 'фото' : mediaType === 'video' ? 'видео' : 'документ'}` : `Upload ${mediaType}`}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {language === 'ru' ? 'Нажмите для выбора' : 'Click to browse'}
          </p>
        </div>
      </button>

      {filtered.length === 0 && !isLoading && (
        <div className="col-span-full text-center py-16 text-muted-foreground">
          <TypeIcon className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            {search || (category && category !== 'all')
              ? (language === 'ru' ? 'По вашим фильтрам ничего не найдено' : 'No results match your filters')
              : (language === 'ru' ? `Нет загруженных ${mediaType === 'photo' ? 'фотографий' : mediaType === 'video' ? 'видео' : 'документов'}` : `No ${mediaType}s uploaded yet`)}
          </p>
        </div>
      )}
    </div>
  )
}

function MediaCard({
  item,
  onEdit,
  onDelete,
}: {
  item: HotelMediaItem
  onEdit: (item: HotelMediaItem) => void
  onDelete: (item: HotelMediaItem) => void
}) {
  const { language } = useLanguage()
  const isPhoto = item.media_type === 'photo'
  const isVideo = item.media_type === 'video'
  const albumPhotos = item.photos ?? []
  const hasAlbum = isPhoto && albumPhotos.length > 0

  const allPhotoUrls: string[] = []
  if (hasAlbum) {
    albumPhotos.slice(0, 4).forEach((p) => { if (p.file_url) allPhotoUrls.push(p.file_url) })
  } else if (isPhoto && item.file_url) {
    allPhotoUrls.push(item.file_url)
  }

  return (
    <div className="group rounded-xl border bg-card overflow-hidden flex flex-col hover:shadow-md transition-shadow">
      <div className="relative h-44 bg-muted overflow-hidden flex-shrink-0">
        {isPhoto && allPhotoUrls.length > 1 ? (
          <div className="w-full h-full grid grid-cols-2 gap-0.5">
            {allPhotoUrls.slice(0, 4).map((url, i) => (
              <div key={i} className="relative overflow-hidden bg-muted">
                <img src={url} alt="" className="w-full h-full object-cover" />
                {i === 3 && albumPhotos.length > 4 ? (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <span className="text-white text-sm font-semibold">+{albumPhotos.length - 4}</span>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : isPhoto && allPhotoUrls.length === 1 ? (
          <img src={allPhotoUrls[0]} alt={item.title} className="w-full h-full object-cover" />
        ) : isVideo && item.video_url ? (
          <div className="w-full h-full flex items-center justify-center bg-slate-900">
            <VideoIcon className="h-10 w-10 text-white/60" />
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            {item.media_type === 'document' ? (
              <FileTextIcon className="h-10 w-10 text-muted-foreground/40" />
            ) : (
              <ImageIcon className="h-10 w-10 text-muted-foreground/40" />
            )}
          </div>
        )}

        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
          <Button size="icon" variant="secondary" className="h-8 w-8" onClick={() => onEdit(item)}>
            <PencilIcon className="h-3.5 w-3.5" />
          </Button>
          <Button size="icon" variant="destructive" className="h-8 w-8" onClick={() => onDelete(item)}>
            <Trash2Icon className="h-3.5 w-3.5" />
          </Button>
        </div>

        {hasAlbum ? (
          <div className="absolute top-2 left-2 flex items-center gap-1 rounded-full bg-black/70 px-2 py-0.5 text-xs text-white">
            <ImagesIcon className="h-3 w-3" />
            {albumPhotos.length}
          </div>
        ) : null}

        {item.ai_send_count > 0 ? (
          <div className="absolute top-2 right-2 flex items-center gap-1 rounded-full bg-black/70 px-2 py-0.5 text-xs text-white">
            <BotIcon className="h-3 w-3" />
            {item.ai_send_count}x
          </div>
        ) : null}
      </div>

      <div className="p-3 flex flex-col gap-2 flex-1">
        <h3 className="text-sm font-semibold leading-tight line-clamp-1">{item.title}</h3>

        {item.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {item.tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${tagColor(tag)}`}
              >
                {tag}
              </span>
            ))}
            {item.tags.length > 4 ? (
              <span className="text-[10px] text-muted-foreground">+{item.tags.length - 4}</span>
            ) : null}
          </div>
        ) : null}

        {item.description ? (
          <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
            {item.description}
          </p>
        ) : null}

        <div className="mt-auto pt-1 flex items-center justify-between text-[10px] text-muted-foreground">
          <span className="capitalize">{item.category_display}</span>
          {item.ai_send_count > 0 ? (
            <span className="flex items-center gap-1 text-emerald-600">
              <BotIcon className="h-3 w-3" />
              {language === 'ru' ? `Отправлено AI: ${item.ai_send_count} раз` : `Sent ${item.ai_send_count}x by AI`}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  )
}

// ── Hotel Policy Tab ──────────────────────────────────────────────────────────

function HotelPolicyTab() {
  const queryClient = useQueryClient()

  // ── Profile & Location ──────────────────────────────────────────────────────
  const { data: profile } = useQuery({ queryKey: ['hotel-profile'], queryFn: fetchHotelProfile })
  const [profileDraft, setProfileDraft] = useState<Omit<HotelProfile, 'links' | 'updated_at'> | null>(null)
  const profileSynced = useRef(false)
  if (profile && !profileSynced.current) {
    profileSynced.current = true
    setProfileDraft({
      hotel_name: profile.hotel_name,
      website: profile.website,
      description: profile.description,
      address: profile.address,
      directions: profile.directions,
    })
  }

  const saveProfileMutation = useMutation({
    mutationFn: (data: Omit<HotelProfile, 'links' | 'updated_at'>) => updateHotelProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-profile'] })
      toast.success('Profile saved')
    },
    onError: () => toast.error('Failed to save profile'),
  })

  // ── Links ───────────────────────────────────────────────────────────────────
  const [linkDialogOpen, setLinkDialogOpen] = useState(false)
  const [linkForm, setLinkForm] = useState({ label: '', url: '' })

  const createLinkMutation = useMutation({
    mutationFn: (data: { label: string; url: string }) => createHotelProfileLink(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-profile'] })
      setLinkDialogOpen(false)
      toast.success('Link added')
    },
    onError: () => toast.error('Не удалось добавить ссылку'),
  })

  const deleteLinkMutation = useMutation({
    mutationFn: (id: number) => deleteHotelProfileLink(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hotel-profile'] }),
    onError: () => toast.error('Failed to delete link'),
  })

  // ── Policies ────────────────────────────────────────────────────────────────
  const { data: policies = [] } = useQuery({ queryKey: ['hotel-policies'], queryFn: fetchHotelPolicies })
  const [policyDialog, setPolicyDialog] = useState<{ open: boolean; item: HotelPolicy | null }>({ open: false, item: null })
  const [policyForm, setPolicyForm] = useState({ label: '', emoji: '', value: '', description: '' })

  const createPolicyMutation = useMutation({
    mutationFn: (data: typeof policyForm) => createHotelPolicy(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-policies'] })
      setPolicyDialog({ open: false, item: null })
      toast.success('Policy added')
    },
    onError: () => toast.error('Failed to save policy'),
  })

  const updatePolicyMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: typeof policyForm }) => updateHotelPolicy(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-policies'] })
      setPolicyDialog({ open: false, item: null })
      toast.success('Policy updated')
    },
    onError: () => toast.error('Failed to save policy'),
  })

  const deletePolicyMutation = useMutation({
    mutationFn: (id: number) => deleteHotelPolicy(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hotel-policies'] }),
    onError: () => toast.error('Failed to delete policy'),
  })

  // ── FAQs ────────────────────────────────────────────────────────────────────
  const { data: faqs = [] } = useQuery({ queryKey: ['hotel-faqs'], queryFn: fetchHotelFAQs })
  const [faqDialog, setFaqDialog] = useState<{ open: boolean; item: HotelFAQ | null }>({ open: false, item: null })
  const [faqForm, setFaqForm] = useState({ question: '', answer: '' })

  const createFaqMutation = useMutation({
    mutationFn: (data: typeof faqForm) => createHotelFAQ(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-faqs'] })
      setFaqDialog({ open: false, item: null })
      toast.success('FAQ added')
    },
    onError: () => toast.error('Failed to save FAQ'),
  })

  const updateFaqMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: typeof faqForm }) => updateHotelFAQ(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-faqs'] })
      setFaqDialog({ open: false, item: null })
      toast.success('FAQ updated')
    },
    onError: () => toast.error('Failed to save FAQ'),
  })

  const deleteFaqMutation = useMutation({
    mutationFn: (id: number) => deleteHotelFAQ(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hotel-faqs'] }),
    onError: () => toast.error('Failed to delete FAQ'),
  })

  // ── Handover Contacts ───────────────────────────────────────────────────────
  const { data: contacts = [] } = useQuery({ queryKey: ['handover-contacts'], queryFn: fetchHandoverContacts })
  const [contactDialog, setContactDialog] = useState<{ open: boolean; item: HandoverContact | null }>({ open: false, item: null })
  const [contactForm, setContactForm] = useState({ name: '', phone: '', escalate_when: '' })

  const createContactMutation = useMutation({
    mutationFn: (data: typeof contactForm) => createHandoverContact(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['handover-contacts'] })
      setContactDialog({ open: false, item: null })
      toast.success('Contact added')
    },
    onError: () => toast.error('Failed to save contact'),
  })

  const updateContactMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: typeof contactForm }) => updateHandoverContact(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['handover-contacts'] })
      setContactDialog({ open: false, item: null })
      toast.success('Contact updated')
    },
    onError: () => toast.error('Failed to save contact'),
  })

  const deleteContactMutation = useMutation({
    mutationFn: (id: number) => deleteHandoverContact(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['handover-contacts'] }),
    onError: () => toast.error('Failed to delete contact'),
  })

  // ── Dialog helpers ──────────────────────────────────────────────────────────
  const openPolicyDialog = (item: HotelPolicy | null) => {
    setPolicyForm(item
      ? { label: item.label, emoji: item.emoji, value: item.value, description: item.description }
      : { label: '', emoji: '', value: '', description: '' }
    )
    setPolicyDialog({ open: true, item })
  }

  const openFaqDialog = (item: HotelFAQ | null) => {
    setFaqForm(item ? { question: item.question, answer: item.answer } : { question: '', answer: '' })
    setFaqDialog({ open: true, item })
  }

  const openContactDialog = (item: HandoverContact | null) => {
    setContactForm(item
      ? { name: item.name, phone: item.phone, escalate_when: item.escalate_when }
      : { name: '', phone: '', escalate_when: '' }
    )
    setContactDialog({ open: true, item })
  }

  if (!profileDraft) {
    return (
      <div className="space-y-6 animate-pulse">
        {[...Array(3)].map((_, i) => <div key={i} className="h-32 rounded-xl bg-muted" />)}
      </div>
    )
  }

  const links: HotelProfileLink[] = profile?.links ?? []

  return (
    <div className="space-y-0 max-w-3xl">

      {/* ── Company Profile ── */}
      <div className="pb-6 border-b border-border">
        <h3 className="text-base font-semibold mb-0.5">Company Profile</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Basic info the AI uses for introductions and general queries.
        </p>
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Hotel Name</Label>
              <Input
                value={profileDraft.hotel_name}
                onChange={(e) => setProfileDraft((d) => d ? { ...d, hotel_name: e.target.value } : d)}
                placeholder="напр. Курорт Кочевник"
              />
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Website</Label>
              <Input
                value={profileDraft.website}
                onChange={(e) => setProfileDraft((d) => d ? { ...d, website: e.target.value } : d)}
                placeholder="https://nomadcamp.kg"
              />
            </div>
          </div>
          <div>
            <Label className="text-sm font-medium mb-1.5 block">Description</Label>
            <Textarea
              value={profileDraft.description}
              onChange={(e) => setProfileDraft((d) => d ? { ...d, description: e.target.value } : d)}
              placeholder="Краткое введение, которое AI использует, когда гости спрашивают об отеле..."
              className="min-h-[80px] text-sm"
            />
          </div>
        </div>
      </div>

      {/* ── Location & Directions ── */}
      <div className="py-6 border-b border-border">
        <h3 className="text-base font-semibold mb-0.5">Location & Directions</h3>
        <p className="text-sm text-muted-foreground mb-4">
          The AI shares this when guests ask how to find you.
        </p>
        <div className="space-y-3">
          <div>
            <Label className="text-sm font-medium mb-1.5 block">Address</Label>
            <Input
              value={profileDraft.address}
              onChange={(e) => setProfileDraft((d) => d ? { ...d, address: e.target.value } : d)}
              placeholder="напр. побережье озера Иссык-Куль, Чолпон-Ата, Кыргызстан"
            />
          </div>
          <div>
            <Label className="text-sm font-medium mb-1.5 block">Directions</Label>
            <Textarea
              value={profileDraft.directions}
              onChange={(e) => setProfileDraft((d) => d ? { ...d, directions: e.target.value } : d)}
              placeholder="Пошаговая инструкция о том, как добраться, которую AI отправляет гостям..."
              className="min-h-[80px] text-sm"
            />
          </div>

          {/* Shareable Links */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-sm font-medium">Shareable Links</Label>
              <Button
                variant="outline" size="sm"
                onClick={() => { setLinkForm({ label: '', url: '' }); setLinkDialogOpen(true) }}
                className="gap-1.5"
              >
                <PlusIcon className="h-3.5 w-3.5" /> Добавить ссылку
              </Button>
            </div>
            {links.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">
                No links yet. Add Google Maps, booking page, etc.
              </p>
            ) : (
              <div className="space-y-2">
                {links.map((link) => (
                  <div key={link.id} className="flex items-center gap-2 p-2.5 rounded-lg border bg-muted/30">
                    <LinkIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm font-medium flex-1 min-w-0 truncate">{link.label}</span>
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-primary truncate max-w-[200px]"
                    >
                      {link.url}
                    </a>
                    <Button
                      variant="ghost" size="icon"
                      className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => deleteLinkMutation.mutate(link.id)}
                    >
                      <XIcon className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Save Profile ── */}
      <div className="py-5 border-b border-border flex items-center gap-3">
        <Button
          onClick={() => saveProfileMutation.mutate(profileDraft)}
          disabled={saveProfileMutation.isPending}
        >
          {saveProfileMutation.isPending ? 'Saving…' : 'Save Profile'}
        </Button>
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => {
            profileSynced.current = false
            queryClient.invalidateQueries({ queryKey: ['hotel-profile'] })
          }}
        >
          Reset
        </button>
      </div>

      {/* ── Hotel Policies ── */}
      <div className="py-6 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold">Hotel Policies</h3>
          <Button variant="outline" size="sm" onClick={() => openPolicyDialog(null)} className="gap-1.5">
            <PlusIcon className="h-3.5 w-3.5" /> Add Policy
          </Button>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Rules the AI can quote to guests — pets, parking, smoking, check-in times, etc.
        </p>
        {policies.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">No policies yet. Add your first one.</p>
        ) : (
          <div className="space-y-2">
            {policies.map((policy) => (
              <div
                key={policy.id}
                className="group flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-muted/20 transition-colors"
              >
                <span className="text-xl leading-none mt-0.5 w-7 text-center shrink-0">
                  {policy.emoji || '📋'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-baseline gap-1.5">
                    <span className="font-medium text-sm">{policy.label}</span>
                    <span className="text-muted-foreground text-sm">—</span>
                    <span className="text-sm">{policy.value}</span>
                  </div>
                  {policy.description ? (
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{policy.description}</p>
                  ) : null}
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  <Button
                    variant="ghost" size="icon" className="h-7 w-7"
                    onClick={() => openPolicyDialog(policy)}
                  >
                    <PencilIcon className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost" size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={() => deletePolicyMutation.mutate(policy.id)}
                  >
                    <Trash2Icon className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── FAQs ── */}
      <div className="py-6 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold">Frequently Asked Questions</h3>
          <Button variant="outline" size="sm" onClick={() => openFaqDialog(null)} className="gap-1.5">
            <PlusIcon className="h-3.5 w-3.5" /> Add FAQ
          </Button>
        </div>
        <p className="text-sm text-muted-foreground mb-5">
          Common questions with prepared answers. The AI uses these verbatim when guests ask.
        </p>
        {faqs.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">No FAQs yet. Add your first question.</p>
        ) : (
          <div className="space-y-5">
            {faqs.map((faq) => (
              <div key={faq.id} className="group relative">
                {/* Q bubble — guest */}
                <div className="flex justify-start mb-1.5">
                  <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-muted px-4 py-2.5">
                    <p className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wide">Guest</p>
                    <p className="text-sm leading-relaxed">{faq.question}</p>
                  </div>
                </div>
                {/* A bubble — AI */}
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary/10 border border-primary/20 px-4 py-2.5">
                    <p className="text-xs font-semibold text-primary/70 mb-1 uppercase tracking-wide">AI Agent</p>
                    <p className="text-sm leading-relaxed">{faq.answer}</p>
                  </div>
                </div>
                {/* Actions — appear on hover */}
                <div className="absolute -top-2 right-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Button
                    variant="ghost" size="icon"
                    className="h-7 w-7 bg-background border shadow-sm"
                    onClick={() => openFaqDialog(faq)}
                  >
                    <PencilIcon className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost" size="icon"
                    className="h-7 w-7 bg-background border shadow-sm text-muted-foreground hover:text-destructive"
                    onClick={() => deleteFaqMutation.mutate(faq.id)}
                  >
                    <Trash2Icon className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Handover Contacts ── */}
      <div className="py-6">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold">Handover Contacts</h3>
          <Button variant="outline" size="sm" onClick={() => openContactDialog(null)} className="gap-1.5">
            <PlusIcon className="h-3.5 w-3.5" /> Add Contact
          </Button>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Managers or staff the AI recommends when it cannot help directly.
        </p>
        {contacts.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">No contacts yet.</p>
        ) : (
          <div className="space-y-2">
            {contacts.map((contact) => (
              <div
                key={contact.id}
                className="group flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-muted/20 transition-colors"
              >
                <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                  <PhoneIcon className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="font-medium text-sm">{contact.name}</span>
                    <span className="text-sm text-muted-foreground">{contact.phone}</span>
                  </div>
                  {contact.escalate_when ? (
                    <p className="text-xs text-muted-foreground mt-0.5">{contact.escalate_when}</p>
                  ) : null}
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  <Button
                    variant="ghost" size="icon" className="h-7 w-7"
                    onClick={() => openContactDialog(contact)}
                  >
                    <PencilIcon className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost" size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={() => deleteContactMutation.mutate(contact.id)}
                  >
                    <Trash2Icon className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Policy Dialog ── */}
      <Dialog open={policyDialog.open} onOpenChange={(open) => { if (!open) setPolicyDialog({ open: false, item: null }) }}>
        <DialogContent className="max-w-[95vw] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{policyDialog.item ? 'Редактировать правило' : 'Добавить правило'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-[64px_1fr] gap-3">
              <div>
                <Label className="text-sm font-medium mb-1.5 block">Emoji</Label>
                <Input
                  value={policyForm.emoji}
                  onChange={(e) => setPolicyForm((f) => ({ ...f, emoji: e.target.value }))}
                  placeholder="🐾"
                  className="text-center text-lg"
                />
              </div>
              <div>
                <Label className="text-sm font-medium mb-1.5 block">Label</Label>
                <Input
                  value={policyForm.label}
                  onChange={(e) => setPolicyForm((f) => ({ ...f, label: e.target.value }))}
                  placeholder="напр. Животные / Домашние питомцы"
                />
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Value</Label>
              <Input
                value={policyForm.value}
                onChange={(e) => setPolicyForm((f) => ({ ...f, value: e.target.value }))}
                placeholder="напр. Разрешено, Запрещено, Есть платная парковка"
              />
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">
                Additional detail{' '}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Textarea
                value={policyForm.description}
                onChange={(e) => setPolicyForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Дополнительный контекст, которым AI может поделиться при уточняющих вопросах..."
                className="min-h-[70px] text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPolicyDialog({ open: false, item: null })}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                policyDialog.item
                  ? updatePolicyMutation.mutate({ id: policyDialog.item.id, data: policyForm })
                  : createPolicyMutation.mutate(policyForm)
              }
              disabled={
                !policyForm.label.trim() || !policyForm.value.trim() ||
                createPolicyMutation.isPending || updatePolicyMutation.isPending
              }
            >
              {policyDialog.item ? 'Save Changes' : 'Add Policy'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── FAQ Dialog ── */}
      <Dialog open={faqDialog.open} onOpenChange={(open) => { if (!open) setFaqDialog({ open: false, item: null }) }}>
        <DialogContent className="max-w-[95vw] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{faqDialog.item ? 'Редактировать FAQ' : 'Добавить FAQ'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Question</Label>
              <Textarea
                value={faqForm.question}
                onChange={(e) => setFaqForm((f) => ({ ...f, question: e.target.value }))}
                placeholder="напр. Разрешено ли проживание с животными?"
                className="min-h-[70px] text-sm"
              />
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Answer</Label>
              <Textarea
                value={faqForm.answer}
                onChange={(e) => setFaqForm((f) => ({ ...f, answer: e.target.value }))}
                placeholder="AI будет использовать этот точный ответ при возникновении вопроса..."
                className="min-h-[100px] text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFaqDialog({ open: false, item: null })}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                faqDialog.item
                  ? updateFaqMutation.mutate({ id: faqDialog.item.id, data: faqForm })
                  : createFaqMutation.mutate(faqForm)
              }
              disabled={
                !faqForm.question.trim() || !faqForm.answer.trim() ||
                createFaqMutation.isPending || updateFaqMutation.isPending
              }
            >
              {faqDialog.item ? 'Save Changes' : 'Add FAQ'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Contact Dialog ── */}
      <Dialog open={contactDialog.open} onOpenChange={(open) => { if (!open) setContactDialog({ open: false, item: null }) }}>
        <DialogContent className="max-w-[95vw] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{contactDialog.item ? 'Редактировать контакт' : 'Добавить контакт'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm font-medium mb-1.5 block">Name</Label>
                <Input
                  value={contactForm.name}
                  onChange={(e) => setContactForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="напр. Асель (Менеджер)"
                />
              </div>
              <div>
                <Label className="text-sm font-medium mb-1.5 block">Phone / Telegram</Label>
                <Input
                  value={contactForm.phone}
                  onChange={(e) => setContactForm((f) => ({ ...f, phone: e.target.value }))}
                  placeholder="+996 700 123 456"
                />
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">
                Escalate when{' '}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Input
                value={contactForm.escalate_when}
                onChange={(e) => setContactForm((f) => ({ ...f, escalate_when: e.target.value }))}
                placeholder="напр. Когда у гостя жалоба или особый запрос"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setContactDialog({ open: false, item: null })}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                contactDialog.item
                  ? updateContactMutation.mutate({ id: contactDialog.item.id, data: contactForm })
                  : createContactMutation.mutate(contactForm)
              }
              disabled={
                !contactForm.name.trim() || !contactForm.phone.trim() ||
                createContactMutation.isPending || updateContactMutation.isPending
              }
            >
              {contactDialog.item ? 'Save Changes' : 'Add Contact'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Link Dialog ── */}
      <Dialog open={linkDialogOpen} onOpenChange={(open) => { if (!open) setLinkDialogOpen(false) }}>
        <DialogContent className="max-w-[95vw] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Добавить ссылку</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Label</Label>
              <Input
                value={linkForm.label}
                onChange={(e) => setLinkForm((f) => ({ ...f, label: e.target.value }))}
                placeholder="напр. Google Карты, Страница бронирования"
              />
            </div>
            <div>
              <Label className="text-sm font-medium mb-1.5 block">URL</Label>
              <Input
                value={linkForm.url}
                onChange={(e) => setLinkForm((f) => ({ ...f, url: e.target.value }))}
                placeholder="https://..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLinkDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => createLinkMutation.mutate(linkForm)}
              disabled={!linkForm.label.trim() || !linkForm.url.trim() || createLinkMutation.isPending}
            >
              Добавить ссылку
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  )
}

// ── Playbooks Tab ──────────────────────────────────────────────────────────────

interface ContentBlock {
  id: string
  title: string
  content: string
}

function newBlockId(): string {
  return Math.random().toString(36).slice(2)
}

function parseContentBlocks(raw: string): ContentBlock[] {
  if (!raw || raw.trim() === '') {
    return [{ id: newBlockId(), title: '', content: '' }]
  }
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed as ContentBlock[]
    }
  } catch {
    // Backward compatibility: non-JSON legacy content is wrapped below.
  }
  // backward compat: wrap plain text as single block
  return [{ id: newBlockId(), title: '', content: raw }]
}

function serializeBlocks(blocks: ContentBlock[]): string {
  return JSON.stringify(blocks)
}

function PlaybooksTab() {
  const queryClient = useQueryClient()
  const { t } = useLanguage()

  const { data: playbooks = [] } = useQuery({ queryKey: ['playbooks'], queryFn: fetchPlaybooks })

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [form, setForm] = useState({ name: '', trigger_description: '', instructions: '', is_active: true, expires_at: '' })
  const [contentBlocks, setContentBlocks] = useState<ContentBlock[]>([{ id: newBlockId(), title: '', content: '' }])
  const [uploadingBlockId, setUploadingBlockId] = useState<string | null>(null)
  const [blockPreview, setBlockPreview] = useState<{ blockId: string; content: string } | null>(null)
  const formSyncedId = useRef<number | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Derive effective selected (auto-select first on load)
  const effectiveSelectedId = selectedId ?? (playbooks.length > 0 ? playbooks[0].id : null)
  const selectedPlaybook = effectiveSelectedId !== null ? (playbooks.find((p) => p.id === effectiveSelectedId) ?? null) : null

  // Sync form when selected playbook changes
  if (selectedPlaybook && formSyncedId.current !== selectedPlaybook.id) {
    formSyncedId.current = selectedPlaybook.id
    setForm({
      name: selectedPlaybook.name,
      trigger_description: selectedPlaybook.trigger_description,
      instructions: selectedPlaybook.instructions,
      is_active: selectedPlaybook.is_active,
      // Convert ISO string → datetime-local value (strip seconds+Z), or empty string
      expires_at: selectedPlaybook.expires_at
        ? selectedPlaybook.expires_at.slice(0, 16)
        : '',
    })
    setContentBlocks(parseContentBlocks(selectedPlaybook.content))
    setBlockPreview(null)
  }

  const createMutation = useMutation({
    mutationFn: createPlaybook,
    onSuccess: (created: Playbook) => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      formSyncedId.current = null
      setSelectedId(created.id)
      setForm({ name: created.name, trigger_description: '', instructions: '', is_active: true, expires_at: '' })
      setContentBlocks([{ id: newBlockId(), title: '', content: '' }])
      setBlockPreview(null)
      toast.success(t('hotelDetails.playbookCreated'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updatePlaybook>[1] }) => updatePlaybook(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      toast.success(t('hotelDetails.playbookSaved'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deletePlaybook,
    onSuccess: () => {
      formSyncedId.current = null
      setSelectedId(null)
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      toast.success(t('hotelDetails.playbookDeleted'))
    },
  })

  function handleSelect(id: number) {
    formSyncedId.current = null
    setSelectedId(id)
  }

  function handleSave() {
    if (!selectedPlaybook) return
    updateMutation.mutate({
      id: selectedPlaybook.id,
      data: {
        ...form,
        content: serializeBlocks(contentBlocks),
        // Send null to clear expiry, or ISO string for a set expiry
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      },
    })
  }

  function handleNew() {
    createMutation.mutate({ name: 'New Playbook', trigger_description: '', instructions: '', content: '', is_active: true })
  }

  function addBlock() {
    setContentBlocks((prev) => [...prev, { id: newBlockId(), title: '', content: '' }])
  }

  function removeBlock(blockId: string) {
    setContentBlocks((prev) => prev.filter((b) => b.id !== blockId))
  }

  function updateBlock(blockId: string, field: 'title' | 'content', value: string) {
    setContentBlocks((prev) => prev.map((b) => (b.id === blockId ? { ...b, [field]: value } : b)))
  }

  function triggerBlockUpload(blockId: string) {
    setUploadingBlockId(blockId)
    fileInputRef.current?.click()
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    const targetBlockId = uploadingBlockId
    if (!file || !selectedPlaybook || !targetBlockId) {
      setUploadingBlockId(null)
      return
    }
    e.target.value = ''
    setExtracting(true)
    setBlockPreview(null)
    try {
      const result = await processPlaybookFile(selectedPlaybook.id, file)
      setBlockPreview({ blockId: targetBlockId, content: result.content })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('hotelDetails.playbookFileError'))
    } finally {
      setExtracting(false)
      setUploadingBlockId(null)
    }
  }

  return (
    <div className="flex gap-4 min-h-[600px]">
      {/* Sidebar: playbook list */}
      <div className="w-52 flex-shrink-0 flex flex-col gap-1">
        <Button
          size="sm"
          variant="outline"
          className="w-full justify-start gap-2 mb-2"
          onClick={handleNew}
          disabled={createMutation.isPending}
        >
          <PlusIcon className="h-4 w-4" />
          {t('hotelDetails.newPlaybook')}
        </Button>
        {playbooks.map((p) => {
          const now = new Date()
          const isExpired = p.expires_at ? new Date(p.expires_at) <= now : false
          const hasExpiry = !!p.expires_at && !isExpired
          return (
            <button
              key={p.id}
              onClick={() => handleSelect(p.id)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                p.id === effectiveSelectedId
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted text-foreground'
              } ${isExpired ? 'opacity-50' : ''}`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full flex-shrink-0 ${
                    isExpired ? 'bg-red-500' : p.is_active ? 'bg-green-500' : 'bg-muted-foreground/40'
                  }`}
                />
                <span className="truncate flex-1">{p.name}</span>
              </div>
              {isExpired ? (
                  <span className="mt-1 inline-block text-[10px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400">
                  {t('hotelDetails.playbookExpired')}
                </span>
              ) : hasExpiry ? (
                <span className="mt-1 inline-block text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
                  {t('hotelDetails.playbookExpires')} {new Date(p.expires_at!).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
              ) : null}
            </button>
          )
        })}
        {playbooks.length === 0 && (
          <p className="text-xs text-muted-foreground px-2 py-6 text-center leading-relaxed">
            {t('hotelDetails.playbookNoDesc')}
          </p>
        )}
      </div>

      {/* Editor */}
      {selectedPlaybook ? (
        <Card className="flex-1 min-w-0">
          <CardContent className="p-5 space-y-5">
            {/* Name row + active toggle + delete */}
            <div className="flex items-center gap-3">
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="text-base font-medium flex-1"
                placeholder="Название сценария"
              />
              <div className="flex items-center gap-2 flex-shrink-0">
                <Switch
                  checked={form.is_active}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, is_active: v }))}
                />
                <span className="text-sm text-muted-foreground whitespace-nowrap">
                  {form.is_active ? t('hotelDetails.playbookActive') : t('hotelDetails.playbookInactive')}
                </span>
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label="Delete playbook"
                className="text-destructive hover:text-destructive flex-shrink-0"
                onClick={() => setDeleteConfirmOpen(true)}
              >
                <Trash2Icon className="h-4 w-4" />
              </Button>
            </div>

            {/* Expiration date */}
            <div className="space-y-1.5">
              <Label>{t('hotelDetails.playbookExpirationDate')}</Label>
              <p className="text-xs text-muted-foreground">
                {t('hotelDetails.playbookExpirationDesc')}
              </p>
              <Input
                type="datetime-local"
                value={form.expires_at}
                onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value }))}
                className="max-w-xs"
              />
            </div>

            {/* Trigger */}
            <div className="space-y-1.5">
              <Label>{t('hotelDetails.playbookWhenToActivate')}</Label>
              <p className="text-xs text-muted-foreground">
                {t('hotelDetails.playbookTriggerDesc')}
              </p>
              <Textarea
                value={form.trigger_description}
                onChange={(e) => setForm((f) => ({ ...f, trigger_description: e.target.value }))}
                placeholder="напр. Когда гость спрашивает о ценах на номера, доступности или бронировании"
                rows={2}
              />
            </div>

            {/* Instructions */}
            <div className="space-y-1.5">
              <Label>{t('hotelDetails.playbookAiInstructions')}</Label>
              <p className="text-xs text-muted-foreground">
                {t('hotelDetails.playbookInstructionsDesc')}
              </p>
              <Textarea
                value={form.instructions}
                onChange={(e) => setForm((f) => ({ ...f, instructions: e.target.value }))}
                placeholder="напр. Всегда уточняйте количество гостей перед сообщением цен. Упоминайте скидку за раннее бронирование."
                rows={4}
              />
            </div>

            {/* Content Blocks */}
            <div className="space-y-3">
              <Label>{t('hotelDetails.playbookKnowledge')}</Label>
              <p className="text-xs text-muted-foreground -mt-1.5">
                {t('hotelDetails.playbookKnowledgeDesc')}
              </p>

              {contentBlocks.map((block, idx) => (
                <div key={block.id} className="rounded-md border p-3 space-y-2.5">
                  {/* Block header: title + remove */}
                  <div className="flex items-center gap-2">
                    <Input
                      value={block.title}
                      onChange={(e) => updateBlock(block.id, 'title', e.target.value)}
                      placeholder={`${t('hotelDetails.playbookBlockTitlePlaceholder')} ${idx + 1}`}
                      className="h-8 text-sm flex-1"
                    />
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 flex-shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeBlock(block.id)}
                      disabled={contentBlocks.length === 1}
                      aria-label="Remove block"
                    >
                      <XIcon className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  {/* Extracted preview for this block */}
                  {blockPreview?.blockId === block.id && (
                    <div className="rounded-md border bg-muted/40 p-3 space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-medium">{t('hotelDetails.playbookExtracted')}</p>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-5 w-5 flex-shrink-0"
                          onClick={() => setBlockPreview(null)}
                          aria-label="Dismiss preview"
                        >
                          <XIcon className="h-3 w-3" />
                        </Button>
                      </div>
                      <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono max-h-40 overflow-y-auto leading-relaxed">
                        {blockPreview.content}
                      </pre>
                      <Button
                        size="sm"
                        className="w-full gap-1.5"
                        onClick={() => {
                          updateBlock(
                            block.id,
                            'content',
                            block.content ? `${block.content}\n\n${blockPreview.content}` : blockPreview.content,
                          )
                          setBlockPreview(null)
                          toast.success(t('hotelDetails.playbookContentInserted'))
                        }}
                      >
                        <CheckIcon className="h-3.5 w-3.5" />
                        {t('hotelDetails.playbookInsertBlock')}
                      </Button>
                    </div>
                  )}

                  {/* Textarea + upload */}
                  <Textarea
                    value={block.content}
                    onChange={(e) => updateBlock(block.id, 'content', e.target.value)}
                    placeholder="Факты, таблицы, скрипты или примеры, на которые AI может ссылаться. Поддерживается Markdown."
                    rows={6}
                    className="font-mono text-sm"
                  />
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="gap-1.5 h-7 text-xs"
                      onClick={() => triggerBlockUpload(block.id)}
                      disabled={extracting}
                    >
                      {extracting && uploadingBlockId === block.id ? (
                        <>
                          <Loader2Icon className="h-3 w-3 animate-spin" />
                          {t('hotelDetails.playbookExtracting')}
                        </>
                      ) : (
                        <>
                          <PaperclipIcon className="h-3 w-3" />
                          {t('hotelDetails.playbookUploadFile')}
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              ))}

              <button
                type="button"
                onClick={addBlock}
                className="w-full border border-dashed rounded-md py-2 text-sm text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors flex items-center justify-center gap-1.5"
              >
                <PlusIcon className="h-3.5 w-3.5" />
                {t('hotelDetails.playbookAddBlock')}
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,application/pdf"
                className="hidden"
                onChange={handleFileUpload}
              />
            </div>

            <div className="flex justify-end">
              <Button onClick={handleSave} disabled={updateMutation.isPending}>
                {updateMutation.isPending ? t('hotelDetails.playbookSaving') : t('hotelDetails.playbookSave')}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
          {playbooks.length === 0 ? t('hotelDetails.playbookSelectOrCreate') : t('hotelDetails.playbookSelect')}
        </div>
      )}

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить сценарий?</AlertDialogTitle>
            <AlertDialogDescription>
              &quot;{selectedPlaybook?.name}&quot; {t('hotelDetails.playbookDeleteConfirmDesc')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (selectedPlaybook) deleteMutation.mutate(selectedPlaybook.id)
                setDeleteConfirmOpen(false)
              }}
            >
              {t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ── Reply Templates Tab ───────────────────────────────────────────────────────

const REPLY_TEMPLATE_CHANNEL_LABELS: Record<ReplyTemplateChannel, string> = {
  all: 'Все каналы',
  telegram: 'Telegram',
  instagram: 'Instagram',
  whatsapp: 'WhatsApp',
}

const EMPTY_TEMPLATE_FORM = {
  title: '',
  text: '',
  channel: 'all' as ReplyTemplateChannel,
  tags: '',
  is_active: true,
}

function getApiErrorMessage(error: unknown, fallback: string) {
  const data = (error as { data?: unknown })?.data
  if (data && typeof data === 'object') {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    const firstValue = Object.values(data as Record<string, unknown>)[0]
    if (Array.isArray(firstValue) && typeof firstValue[0] === 'string') return firstValue[0]
  }
  return fallback
}

function ReplyTemplatesTab() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const orgSlug = user?.current_organization_slug ?? ''
  const categoriesQueryKey = ['reply-template-categories', orgSlug] as const
  const { data: categories = [], isLoading } = useQuery({
    queryKey: categoriesQueryKey,
    queryFn: fetchReplyTemplateCategories,
    enabled: !!orgSlug,
  })

  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null)
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [categoryError, setCategoryError] = useState('')
  const [categoryName, setCategoryName] = useState('')
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<ReplyTemplate | null>(null)
  const [templateForm, setTemplateForm] = useState(EMPTY_TEMPLATE_FORM)
  const [categoryDeleteTarget, setCategoryDeleteTarget] = useState<ReplyTemplateCategory | null>(null)
  const [templateDeleteTarget, setTemplateDeleteTarget] = useState<ReplyTemplate | null>(null)

  const selectedCategory = useMemo(() => {
    if (selectedCategoryId !== null) {
      return categories.find((category) => category.id === selectedCategoryId) ?? categories[0] ?? null
    }
    return categories[0] ?? null
  }, [categories, selectedCategoryId])

  useEffect(() => {
    if (!selectedCategoryId && categories[0]) {
      setSelectedCategoryId(categories[0].id)
    }
  }, [categories, selectedCategoryId])

  useEffect(() => {
    setCategoryName(selectedCategory?.name ?? '')
  }, [selectedCategory?.id, selectedCategory?.name])

  const invalidateTemplates = () => {
    queryClient.invalidateQueries({ queryKey: categoriesQueryKey })
    queryClient.invalidateQueries({ queryKey: ['reply-templates'] })
  }

  const createCategoryMutation = useMutation({
    mutationFn: createReplyTemplateCategory,
    onSuccess: (created) => {
      queryClient.setQueryData<ReplyTemplateCategory[]>(categoriesQueryKey, (existing = []) => {
        const withoutDuplicate = existing.filter((category) => category.id !== created.id)
        return [...withoutDuplicate, created].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name))
      })
      invalidateTemplates()
      setSelectedCategoryId(created.id)
      setCategoryDialogOpen(false)
      setNewCategoryName('')
      setCategoryError('')
      toast.success('Раздел добавлен')
    },
    onError: (error) => {
      const message = getApiErrorMessage(error, 'Не удалось добавить раздел')
      setCategoryError(message)
      toast.error(message)
    },
  })

  const updateCategoryMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => updateReplyTemplateCategory(id, { name }),
    onSuccess: () => {
      invalidateTemplates()
      toast.success('Раздел сохранен')
    },
    onError: () => toast.error('Не удалось сохранить раздел'),
  })

  const deleteCategoryMutation = useMutation({
    mutationFn: deleteReplyTemplateCategory,
    onSuccess: () => {
      invalidateTemplates()
      setSelectedCategoryId(null)
      setCategoryDeleteTarget(null)
      toast.success('Раздел удален')
    },
    onError: () => toast.error('Не удалось удалить раздел'),
  })

  const createTemplateMutation = useMutation({
    mutationFn: createReplyTemplate,
    onSuccess: () => {
      invalidateTemplates()
      setTemplateDialogOpen(false)
      toast.success('Шаблон добавлен')
    },
    onError: () => toast.error('Не удалось добавить шаблон'),
  })

  const updateTemplateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateReplyTemplate>[1] }) => updateReplyTemplate(id, data),
    onSuccess: () => {
      invalidateTemplates()
      setTemplateDialogOpen(false)
      toast.success('Шаблон сохранен')
    },
    onError: () => toast.error('Не удалось сохранить шаблон'),
  })

  const deleteTemplateMutation = useMutation({
    mutationFn: deleteReplyTemplate,
    onSuccess: () => {
      invalidateTemplates()
      setTemplateDeleteTarget(null)
      toast.success('Шаблон удален')
    },
    onError: () => toast.error('Не удалось удалить шаблон'),
  })

  const openCreateTemplate = () => {
    setEditingTemplate(null)
    setTemplateForm(EMPTY_TEMPLATE_FORM)
    setTemplateDialogOpen(true)
  }

  const handleCreateCategory = () => {
    const name = newCategoryName.trim()
    setCategoryError('')
    if (!name) {
      const message = 'Введите название раздела'
      setCategoryError(message)
      toast.error(message)
      return
    }
    createCategoryMutation.mutate({ name })
  }

  const openEditTemplate = (template: ReplyTemplate) => {
    setEditingTemplate(template)
    setTemplateForm({
      title: template.title,
      text: template.text,
      channel: template.channel,
      tags: template.tags.join(', '),
      is_active: template.is_active,
    })
    setTemplateDialogOpen(true)
  }

  const handleTemplateSubmit = () => {
    if (!selectedCategory) return
    const title = templateForm.title.trim()
    const text = templateForm.text.trim()
    if (!title || !text) {
      toast.error('Заполните название и текст шаблона')
      return
    }
    const payload = {
      category: selectedCategory.id,
      title,
      text,
      channel: templateForm.channel,
      tags: templateForm.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
      is_active: templateForm.is_active,
    }

    if (editingTemplate) {
      updateTemplateMutation.mutate({ id: editingTemplate.id, data: payload })
    } else {
      createTemplateMutation.mutate(payload)
    }
  }

  const sortedTemplates = [...(selectedCategory?.templates ?? [])].sort((a, b) => a.order - b.order || a.title.localeCompare(b.title))

  return (
    <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
      <div className="space-y-2">
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={() => setCategoryDialogOpen(true)}
          disabled={createCategoryMutation.isPending}
        >
          <PlusIcon className="h-4 w-4" />
          Добавить раздел
        </Button>
        <div className="space-y-1">
          {isLoading ? (
            <div className="rounded-md border p-4 text-sm text-muted-foreground">Загрузка...</div>
          ) : categories.length === 0 ? (
            <div className="rounded-md border p-4 text-sm text-muted-foreground">Разделы пока не созданы</div>
          ) : (
            categories.map((category) => (
              <button
                key={category.id}
                type="button"
                onClick={() => setSelectedCategoryId(category.id)}
                className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors ${
                  selectedCategory?.id === category.id
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-muted'
                }`}
              >
                <span className="truncate">{category.name}</span>
                <span className="text-xs opacity-75">{category.templates.length}</span>
              </button>
            ))
          )}
        </div>
      </div>

      <div className="min-w-0 space-y-4">
        {selectedCategory ? (
          <>
            <div className="flex flex-col gap-3 rounded-md border bg-background p-4 sm:flex-row sm:items-end">
              <div className="min-w-0 flex-1 space-y-1.5">
                <Label>Раздел</Label>
                <Input value={categoryName} onChange={(event) => setCategoryName(event.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => updateCategoryMutation.mutate({ id: selectedCategory.id, name: categoryName.trim() || selectedCategory.name })}
                  disabled={updateCategoryMutation.isPending}
                >
                  Сохранить
                </Button>
                <Button variant="outline" onClick={openCreateTemplate}>
                  <PlusIcon className="h-4 w-4" />
                  Шаблон
                </Button>
                <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => setCategoryDeleteTarget(selectedCategory)}>
                  <Trash2Icon className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {sortedTemplates.length === 0 ? (
              <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
                В этом разделе пока нет шаблонов
              </div>
            ) : (
              <div className="grid gap-3">
                {sortedTemplates.map((template) => (
                  <div key={template.id} className="rounded-md border bg-background p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold">{template.title}</h3>
                          <Badge variant="secondary">{REPLY_TEMPLATE_CHANNEL_LABELS[template.channel]}</Badge>
                          {!template.is_active ? <Badge variant="outline">Выключен</Badge> : null}
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{template.text}</p>
                        {template.tags.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {template.tags.map((tag) => (
                              <Badge key={tag} variant="outline" className="text-[10px]">{tag}</Badge>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEditTemplate(template)} aria-label="Редактировать шаблон">
                          <PencilIcon className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setTemplateDeleteTarget(template)}
                          aria-label="Удалить шаблон"
                        >
                          <Trash2Icon className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            Добавьте первый раздел шаблонов
          </div>
        )}
      </div>

      <Dialog open={templateDialogOpen} onOpenChange={setTemplateDialogOpen}>
        <DialogContent className="max-w-[95vw] sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editingTemplate ? 'Редактировать шаблон' : 'Новый шаблон'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Название</Label>
              <Input
                value={templateForm.title}
                onChange={(event) => setTemplateForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="Например: Уточнить даты"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Канал</Label>
              <Select
                value={templateForm.channel}
                onValueChange={(value) => setTemplateForm((current) => ({ ...current, channel: value as ReplyTemplateChannel }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(REPLY_TEMPLATE_CHANNEL_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Текст</Label>
              <Textarea
                value={templateForm.text}
                onChange={(event) => setTemplateForm((current) => ({ ...current, text: event.target.value }))}
                placeholder="Здравствуйте! Подскажите, пожалуйста, даты заезда и выезда..."
                rows={6}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Теги</Label>
              <Input
                value={templateForm.tags}
                onChange={(event) => setTemplateForm((current) => ({ ...current, tags: event.target.value }))}
                placeholder="бронь, оплата, даты"
              />
            </div>
            <label className="flex items-center justify-between rounded-md border p-3 text-sm">
              <span>Активен</span>
              <Switch
                checked={templateForm.is_active}
                onCheckedChange={(checked) => setTemplateForm((current) => ({ ...current, is_active: checked }))}
              />
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTemplateDialogOpen(false)}>Отмена</Button>
            <Button onClick={handleTemplateSubmit} disabled={createTemplateMutation.isPending || updateTemplateMutation.isPending}>
              Сохранить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
        <DialogContent className="max-w-[95vw] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Новый раздел шаблонов</DialogTitle>
            <DialogDescription>
              Раздел поможет менеджерам быстрее находить нужные ответы в чате.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5 py-2">
            <Label>Название раздела</Label>
            <Input
              value={newCategoryName}
              onChange={(event) => {
                setNewCategoryName(event.target.value)
                setCategoryError('')
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  handleCreateCategory()
                }
              }}
              placeholder="Например: Бронирование, Оплата, Заезд"
              autoFocus
            />
            {categoryError ? (
              <p className="text-sm text-destructive">{categoryError}</p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCategoryDialogOpen(false)}>Отмена</Button>
            <Button onClick={handleCreateCategory} disabled={createCategoryMutation.isPending}>
              {createCategoryMutation.isPending ? 'Добавляем...' : 'Добавить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!categoryDeleteTarget} onOpenChange={(open) => { if (!open) setCategoryDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить раздел?</AlertDialogTitle>
            <AlertDialogDescription>
              Все шаблоны внутри раздела тоже будут удалены.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => categoryDeleteTarget && deleteCategoryMutation.mutate(categoryDeleteTarget.id)}
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!templateDeleteTarget} onOpenChange={(open) => { if (!open) setTemplateDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить шаблон?</AlertDialogTitle>
            <AlertDialogDescription>
              Шаблон исчезнет из быстрых ответов в коммуникациях.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => templateDeleteTarget && deleteTemplateMutation.mutate(templateDeleteTarget.id)}
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ── Room Combinations Section ─────────────────────────────────────────────────

function guestLabel(n: number): string {
  if (n === 1) return '1 Гость'
  if (n >= 2 && n <= 4) return `${n} Гостя`
  return `${n} Гостей`
}

function CombinationNoteCell({
  guestCount,
  combinationIndex,
  initialNote,
  canEdit,
}: {
  guestCount: number
  combinationIndex: number
  initialNote: string
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState(initialNote)

  async function handleBlur() {
    if (!canEdit) return
    if (value === initialNote) return
    try {
      await saveRoomCombinationNote(guestCount, combinationIndex, value)
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
    } catch {
      toast.error('Не удалось сохранить примечание')
    }
  }

  return (
    canEdit ? (
      <input
        className="w-full bg-transparent text-sm text-muted-foreground outline-none border-b border-transparent focus:border-border focus:text-foreground placeholder:text-muted-foreground/50 py-0.5"
        value={value}
        placeholder="Добавить примечание…"
        onChange={(e) => setValue(e.target.value)}
        onBlur={handleBlur}
      />
    ) : (
      <span className="block text-sm text-muted-foreground">{initialNote || '—'}</span>
    )
  )
}

function AddCombinationDialog({
  open,
  onOpenChange,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [guestCount, setGuestCount] = useState('2')
  const [rooms, setRooms] = useState<string[]>([])
  const [combinationType, setCombinationType] = useState<'Основной' | 'Альтернатива' | 'Семейный'>('Альтернатива')
  const [note, setNote] = useState('')
  const [roomSelectKey, setRoomSelectKey] = useState(0)
  const [isPending, setIsPending] = useState(false)

  const { data: roomTypesData } = useQuery({
    queryKey: ['room-combination-room-types'],
    queryFn: fetchRoomCombinationRoomTypes,
    enabled: open,
  })
  const roomTypes = roomTypesData?.results ?? []

  function addRoom(roomType: string) {
    setRooms((prev) => [...prev, roomType])
    setRoomSelectKey((k) => k + 1)
  }

  function removeRoom(idx: number) {
    setRooms((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleSave() {
    if (rooms.length === 0) {
      toast.error('Добавьте хотя бы один номер')
      return
    }
    setIsPending(true)
    try {
      await createCustomCombination({
        guest_count: Number(guestCount),
        rooms,
        combination_type: combinationType,
        note,
      })
      toast.success('Комбинация добавлена')
      setRooms([])
      setCombinationType('Альтернатива')
      setNote('')
      setRoomSelectKey((k) => k + 1)
      onSaved()
    } catch {
      toast.error('Не удалось добавить комбинацию')
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[95vw] sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Добавить комбинацию</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Для гостей</label>
            <Select value={guestCount} onValueChange={setGuestCount}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {guestLabel(n)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Номера</label>
            <Select key={roomSelectKey} onValueChange={addRoom}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите номер для добавления…" />
              </SelectTrigger>
              <SelectContent>
                {roomTypes.map((rt) => (
                  <SelectItem key={rt} value={rt}>
                    {rt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {rooms.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {rooms.map((room, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-muted text-xs"
                  >
                    {room}
                    <button
                      type="button"
                      onClick={() => removeRoom(idx)}
                      className="text-muted-foreground hover:text-foreground ml-0.5"
                    >
                      <XIcon className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Тип</label>
            <Select
              value={combinationType}
              onValueChange={(v) => setCombinationType(v as 'Основной' | 'Альтернатива' | 'Семейный')}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Основной">Основной</SelectItem>
                <SelectItem value="Альтернатива">Альтернатива</SelectItem>
                <SelectItem value="Семейный">Семейный (только для гостей с детьми)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-muted-foreground">Примечания (необязательно)</label>
            <Input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Добавить примечание…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Закрыть
          </Button>
          <Button onClick={handleSave} disabled={isPending || rooms.length === 0}>
            {isPending ? <Loader2Icon className="h-4 w-4 mr-1.5 animate-spin" /> : null}
            Добавить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function RoomCombinationsSection() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canEditPricing = canEditHotelPricing(user)
  const [addOpen, setAddOpen] = useState(false)
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['room-combinations'],
    queryFn: () => fetchRoomCombinations(),
  })

  const groups: RoomCombinationGroup[] = data?.results ?? []

  async function handleTypeChange(
    guestCount: number,
    comboIndex: number,
    newType: 'Основной' | 'Альтернатива' | 'Семейный',
  ) {
    if (!canEditPricing) return
    queryClient.setQueryData(
      ['room-combinations'],
      (old: { results: RoomCombinationGroup[] } | undefined) => {
        if (!old) return old
        return {
          ...old,
          results: old.results.map((group) => {
            if (group.guest_count !== guestCount) return group
            return {
              ...group,
              combinations: group.combinations.map((combo) => ({
                ...combo,
                type:
                  combo.index === comboIndex
                    ? newType
                    : newType === 'Основной' && combo.type !== 'Семейный'
                    ? 'Альтернатива'
                    : combo.type,
              })),
            }
          }),
        }
      },
    )
    try {
      await saveCombinationType(guestCount, comboIndex, newType)
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
    } catch {
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
      toast.error('Не удалось сохранить тип')
    }
  }

  async function handleDelete(combo: { id: number | null; is_custom: boolean; index: number }, guestCount: number) {
    if (!canEditPricing) return
    queryClient.setQueryData(
      ['room-combinations'],
      (old: { results: RoomCombinationGroup[] } | undefined) => {
        if (!old) return old
        return {
          ...old,
          results: old.results.map((group) =>
            group.guest_count !== guestCount ? group : {
              ...group,
              combinations: group.combinations.filter((c) => c.index !== combo.index),
            }
          ),
        }
      },
    )
    try {
      if (combo.is_custom && combo.id != null) {
        await deleteCustomCombination(combo.id)
      } else {
        await hideAutoCombination(guestCount, combo.index)
      }
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
    } catch {
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
      toast.error('Не удалось удалить комбинацию')
    }
  }

  return (
    <div className="space-y-4 mt-8">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-base font-semibold">Комбинации номеров</h3>
          <p className="text-sm text-muted-foreground">
            Автоматически рассчитывается на основе текущего прайса (сегодняшние тарифы)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching
              ? <Loader2Icon className="h-4 w-4 mr-1.5 animate-spin" />
              : <RefreshCwIcon className="h-4 w-4 mr-1.5" />}
            Обновить
          </Button>
          {canEditPricing ? (
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <PlusIcon className="h-4 w-4 mr-1.5" />
              Добавить комбинацию
            </Button>
          ) : null}
        </div>
      </div>

      {canEditPricing ? (
        <AddCombinationDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ['room-combinations'] })}
        />
      ) : null}

      {isLoading ? (
        <div className="text-sm text-muted-foreground py-4">Загрузка...</div>
      ) : groups.length === 0 ? (
        <div className="text-sm text-muted-foreground py-4">Нет данных</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm min-w-[960px]">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">Комбинация</th>
                <th className="px-3 py-2 text-center font-medium text-muted-foreground whitespace-nowrap">Гостей</th>
                <th className="px-3 py-2 text-center font-medium text-muted-foreground whitespace-nowrap">Кол-во номеров</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">Тип</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground whitespace-nowrap">Стандарт</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground whitespace-nowrap">С завтраком</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground whitespace-nowrap">Полупансион</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground whitespace-nowrap">Полный пансион</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Примечания</th>
                {canEditPricing ? <th className="w-8" /> : null}
              </tr>
            </thead>
            <tbody>
              {groups.flatMap((group) =>
                group.combinations.map((combo) => (
                  <tr
                    key={`${group.guest_count}-${combo.index}`}
                    className={cn(
                      'border-b last:border-b-0 transition-colors',
                      combo.available
                        ? 'hover:bg-muted/30'
                        : 'opacity-50 bg-muted/20'
                    )}
                  >
                    <td className="px-3 py-2.5 font-medium">
                      <span className="inline-flex items-center gap-1.5">
                        {combo.available ? (
                          combo.rooms.join(' + ')
                        ) : (
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="cursor-help text-muted-foreground line-through">
                                  {combo.rooms.join(' + ')}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>
                                Нет тарифа в прайсе для этого номера
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        )}
                        {combo.is_custom && (
                          <span className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground font-normal leading-none">
                            своя
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-center tabular-nums font-medium">{group.guest_count}</td>
                    <td className="px-3 py-2.5 text-center tabular-nums">{combo.room_count}</td>
                    <td className="px-3 py-1.5">
                      {canEditPricing ? (
                        <Select
                          value={combo.type}
                          onValueChange={(v) =>
                            handleTypeChange(
                              group.guest_count,
                              combo.index,
                              v as 'Основной' | 'Альтернатива' | 'Семейный',
                            )
                          }
                        >
                          <SelectTrigger
                            className={cn(
                              'h-7 text-xs w-[140px] font-medium',
                              combo.type === 'Основной'
                                ? 'text-blue-600 border-blue-200 bg-blue-50 hover:bg-blue-100'
                                : combo.type === 'Семейный'
                                ? 'text-violet-600 border-violet-200 bg-violet-50 hover:bg-violet-100'
                                : 'text-muted-foreground',
                            )}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Основной" className="text-xs text-blue-600">Основной</SelectItem>
                            <SelectItem value="Альтернатива" className="text-xs">Альтернатива</SelectItem>
                            <SelectItem value="Семейный" className="text-xs text-violet-600">Семейный</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : (
                        <span className="inline-flex h-7 items-center rounded-md border bg-muted/30 px-2.5 text-xs font-medium text-muted-foreground">
                          {combo.type}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {combo.prices?.standard != null ? combo.prices.standard.toLocaleString('ru-RU') : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {combo.prices?.with_breakfast != null ? combo.prices.with_breakfast.toLocaleString('ru-RU') : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {combo.prices?.half_board != null ? combo.prices.half_board.toLocaleString('ru-RU') : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {combo.prices?.full_board != null ? combo.prices.full_board.toLocaleString('ru-RU') : '—'}
                    </td>
                    <td className="px-3 py-2.5 min-w-[160px]">
                      <CombinationNoteCell
                        guestCount={group.guest_count}
                        combinationIndex={combo.index}
                        initialNote={combo.note}
                        canEdit={canEditPricing}
                      />
                    </td>
                    {canEditPricing ? (
                      <td className="px-2 py-2.5 text-center">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Удалить"
                          className="h-7 w-7 text-muted-foreground hover:text-destructive"
                          onClick={() => handleDelete(combo, group.guest_count)}
                        >
                          <Trash2Icon className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    ) : null}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Pricing Tab ───────────────────────────────────────────────────────────────

const WEEKDAYS_RU = [
  'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье',
]

const EMPTY_PRICING: RoomPricingFormData = {
  kategoria_nomera: '',
  kolichestvo_chelovek: 2,
  guest_type: 'any',
  deystvitelno_s: null,
  deystvitelno_do: null,
  dni_nedeli: [],
  standartny_tarif: null,
  s_zavtrakom: null,
  polupansion: null,
  polny_pansion: null,
}

function formatPricingDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const [y, m, d] = dateStr.split('-')
  return `${d}.${m}.${y}`
}

function formatPrice(val: string | null): string {
  if (val === null || val === undefined || val === '') return '—'
  return Number(val).toLocaleString('ru-RU')
}

function PricingTab() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canEditPricing = canEditHotelPricing(user)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRow, setEditingRow] = useState<RoomPricing | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<RoomPricing | null>(null)
  const [form, setForm] = useState<RoomPricingFormData>(EMPTY_PRICING)
  const [isUploading, setIsUploading] = useState(false)
  const excelInputRef = useRef<HTMLInputElement>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc' | null>(null)

  function cycleSort() {
    setSortDir((d) => (d === null ? 'asc' : d === 'asc' ? 'desc' : null))
  }
  type UploadResult = { deleted: number; created: number; updated: number; skipped: number; skipped_details: { row: number; reason: string }[] }
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadResultOpen, setUploadResultOpen] = useState(false)

  async function handleExcelUpload(e: React.ChangeEvent<HTMLInputElement>) {
    if (!canEditPricing) return
    const file = e.target.files?.[0]
    if (!excelInputRef.current) return
    excelInputRef.current.value = ''
    if (!file) return
    setIsUploading(true)
    setUploadResult(null)
    setUploadError(null)
    try {
      const result = await uploadRoomPricingExcel(file)
      queryClient.invalidateQueries({ queryKey: ['room-pricing'] })
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
      setUploadResult(result)
      setUploadResultOpen(true)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Не удалось загрузить файл')
      setUploadResultOpen(true)
    } finally {
      setIsUploading(false)
    }
  }

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['room-pricing'],
    queryFn: fetchRoomPricing,
  })

  const sortedRows = sortDir === null
    ? rows
    : [...rows].sort((a, b) =>
        sortDir === 'asc'
          ? a.kolichestvo_chelovek - b.kolichestvo_chelovek
          : b.kolichestvo_chelovek - a.kolichestvo_chelovek
      )

  // Color rooms and date groups — assigned in stable insertion order from `rows`
  const { roomTypeColorMap, dateGroupAltMap } = useMemo(() => {
    const TYPE_COLORS = ['#3b82f6', '#10b981', '#f97316', '#a855f7', '#f43f5e', '#14b8a6', '#f59e0b', '#6366f1']
    const roomTypeColorMap = new Map<string, string>()
    const dateGroupAltMap = new Map<string, boolean>()
    let typeIdx = 0
    let dateGroupIdx = 0
    for (const row of rows) {
      if (!roomTypeColorMap.has(row.kategoria_nomera)) {
        roomTypeColorMap.set(row.kategoria_nomera, TYPE_COLORS[typeIdx % TYPE_COLORS.length])
        typeIdx++
      }
      const groupKey = `${row.deystvitelno_s ?? ''}|${row.deystvitelno_do ?? ''}|${(row.dni_nedeli ?? []).join(',')}`
      if (!dateGroupAltMap.has(groupKey)) {
        dateGroupAltMap.set(groupKey, dateGroupIdx % 2 === 1)
        dateGroupIdx++
      }
    }
    return { roomTypeColorMap, dateGroupAltMap }
  }, [rows])

  const createMutation = useMutation({
    mutationFn: createRoomPricing,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['room-pricing'] })
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
      setDialogOpen(false)
      toast.success('Строка добавлена')
    },
    onError: () => toast.error('Не удалось сохранить'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: RoomPricingFormData }) =>
      updateRoomPricing(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['room-pricing'] })
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
      setDialogOpen(false)
      toast.success('Строка обновлена')
    },
    onError: () => toast.error('Не удалось сохранить'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteRoomPricing(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['room-pricing'] })
      queryClient.invalidateQueries({ queryKey: ['room-combinations'] })
      setDeleteTarget(null)
      toast.success('Строка удалена')
    },
    onError: () => toast.error('Не удалось удалить'),
  })

  function openAdd() {
    if (!canEditPricing) return
    setEditingRow(null)
    setForm(EMPTY_PRICING)
    setDialogOpen(true)
  }

  function openEdit(row: RoomPricing) {
    if (!canEditPricing) return
    setEditingRow(row)
    setForm({
      kategoria_nomera: row.kategoria_nomera,
      kolichestvo_chelovek: row.kolichestvo_chelovek,
      guest_type: row.guest_type ?? 'any',
      deystvitelno_s: row.deystvitelno_s,
      deystvitelno_do: row.deystvitelno_do,
      dni_nedeli: row.dni_nedeli ?? [],
      standartny_tarif: row.standartny_tarif,
      s_zavtrakom: row.s_zavtrakom,
      polupansion: row.polupansion,
      polny_pansion: row.polny_pansion,
    })
    setDialogOpen(true)
  }

  function handleSave() {
    if (!canEditPricing) return
    if (!form.kategoria_nomera.trim()) {
      toast.error('Укажите категорию номера')
      return
    }
    const payload: RoomPricingFormData = {
      ...form,
      standartny_tarif: form.standartny_tarif === '' ? null : form.standartny_tarif,
      s_zavtrakom: form.s_zavtrakom === '' ? null : form.s_zavtrakom,
      polupansion: form.polupansion === '' ? null : form.polupansion,
      polny_pansion: form.polny_pansion === '' ? null : form.polny_pansion,
    }
    if (editingRow) {
      updateMutation.mutate({ id: editingRow.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  function toggleDay(day: string) {
    setForm((f) => ({
      ...f,
      dni_nedeli: f.dni_nedeli.includes(day)
        ? f.dni_nedeli.filter((d) => d !== day)
        : [...f.dni_nedeli, day],
    }))
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-4">
      <input
        ref={excelInputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={handleExcelUpload}
      />
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-base font-semibold">Прайс-лист</h3>
          <p className="text-sm text-muted-foreground">
            Цены по категориям номеров. ИИ будет использовать только эти данные.
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Валюта: <span className="font-medium text-foreground">KGS</span> (Кыргызский сом)
          </p>
        </div>
        {canEditPricing ? (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => excelInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? (
                <Loader2Icon className="h-4 w-4 mr-1.5 animate-spin" />
              ) : (
                <UploadCloudIcon className="h-4 w-4 mr-1.5" />
              )}
              Загрузить Excel
            </Button>
            <Button onClick={openAdd} size="sm">
              <PlusIcon className="h-4 w-4 mr-1.5" />
              Добавить строку
            </Button>
          </div>
        ) : null}
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm min-w-[900px]">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">Категория номера</th>
              <th className="px-3 py-2.5 text-center font-medium text-muted-foreground whitespace-nowrap">
                <button
                  onClick={cycleSort}
                  className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                >
                  Макс. чел.
                  {sortDir === 'asc' && <ArrowUpIcon className="h-3 w-3" />}
                  {sortDir === 'desc' && <ArrowDownIcon className="h-3 w-3" />}
                </button>
              </th>
              <th className="px-3 py-2.5 text-center font-medium text-muted-foreground whitespace-nowrap">Тип гостей</th>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">Действ. с</th>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">Действ. до</th>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">Дни недели</th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground whitespace-nowrap">Стандарт</th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground whitespace-nowrap">С завтраком</th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground whitespace-nowrap">Полупансион</th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground whitespace-nowrap">Полный пансион</th>
              {canEditPricing ? (
                <th className="px-3 py-2.5 text-center font-medium text-muted-foreground whitespace-nowrap">Действия</th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={canEditPricing ? 11 : 10} className="px-3 py-8 text-center text-muted-foreground">
                  Загрузка...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={canEditPricing ? 11 : 10} className="px-3 py-8 text-center text-muted-foreground">
                  {canEditPricing ? 'Прайс-лист пуст. Добавьте первую строку.' : 'Прайс-лист пуст.'}
                </td>
              </tr>
            ) : (
              sortedRows.map((row, idx) => {
                const borderColor = roomTypeColorMap.get(row.kategoria_nomera) ?? '#e4e4e7'
                const groupKey = `${row.deystvitelno_s ?? ''}|${row.deystvitelno_do ?? ''}|${(row.dni_nedeli ?? []).join(',')}`
                const isAlt = dateGroupAltMap.get(groupKey) ?? false
                const isLastRow = idx === sortedRows.length - 1
                const nextGroupKey = !isLastRow
                  ? `${sortedRows[idx + 1].deystvitelno_s ?? ''}|${sortedRows[idx + 1].deystvitelno_do ?? ''}|${(sortedRows[idx + 1].dni_nedeli ?? []).join(',')}`
                  : null
                const isGroupEnd = !isLastRow && groupKey !== nextGroupKey
                return (
                  <tr
                    key={row.id}
                    className={cn(
                      'transition-colors border-l-[3px]',
                      isLastRow
                        ? ''
                        : isGroupEnd
                        ? 'border-b-2 border-b-zinc-400/60 dark:border-b-zinc-500/60'
                        : 'border-b',
                      isAlt
                        ? 'bg-zinc-50 dark:bg-zinc-900/40 hover:bg-zinc-100 dark:hover:bg-zinc-800/60'
                        : 'hover:bg-muted/30'
                    )}
                    style={{ borderLeftColor: borderColor }}
                  >
                  <td className="px-3 py-2.5 font-medium">{row.kategoria_nomera}</td>
                  <td className="px-3 py-2.5 text-center">{row.kolichestvo_chelovek}</td>
                  <td className="px-3 py-2.5 text-center">
                    {row.guest_type === 'family' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-violet-100 text-violet-700 border border-violet-200">
                        Семейный
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600 border border-zinc-200">
                        Любой
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{formatPricingDate(row.deystvitelno_s)}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{formatPricingDate(row.deystvitelno_do)}</td>
                  <td className="px-3 py-2.5 text-muted-foreground max-w-[160px]">
                    {row.dni_nedeli && row.dni_nedeli.length > 0
                      ? row.dni_nedeli.map((d) => d.slice(0, 2)).join(', ')
                      : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatPrice(row.standartny_tarif)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatPrice(row.s_zavtrakom)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatPrice(row.polupansion)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatPrice(row.polny_pansion)}</td>
                  {canEditPricing ? (
                    <td className="px-3 py-2.5 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          aria-label="Edit"
                          onClick={() => openEdit(row)}
                        >
                          <PencilIcon className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          aria-label="Delete"
                          onClick={() => setDeleteTarget(row)}
                        >
                          <Trash2Icon className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  ) : null}
                </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="space-y-2">
        <div className="rounded-lg border border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/30 p-3 text-sm text-blue-800 dark:text-blue-200">
          <span className="font-medium">Правило для детей:</span>{' '}
          Один ребёнок до 6 лет не считается. При двух детях до 6 лет — рекомендовать семейный номер.
        </div>
        <p className="text-xs text-muted-foreground px-1">
          <span className="font-medium">Макс. чел.</span> — максимальное количество гостей, не считая детей до 6 лет.
        </p>
      </div>

      {/* Add / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-[95vw] md:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingRow ? 'Редактировать строку' : 'Добавить строку'}</DialogTitle>
          </DialogHeader>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-2">
            {/* Категория номера */}
            <div className="space-y-1.5">
              <Label>Категория номера <span className="text-destructive">*</span></Label>
              <Input
                value={form.kategoria_nomera}
                onChange={(e) => setForm((f) => ({ ...f, kategoria_nomera: e.target.value }))}
                placeholder="Стандарт, Комфорт, Семейный..."
              />
            </div>

            {/* Макс. чел. */}
            <div className="space-y-1.5">
              <Label>Макс. чел. <span className="text-destructive">*</span></Label>
              <Select
                value={String(form.kolichestvo_chelovek)}
                onValueChange={(v) => setForm((f) => ({ ...f, kolichestvo_chelovek: Number(v) }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4].map((n) => (
                    <SelectItem key={n} value={String(n)}>{n} чел.</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Тип гостей */}
            <div className="space-y-1.5 md:col-span-2">
              <Label>Тип гостей</Label>
              <Select
                value={form.guest_type ?? 'any'}
                onValueChange={(v) => setForm((f) => ({ ...f, guest_type: v as 'any' | 'family' }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Любой — стандартные и комфорт номера (рекомендуется всем гостям)</SelectItem>
                  <SelectItem value="family">Семейный — только для гостей с детьми</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Семейные номера ИИ предлагает только когда гость подтверждает наличие детей.
              </p>
            </div>

            {/* Действительно с */}
            <div className="space-y-1.5">
              <Label>Действительно с</Label>
              <div className="flex gap-1">
                <div className="flex-1">
                  <DatePicker
                    value={form.deystvitelno_s ?? undefined}
                    onChange={(d) => setForm((f) => ({ ...f, deystvitelno_s: d ?? null }))}
                    placeholder="Не ограничено"
                  />
                </div>
                {form.deystvitelno_s ? (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-10 w-10 shrink-0"
                    onClick={() => setForm((f) => ({ ...f, deystvitelno_s: null }))}
                  >
                    <XCircleIcon className="h-4 w-4 text-muted-foreground" />
                  </Button>
                ) : null}
              </div>
            </div>

            {/* Действительно до */}
            <div className="space-y-1.5">
              <Label>Действительно до</Label>
              <div className="flex gap-1">
                <div className="flex-1">
                  <DatePicker
                    value={form.deystvitelno_do ?? undefined}
                    onChange={(d) => setForm((f) => ({ ...f, deystvitelno_do: d ?? null }))}
                    placeholder="Не ограничено"
                  />
                </div>
                {form.deystvitelno_do ? (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-10 w-10 shrink-0"
                    onClick={() => setForm((f) => ({ ...f, deystvitelno_do: null }))}
                  >
                    <XCircleIcon className="h-4 w-4 text-muted-foreground" />
                  </Button>
                ) : null}
              </div>
            </div>

            {/* Дни недели */}
            <div className="space-y-1.5 md:col-span-2">
              <Label>Дни недели (оставьте пустым — применяется ко всем дням)</Label>
              <div className="flex flex-wrap gap-2">
                {WEEKDAYS_RU.map((day) => (
                  <label
                    key={day}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 rounded-md border cursor-pointer text-sm select-none transition-colors',
                      form.dni_nedeli.includes(day)
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-background hover:bg-muted border-input'
                    )}
                  >
                    <Checkbox
                      checked={form.dni_nedeli.includes(day)}
                      onCheckedChange={() => toggleDay(day)}
                      className="hidden"
                    />
                    {day.slice(0, 2)}
                  </label>
                ))}
              </div>
            </div>

            {/* Price fields */}
            {([
              ['standartny_tarif', 'Стандартный тариф (KGS)'],
              ['s_zavtrakom', 'С завтраком (KGS)'],
              ['polupansion', 'Полупансион (KGS)'],
              ['polny_pansion', 'Полный пансион (KGS)'],
            ] as const).map(([field, label]) => (
              <div key={field} className="space-y-1.5">
                <Label>{label}</Label>
                <Input
                  type="number"
                  min={0}
                  value={form[field] ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      [field]: e.target.value === '' ? null : e.target.value,
                    }))
                  }
                  placeholder="—"
                />
              </div>
            ))}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? <Loader2Icon className="h-4 w-4 mr-2 animate-spin" /> : null}
              Сохранить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upload result dialog */}
      <Dialog open={uploadResultOpen} onOpenChange={setUploadResultOpen}>
        <DialogContent className="max-w-[95vw] md:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {uploadError ? 'Ошибка загрузки' : 'Результат загрузки Excel'}
            </DialogTitle>
          </DialogHeader>
          {uploadError ? (
            <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
              {uploadError}
            </div>
          ) : uploadResult ? (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-3">
                <div className="rounded-lg border bg-muted/40 p-3 text-center">
                  <p className="text-2xl font-bold text-destructive">{uploadResult.deleted}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">удалено</p>
                </div>
                <div className="rounded-lg border bg-muted/40 p-3 text-center">
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">{uploadResult.created}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">добавлено</p>
                </div>
                <div className="rounded-lg border bg-muted/40 p-3 text-center">
                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{uploadResult.updated ?? 0}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">обновлено</p>
                </div>
                <div className="rounded-lg border bg-muted/40 p-3 text-center">
                  <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{uploadResult.skipped}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">пропущено</p>
                </div>
              </div>
              {uploadResult.skipped_details.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-sm font-medium text-muted-foreground">Пропущенные строки:</p>
                  <div className="max-h-48 overflow-y-auto rounded-lg border divide-y text-sm">
                    {uploadResult.skipped_details.map((s) => (
                      <div key={s.row} className="flex items-start gap-3 px-3 py-2">
                        <span className="text-muted-foreground shrink-0">Стр. {s.row}</span>
                        <span>{s.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {uploadResult.created === 0 && uploadResult.skipped > 0 && (
                <p className="text-sm text-amber-600 dark:text-amber-400">
                  Ни одна строка не была импортирована. Проверьте названия столбцов.
                </p>
              )}
            </div>
          ) : null}
          <DialogFooter>
            <Button onClick={() => setUploadResultOpen(false)}>Закрыть</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить строку?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget
                ? `${deleteTarget.kategoria_nomera} × ${deleteTarget.kolichestvo_chelovek} чел. будет удалена из прайс-листа.`
                : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <RoomCombinationsSection />
    </div>
  )
}

// ── Social Content Review ─────────────────────────────────────────────────────

const SOCIAL_TYPE_LABELS: Record<SocialContentType, string> = {
  post: 'Пост',
  reel: 'Рилс',
  story: 'Сторис',
  highlight: 'Актуальное',
  event: 'Ивент',
  unknown: 'Неизвестно',
}

const SOCIAL_STATUS_LABELS: Record<SocialContentStatus, string> = {
  active: 'Активно',
  expired: 'Истекло',
  archived: 'Архив',
  deleted: 'Удалено',
}

const SOCIAL_REVIEW_LABELS: Record<SocialContentReviewStatus, string> = {
  auto: 'Авто',
  needs_review: 'Проверить',
  reviewed: 'Проверено',
}

interface SocialContentFormState {
  title: string
  caption: string
  content_type: SocialContentType
  status: SocialContentStatus
  review_status: SocialContentReviewStatus
  linked_media_item: string
  category: string
  room_category: string
  playbook_keys_text: string
  reply_guidance: string
  manager_notes: string
}

function SocialContentTab({ mediaItems }: { mediaItems: HotelMediaItem[] }) {
  const queryClient = useQueryClient()
  const [needsReviewOnly, setNeedsReviewOnly] = useState(true)
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<SocialContentItem | null>(null)
  const [form, setForm] = useState<SocialContentFormState | null>(null)

  const { data: socialItems = [], isLoading } = useQuery({
    queryKey: ['social-content', needsReviewOnly, search],
    queryFn: () => fetchSocialContentItems({
      needs_review: needsReviewOnly,
      search: search.trim() || undefined,
    }),
  })

  const syncMutation = useMutation({
    mutationFn: syncInstagramSocialContent,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['social-content'] })
      toast.success(`Синк завершен: посты/рилсы ${result.items_synced}, сторис ${result.stories_synced}`)
      if (result.errors.length > 0) toast.warning(result.errors[0])
    },
    onError: () => toast.error('Не удалось синхронизировать Instagram'),
  })

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!editing || !form) throw new Error('No item selected')
      const playbookKeys = form.playbook_keys_text
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean)
      return updateSocialContentItem(editing.id, {
        title: form.title,
        caption: form.caption,
        content_type: form.content_type,
        status: form.status,
        review_status: form.review_status,
        linked_media_item: form.linked_media_item === 'none' ? null : Number(form.linked_media_item),
        category: form.category === 'none' ? '' : form.category,
        room_category: form.room_category === 'none' ? null : form.room_category as RoomCategory,
        playbook_keys: playbookKeys,
        reply_guidance: form.reply_guidance,
        manager_notes: form.manager_notes,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social-content'] })
      toast.success('Соцконтент обновлен')
      setEditing(null)
      setForm(null)
    },
    onError: () => toast.error('Не удалось сохранить соцконтент'),
  })

  const reviewedMutation = useMutation({
    mutationFn: (id: number) => markSocialContentReviewed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social-content'] })
      toast.success('Помечено как проверенное')
    },
    onError: () => toast.error('Не удалось обновить статус'),
  })

  const rebuildMutation = useMutation({
    mutationFn: (id: number) => rebuildSocialContentFingerprints(id),
    onSuccess: (result) => toast.success(`Отпечатки пересобраны: ${result.fingerprints_created}`),
    onError: () => toast.error('Не удалось пересобрать отпечатки'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteSocialContentItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social-content'] })
      toast.success('Соцконтент удален')
    },
    onError: () => toast.error('Не удалось удалить соцконтент'),
  })

  function openEdit(item: SocialContentItem) {
    setEditing(item)
    setForm({
      title: item.title,
      caption: item.caption,
      content_type: item.content_type,
      status: item.status,
      review_status: item.review_status,
      linked_media_item: item.linked_media_item ? String(item.linked_media_item) : 'none',
      category: item.category || 'none',
      room_category: item.room_category || 'none',
      playbook_keys_text: item.playbook_keys.join(', '),
      reply_guidance: item.reply_guidance,
      manager_notes: item.manager_notes,
    })
  }

  const categoryLabel = (value: string) => CATEGORIES.find((c) => c.value === value)?.label || value || 'Не задано'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по сторис, постам, заметкам..."
              className="pl-8 w-72"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox checked={needsReviewOnly} onCheckedChange={(v) => setNeedsReviewOnly(Boolean(v))} />
            Только требующие проверки
          </label>
        </div>
        <Button onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
          {syncMutation.isPending ? <Loader2Icon className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCwIcon className="h-4 w-4 mr-2" />}
          Синхронизировать Instagram
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => <div key={i} className="h-48 rounded-lg border bg-muted animate-pulse" />)}
        </div>
      ) : socialItems.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          Нет соцконтента для выбранного фильтра. Запустите синхронизацию Instagram или дождитесь входящих ответов на сторис.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {socialItems.map((item) => {
            const preview = item.thumbnail_url || item.media_url
            const needsReview = item.review_status === 'needs_review'
            return (
              <div key={item.id} className="rounded-lg border bg-card overflow-hidden">
                <div className="aspect-video bg-muted relative">
                  {preview ? (
                    <img src={preview} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                      <InstagramIcon className="h-8 w-8" />
                    </div>
                  )}
                  <div className="absolute top-2 left-2 flex gap-1.5 flex-wrap">
                    <Badge variant={needsReview ? 'destructive' : 'secondary'}>{SOCIAL_REVIEW_LABELS[item.review_status]}</Badge>
                    <Badge variant="secondary">{SOCIAL_TYPE_LABELS[item.content_type]}</Badge>
                  </div>
                </div>
                <div className="p-3 space-y-3">
                  <div>
                    <div className="font-medium line-clamp-1">{item.title || item.linked_media_title || item.external_id || 'Без названия'}</div>
                    <div className="text-xs text-muted-foreground line-clamp-2">{item.caption || item.manager_notes || 'Описание еще не заполнено'}</div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline">{categoryLabel(item.effective_category || item.category)}</Badge>
                    {item.effective_room_category ? <Badge variant="outline">{item.effective_room_category}</Badge> : null}
                    {item.fingerprint_count > 0 ? <Badge variant="secondary">{item.fingerprint_count} hash</Badge> : null}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <CalendarClockIcon className="h-3.5 w-3.5" />
                    {item.posted_at ? new Date(item.posted_at).toLocaleString('ru-RU') : 'Дата публикации неизвестна'}
                    <span>·</span>
                    {SOCIAL_STATUS_LABELS[item.status]}
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Button size="sm" variant="outline" onClick={() => openEdit(item)}>
                      <PencilIcon className="h-3.5 w-3.5 mr-1.5" />
                      Настроить
                    </Button>
                    {needsReview ? (
                      <Button size="sm" variant="outline" onClick={() => reviewedMutation.mutate(item.id)}>
                        <CheckIcon className="h-3.5 w-3.5 mr-1.5" />
                        Проверено
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        if (confirm('Вы уверены, что хотите удалить этот элемент соцконтента?')) {
                          deleteMutation.mutate(item.id)
                        }
                      }}
                      disabled={deleteMutation.isPending}
                    >
                      {deleteMutation.isPending ? <Loader2Icon className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Trash2Icon className="h-3.5 w-3.5 mr-1.5" />}
                      Удалить
                    </Button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Dialog open={!!editing && !!form} onOpenChange={(open) => { if (!open) { setEditing(null); setForm(null) } }}>
        <DialogContent className="max-w-[95vw] md:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Настройка соцконтента</DialogTitle>
            <DialogDescription>
              Эти поля помогают AI понять, что изображено в сторис/посте и какой контекст использовать в ответе.
            </DialogDescription>
          </DialogHeader>
          {form ? (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Тип</Label>
                  <Select value={form.content_type} onValueChange={(v) => setForm((f) => f && ({ ...f, content_type: v as SocialContentType }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(SOCIAL_TYPE_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Статус</Label>
                  <Select value={form.status} onValueChange={(v) => setForm((f) => f && ({ ...f, status: v as SocialContentStatus }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(SOCIAL_STATUS_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label>Название</Label>
                <Input value={form.title} onChange={(e) => setForm((f) => f && ({ ...f, title: e.target.value }))} placeholder="Напр. Сторис про номер Комфорт" />
              </div>

              <div className="space-y-1.5">
                <Label>Связать с медиатекой отеля</Label>
                <Select value={form.linked_media_item} onValueChange={(v) => setForm((f) => f && ({ ...f, linked_media_item: v }))}>
                  <SelectTrigger><SelectValue placeholder="Не связано" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Не связано</SelectItem>
                    {mediaItems.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.title}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Тема</Label>
                  <Select value={form.category} onValueChange={(v) => setForm((f) => f && ({ ...f, category: v, room_category: v === 'rooms' ? f.room_category : 'none' }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Не задано</SelectItem>
                      {CATEGORIES.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Тип номера</Label>
                  <Select value={form.room_category} onValueChange={(v) => setForm((f) => f && ({ ...f, room_category: v }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Не задано</SelectItem>
                      <SelectItem value="standard_queen">Стандарт Квин</SelectItem>
                      <SelectItem value="standard_twin">Стандарт Твин</SelectItem>
                      <SelectItem value="comfort">Комфорт</SelectItem>
                      <SelectItem value="family">Семейный</SelectItem>
                      <SelectItem value="other">Другой</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label>Playbook keys</Label>
                <Input
                  value={form.playbook_keys_text}
                  onChange={(e) => setForm((f) => f && ({ ...f, playbook_keys_text: e.target.value }))}
                  placeholder="nomad_run_camp, prices_and_tariffs"
                />
              </div>

              <div className="space-y-1.5">
                <Label>Подсказка для ответа</Label>
                <Textarea
                  value={form.reply_guidance}
                  onChange={(e) => setForm((f) => f && ({ ...f, reply_guidance: e.target.value }))}
                  rows={3}
                  placeholder="Напр. Если спрашивают цену, уточнить даты и количество гостей. Не обещать наличие без проверки."
                />
              </div>

              <div className="space-y-1.5">
                <Label>Заметки менеджера</Label>
                <Textarea
                  value={form.manager_notes}
                  onChange={(e) => setForm((f) => f && ({ ...f, manager_notes: e.target.value }))}
                  rows={2}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Caption / текст из Instagram</Label>
                <Textarea
                  value={form.caption}
                  onChange={(e) => setForm((f) => f && ({ ...f, caption: e.target.value }))}
                  rows={3}
                />
              </div>
            </div>
          ) : null}
          <DialogFooter className="gap-2 sm:gap-0">
            {editing ? (
              <Button variant="outline" onClick={() => rebuildMutation.mutate(editing.id)} disabled={rebuildMutation.isPending}>
                <RefreshCwIcon className={cn('h-4 w-4 mr-2', rebuildMutation.isPending && 'animate-spin')} />
                Пересобрать hash
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => { setEditing(null); setForm(null) }}>Отмена</Button>
            <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function HotelDetailsPage() {
  return <HotelDetailsPageContent />
}

function HotelDetailsPageContent() {
  const { t } = useLanguage()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'photo' | 'video' | 'playbooks' | 'reply-templates' | 'pricing' | 'social-content'>('playbooks')
  const [search, setSearch] = useState('')
  const [category, setКатегория] = useState('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<HotelMediaItem | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<HotelMediaItem | null>(null)
  const [form, setForm] = useState<MediaFormState>(EMPTY_FORM)
  const [tagInput, setTagInput] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [pendingPhotos, setPendingPhotos] = useState<File[]>([])
  const [photoDragOver, setPhotoDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const photoInputRef = useRef<HTMLInputElement>(null)

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['hotel-media'],
    queryFn: () => fetchHotelMediaItems(),
  })

  const uploadMutation = useMutation({
    mutationFn: async ({ data, file, photos }: { data: typeof form; file: File | null; photos: File[] }) => {
      if (editingItem) {
        const updated = await updateHotelMediaItem(editingItem.id, data, file ?? undefined)
        if (photos.length > 0) return addPhotosToAlbum(editingItem.id, photos)
        return updated
      } else {
        const created = await uploadHotelMediaItem(data, file ?? undefined)
        if (photos.length > 0) return addPhotosToAlbum(created.id, photos)
        return created
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-media'] })
      toast.success(editingItem ? 'Updated successfully' : 'Uploaded successfully')
      closeDialog()
    },
    onError: () => toast.error('Failed to save. Please try again.'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteHotelMediaItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hotel-media'] })
      toast.success('Deleted')
      setDeleteTarget(null)
    },
    onError: () => toast.error('Failed to delete'),
  })

  const deletePhotoMutation = useMutation({
    mutationFn: (photoId: number) => deleteHotelMediaPhoto(photoId),
    onSuccess: (_, photoId) => {
      queryClient.invalidateQueries({ queryKey: ['hotel-media'] })
      setEditingItem((prev) =>
        prev ? { ...prev, photos: prev.photos.filter((p) => p.id !== photoId) } : prev,
      )
    },
    onError: () => toast.error('Failed to delete photo'),
  })

  const openUpload = () => {
    setEditingItem(null)
    const mediaType = activeTab === 'playbooks' || activeTab === 'reply-templates' || activeTab === 'pricing' || activeTab === 'social-content' ? 'photo' : activeTab as 'photo' | 'video'
    setForm({
      ...EMPTY_FORM,
      media_type: mediaType,
    })
    setSelectedFile(null)
    setPendingPhotos([])
    setTagInput('')
    setDialogOpen(true)
  }

  const openEdit = (item: HotelMediaItem) => {
    setEditingItem(item)
    setForm({
      title: item.title,
      description: item.description,
      tags: [...item.tags],
      category: item.category,
      room_category: item.room_category ?? null,
      media_type: item.media_type,
      video_url: item.video_url,
    })
    setSelectedFile(null)
    setPendingPhotos([])
    setTagInput('')
    setDialogOpen(true)
  }

  const closeDialog = () => {
    setDialogOpen(false)
    setEditingItem(null)
    setForm(EMPTY_FORM)
    setSelectedFile(null)
    setPendingPhotos([])
    setTagInput('')
  }

  const handleFile = useCallback((file: File) => {
    setSelectedFile(file)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const handlePhotoDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setPhotoDragOver(false)
    const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'))
    if (files.length > 0) setPendingPhotos((prev) => [...prev, ...files])
  }, [])

  const handlePhotoFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).filter((f) => f.type.startsWith('image/'))
    if (files.length > 0) setPendingPhotos((prev) => [...prev, ...files])
    e.target.value = ''
  }

  const removePendingPhoto = (idx: number) => {
    setPendingPhotos((prev) => prev.filter((_, i) => i !== idx))
  }

  const addTag = () => {
    const tag = tagInput.trim().toLowerCase()
    if (tag && !form.tags.includes(tag)) {
      setForm((f) => ({ ...f, tags: [...f.tags, tag] }))
    }
    setTagInput('')
  }

  const removeTag = (tag: string) => {
    setForm((f) => ({ ...f, tags: f.tags.filter((t) => t !== tag) }))
  }

  const handleSubmit = () => {
    if (!form.title.trim()) { toast.error('Title is required'); return }
    const isPhotoAlbum = form.media_type === 'photo'
    if (isPhotoAlbum && !editingItem && pendingPhotos.length === 0 && !selectedFile) {
      toast.error('Add at least one photo to the album')
      return
    }
    if (!isPhotoAlbum && !selectedFile && !editingItem?.file_url) {
      toast.error('Please select a file to upload')
      return
    }
    uploadMutation.mutate({ data: form, file: selectedFile, photos: pendingPhotos })
  }

  const tabCount = (type: 'photo' | 'video') =>
    items.filter((i) => i.media_type === type).length

  const isPhotoMode = form.media_type === 'photo'
  const existingAlbumPhotos = editingItem?.photos ?? []
  const isMediaTab = activeTab === 'photo' || activeTab === 'video'

  return (
    <div className="flex flex-1 flex-col min-w-0">
      <div className="flex flex-1 flex-col gap-4 py-4 md:gap-6 md:py-6">
        <div className="px-4 lg:px-6 flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold">{t('hotelDetails.title')}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {t('hotelDetails.subtitle')}
            </p>
          </div>
          {isMediaTab ? (
            <Button onClick={openUpload}>
              <UploadCloudIcon className="h-4 w-4 mr-2" />
              Upload {activeTab === 'photo' ? 'Photo' : 'Video'}
            </Button>
          ) : null}
        </div>

        <div className="px-4 lg:px-6">
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as typeof activeTab)}
            className="space-y-5"
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <TabsList>
                <TabsTrigger value="playbooks" className="gap-1.5">
                  <ZapIcon className="h-4 w-4" />
                  {t('hotelDetails.tabs.playbooks')}
                </TabsTrigger>
                <TabsTrigger value="reply-templates" className="gap-1.5">
                  <FileTextIcon className="h-4 w-4" />
                  Шаблоны
                </TabsTrigger>
                <TabsTrigger value="pricing" className="gap-1.5">
                  <DollarSignIcon className="h-4 w-4" />
                  {t('hotelDetails.tabs.pricing')}
                </TabsTrigger>
                <TabsTrigger value="social-content" className="gap-1.5">
                  <InstagramIcon className="h-4 w-4" />
                  Соцконтент
                </TabsTrigger>
                <TabsTrigger value="photo" className="gap-1.5">
                  <ImageIcon className="h-4 w-4" />
                  {t('hotelDetails.tabs.photos')}
                  {tabCount('photo') > 0 ? (
                    <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">{tabCount('photo')}</Badge>
                  ) : null}
                </TabsTrigger>
                <TabsTrigger value="video" className="gap-1.5">
                  <VideoIcon className="h-4 w-4" />
                  {t('hotelDetails.tabs.videos')}
                  {tabCount('video') > 0 ? (
                    <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">{tabCount('video')}</Badge>
                  ) : null}
                </TabsTrigger>
              </TabsList>

              {isMediaTab ? (
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="relative">
                    <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Поиск по названию, тегу..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="pl-8 w-56"
                    />
                  </div>
                  <Select value={category} onValueChange={setКатегория}>
                    <SelectTrigger className="w-44">
                      <SelectValue placeholder="Все категории" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Categories</SelectItem>
                      {CATEGORIES.map((c) => (
                        <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ) : null}
            </div>

            {(['photo', 'video'] as const).map((type) => (
              <TabsContent key={type} value={type}>
                <MediaGrid
                  items={items}
                  isLoading={isLoading}
                  mediaType={type}
                  search={search}
                  category={category}
                  onEdit={openEdit}
                  onDelete={setDeleteTarget}
                  onUpload={openUpload}
                />
              </TabsContent>
            ))}

            <TabsContent value="playbooks">
              <PlaybooksTab />
            </TabsContent>

            <TabsContent value="reply-templates">
              <ReplyTemplatesTab />
            </TabsContent>

            <TabsContent value="pricing">
              <PricingTab />
            </TabsContent>

            <TabsContent value="social-content">
              <SocialContentTab mediaItems={items} />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* Upload / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open) closeDialog() }}>
        <DialogContent className="max-w-[95vw] md:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingItem ? 'Edit' : 'Upload'}{' '}
              {form.media_type === 'photo' ? 'Photo Album' : 'Video'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-5 py-2">
            {!editingItem ? (
              <div className="space-y-1.5">
                <Label>Тип</Label>
                <div className="flex gap-2">
                  {(['photo', 'video'] as const).map((t) => (
                    <button
                      key={t === 'photo' ? 'Фото' : 'Видео'}
                      onClick={() => setForm((f) => ({ ...f, media_type: t }))}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-sm capitalize transition-colors ${
                        form.media_type === t
                          ? 'border-primary bg-primary/5 text-primary font-medium'
                          : 'border-border text-muted-foreground hover:border-foreground/40'
                      }`}
                    >
                      {t === 'photo' ? <ImageIcon className="h-3.5 w-3.5" /> : <VideoIcon className="h-3.5 w-3.5" />}
                      {t === 'photo' ? 'Фото' : 'Видео'}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {isPhotoMode ? (
              <div className="space-y-3">
                <Label className="flex items-center gap-1.5">
                  <ImagesIcon className="h-3.5 w-3.5" />
                  Photos
                  <span className="text-xs text-muted-foreground font-normal ml-1">
                    — AI sends up to 3 photos when a guest asks
                  </span>
                </Label>

                {existingAlbumPhotos.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {existingAlbumPhotos.map((photo) => (
                      <div key={photo.id} className="relative group/photo w-20 h-20 rounded-lg overflow-hidden border bg-muted flex-shrink-0">
                        {photo.file_url ? <img src={photo.file_url} alt="" className="w-full h-full object-cover" /> : null}
                        <button
                          type="button"
                          onClick={() => deletePhotoMutation.mutate(photo.id)}
                          className="absolute top-0.5 right-0.5 rounded-full bg-black/70 p-0.5 opacity-0 group-hover/photo:opacity-100 transition-opacity"
                        >
                          <XIcon className="h-3 w-3 text-white" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}

                {pendingPhotos.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {pendingPhotos.map((file, idx) => (
                      <div key={idx} className="relative group/photo w-20 h-20 rounded-lg overflow-hidden border bg-muted flex-shrink-0">
                        <img src={URL.createObjectURL(file)} alt="" className="w-full h-full object-cover" />
                        <button
                          type="button"
                          onClick={() => removePendingPhoto(idx)}
                          className="absolute top-0.5 right-0.5 rounded-full bg-black/70 p-0.5 opacity-0 group-hover/photo:opacity-100 transition-opacity"
                        >
                          <XIcon className="h-3 w-3 text-white" />
                        </button>
                        <div className="absolute bottom-0 inset-x-0 bg-primary/80 text-[9px] text-white text-center py-0.5">новое</div>
                      </div>
                    ))}
                  </div>
                ) : null}

                <div
                  onDragOver={(e) => { e.preventDefault(); setPhotoDragOver(true) }}
                  onDragLeave={() => setPhotoDragOver(false)}
                  onDrop={handlePhotoDrop}
                  onClick={() => photoInputRef.current?.click()}
                  className={`relative rounded-xl border-2 border-dashed cursor-pointer transition-colors flex flex-col items-center justify-center gap-2 py-6 ${
                    photoDragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/40 hover:bg-muted/30'
                  }`}
                >
                  <input ref={photoInputRef} type="file" className="sr-only" accept="image/*" multiple onChange={handlePhotoFilePick} />
                  <PlusIcon className="h-6 w-6 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">
                    {existingAlbumPhotos.length + pendingPhotos.length > 0 ? 'Добавить больше фото' : 'Перетащите фото сюда или нажмите для выбора'}
                  </p>
                  <p className="text-xs text-muted-foreground">Вы можете выбрать несколько файлов одновременно</p>
                </div>
              </div>
            ) : null}

            {!isPhotoMode && form.media_type !== 'video' ? (
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
                  dragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/40 hover:bg-muted/30'
                }`}
              >
                <input ref={fileInputRef} type="file" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
                {selectedFile ? (
                  <div className="h-32 flex flex-col items-center justify-center gap-2">
                    <FileTextIcon className="h-8 w-8 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">{selectedFile.name}</p>
                  </div>
                ) : editingItem?.file_url ? (
                  <div className="h-32 flex flex-col items-center justify-center gap-2">
                    <FileTextIcon className="h-8 w-8 text-muted-foreground/50" />
                    <p className="text-sm text-muted-foreground">Перетащите новый файл для замены</p>
                  </div>
                ) : (
                  <div className="h-32 flex flex-col items-center justify-center gap-2">
                    <UploadCloudIcon className="h-8 w-8 text-muted-foreground/50" />
                    <p className="text-sm text-muted-foreground">Перетащите файл сюда или нажмите для выбора</p>
                  </div>
                )}
              </div>
            ) : null}

            {form.media_type === 'video' ? (
              <div className="space-y-1.5">
                <Label htmlFor="video-url">Ссылка на видео</Label>
                <div className="relative">
                  <LinkIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="video-url"
                    placeholder="https://youtube.com/..."
                    value={form.video_url}
                    onChange={(e) => setForm((f) => ({ ...f, video_url: e.target.value }))}
                    className="pl-8"
                  />
                </div>
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="media-title">Название *</Label>
              <Input
                id="media-title"
                placeholder="напр. Номер Делюкс — Двуспальная кровать"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label>Категория</Label>
              <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v, room_category: v === 'rooms' ? f.room_category : null }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            {form.category === 'rooms' && (
              <div className="space-y-1.5">
                <Label>Тип номера</Label>
                <Select
                  value={form.room_category ?? ''}
                  onValueChange={(v) => setForm((f) => ({ ...f, room_category: (v || null) as RoomCategory | null }))}
                >
                  <SelectTrigger><SelectValue placeholder="Выберите тип номера..." /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="standard_queen">Стандарт Квин</SelectItem>
                    <SelectItem value="standard_twin">Стандарт Твин</SelectItem>
                    <SelectItem value="comfort">Комфорт</SelectItem>
                    <SelectItem value="family">Семейный</SelectItem>
                    <SelectItem value="other">Другой</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">Используется AI для отправки гостям подходящих фотографий номеров</p>
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="tag-input" className="flex items-center gap-1.5">
                <TagIcon className="h-3.5 w-3.5" />
                Теги
              </Label>
              <div className="flex flex-wrap gap-1.5 rounded-md border bg-background px-3 py-2 min-h-[42px] focus-within:ring-1 focus-within:ring-ring">
                {form.tags.map((tag) => (
                  <span key={tag} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${tagColor(tag)}`}>
                    {tag}
                    <button type="button" onClick={() => removeTag(tag)} className="opacity-60 hover:opacity-100">
                      <XIcon className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  id="tag-input"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag() }
                    if (e.key === 'Backspace' && !tagInput && form.tags.length > 0) removeTag(form.tags[form.tags.length - 1])
                  }}
                  onBlur={addTag}
                  placeholder={form.tags.length === 0 ? 'Введите тег и нажмите Enter...' : ''}
                  className="flex-1 min-w-24 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                />
              </div>
              <p className="text-xs text-muted-foreground">e.g. bedroom, luxury, king-bed</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="media-description" className="flex items-center gap-1.5">
                Description
                <span className="text-xs text-muted-foreground font-normal ml-1">
                  — AI reads this to decide when to send this item to leads
                </span>
              </Label>
              <Textarea
                id="media-description"
                placeholder="Опишите, что изображено и когда это актуально."
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? 'Saving...' : editingItem ? 'Save Changes' : 'Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить &quot;{deleteTarget?.title}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>
              Это навсегда удалит этот элемент и все его фотографии из медиатеки.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
