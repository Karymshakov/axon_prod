import { createFileRoute, Link } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import {
  SearchIcon,
  MailIcon,
  PhoneIcon,
  ArrowRightIcon,
  BuildingIcon,
  BriefcaseIcon,
  XIcon,
  UserRoundIcon,
} from 'lucide-react'
import { fetchLeads, fetchPipelineStages, SOURCE_OPTIONS, type Lead } from '@/lib/api'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'

export const Route = createFileRoute('/_app/contacts/')({
  component: ContactsPage,
})

const AVATAR_GRADIENTS = [
  'from-violet-500 to-purple-600',
  'from-emerald-500 to-teal-600',
  'from-orange-400 to-rose-500',
  'from-blue-500 to-cyan-600',
  'from-pink-500 to-rose-600',
  'from-amber-400 to-orange-500',
  'from-sky-400 to-blue-600',
  'from-green-400 to-emerald-600',
]

function getAvatarGradient(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AVATAR_GRADIENTS[Math.abs(hash) % AVATAR_GRADIENTS.length]
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

const SEGMENT_CONFIG = {
  business: {
    label: 'Business',
    icon: BuildingIcon,
    borderClass: 'border-t-2 border-t-amber-400',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200',
  },
  individual: {
    label: 'Individual',
    icon: UserRoundIcon,
    borderClass: 'border-t-2 border-t-sky-400',
    badgeClass: 'bg-sky-50 text-sky-700 border-sky-200',
  },
} as const

function ContactCard({ lead, stageName }: { lead: Lead; stageName: string }) {
  const displayName = lead.contact_person || 'Unknown'
  const gradient = getAvatarGradient(displayName)
  const initials = getInitials(displayName)
  const segment = SEGMENT_CONFIG[lead.segment as keyof typeof SEGMENT_CONFIG] ?? SEGMENT_CONFIG.individual
  const SegmentIcon = segment.icon

  return (
    <Card className={`group flex flex-col hover:shadow-md transition-shadow duration-200 ${segment.borderClass}`}>
      <CardContent className="flex flex-col gap-3 p-4">
        {/* Avatar + Name */}
        <div className="flex items-start gap-3">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gradient-to-br ${gradient} text-white text-sm font-semibold shadow-sm`}
          >
            {initials || <UserRoundIcon className="h-5 w-5" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 min-w-0">
              <p className="truncate font-semibold text-sm leading-tight">{displayName}</p>
              <span className={`inline-flex shrink-0 items-center gap-0.5 rounded-full border px-1.5 py-0 text-[10px] font-medium leading-4 ${segment.badgeClass}`}>
                <SegmentIcon className="h-2.5 w-2.5" />
                {segment.label}
              </span>
            </div>
              {lead.job_title ? (
              <p className="truncate text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                <BriefcaseIcon className="h-3 w-3 shrink-0" />
                {lead.job_title}
              </p>
            ) : null}
          </div>
        </div>

        {/* Divider */}
        <div className="h-px bg-border" />

        {/* Contact info */}
        <div className="space-y-1.5">
          {lead.email ? (
            <a
              href={`mailto:${lead.email}`}
              className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors min-w-0"
              onClick={(e) => e.stopPropagation()}
            >
              <MailIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{lead.email}</span>
            </a>
          ) : null}
          {lead.phone || lead.mobile_phone ? (
            <a
              href={`tel:${lead.phone || lead.mobile_phone}`}
              className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors min-w-0"
              onClick={(e) => e.stopPropagation()}
            >
              <PhoneIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{lead.phone || lead.mobile_phone}</span>
            </a>
          ) : null}
          {!lead.email && !lead.phone && !lead.mobile_phone ? (
            <p className="text-xs text-muted-foreground italic">No contact details</p>
          ) : null}
        </div>

        {/* Tags row */}
        <div className="flex flex-wrap gap-1.5 mt-auto">
          {stageName ? (
            <Badge variant="secondary" className="text-xs px-2 py-0 h-5 font-normal">
              {stageName}
            </Badge>
          ) : null}
          {lead.source ? (
            <Badge variant="outline" className="text-xs px-2 py-0 h-5 font-normal">
              {lead.source}
            </Badge>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-1 border-t border-border/50">
          {lead.last_contacted ? (
            <span className="text-xs text-muted-foreground">
              Last contact{' '}
              {new Date(lead.last_contacted).toLocaleDateString('ru-RU', {
                month: 'short',
                day: 'numeric',
              })}
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">Never contacted</span>
          )}
          <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs gap-1">
            <Link to="/leads/$leadId" params={{ leadId: String(lead.id) }}>
              View
              <ArrowRightIcon className="h-3 w-3" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function ContactsPage() {
  const { t } = useLanguage()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')

  const queryParams = useMemo(() => {
    const p: Record<string, string> = {}
    if (statusFilter && statusFilter !== 'all') p.status = statusFilter
    if (sourceFilter && sourceFilter !== 'all') p.source = sourceFilter
    if (search) p.search = search
    return p
  }, [search, statusFilter, sourceFilter])

  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['leads', queryParams],
    queryFn: () => fetchLeads(queryParams),
  })

  const { data: stages = [] } = useQuery({
    queryKey: ['pipeline-stages'],
    queryFn: fetchPipelineStages,
  })

  const stageMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const s of stages) map[s.key] = s.name
    return map
  }, [stages])

  const sortedLeads = useMemo(() => {
    return [...leads].sort((a, b) => {
      const nameA = (a.contact_person || '').toLowerCase()
      const nameB = (b.contact_person || '').toLowerCase()
      return nameA.localeCompare(nameB)
    })
  }, [leads])

  const hasFilters = search || (statusFilter && statusFilter !== 'all') || (sourceFilter && sourceFilter !== 'all')

  const clearFilters = () => {
    setSearch('')
    setStatusFilter('')
    setSourceFilter('')
  }

  return (
    <div className="flex flex-1 flex-col min-w-0">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
        {/* Header */}
        <div className="px-4 lg:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{t('contacts.title')}</h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                {isLoading ? t('common.loading') : `${sortedLeads.length} ${t('contacts.title').toLowerCase()}`}
              </p>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="px-4 lg:px-6">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                placeholder={t('contacts.searchPlaceholder')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px] h-9">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                {stages.map((stage) => (
                  <SelectItem key={stage.key} value={stage.key}>
                    {stage.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-[140px] h-9">
                <SelectValue placeholder="All Sources" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                {SOURCE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {hasFilters ? (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 gap-1.5">
                <XIcon className="h-3.5 w-3.5" />
                Clear
              </Button>
            ) : null}
          </div>
        </div>

        {/* Content */}
        <div className="px-4 lg:px-6">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="h-48 rounded-lg bg-muted animate-pulse"
                />
              ))}
            </div>
          ) : sortedLeads.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
                <UserRoundIcon className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="font-semibold text-base mb-1">
                {hasFilters ? t('common.noResults') : t('contacts.noContacts')}
              </h3>
              <p className="text-sm text-muted-foreground max-w-xs">
                {hasFilters
                  ? 'Try adjusting your search or filters.'
                  : 'Contacts are created when you add leads. Head to the Leads page to add your first lead.'}
              </p>
              {hasFilters ? (
                <Button variant="outline" size="sm" onClick={clearFilters} className="mt-4">
                  Clear filters
                </Button>
              ) : (
                <Button asChild variant="outline" size="sm" className="mt-4">
                  <Link to="/leads">Go to Leads</Link>
                </Button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {sortedLeads.map((lead) => (
                <ContactCard
                  key={lead.id}
                  lead={lead}
                  stageName={stageMap[lead.status] || lead.status}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
