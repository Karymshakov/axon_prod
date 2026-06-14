import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery } from '@tanstack/react-query'
import { useState, useEffect, useRef } from 'react'
import { ArrowDown, ArrowUp, Search } from 'lucide-react'

import { getAuditLogs, getAdminUsers, type AuditLog } from '@/lib/api'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DateRangePicker } from '@/components/date-range-picker'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TablePagination } from '@/components/table-pagination'

// URL search params schema
type SearchParams = {
  page?: number
  page_size?: number
  search?: string
  actor?: string
  action?: 'create' | 'update' | 'delete'
  date_from?: string
  date_to?: string
  ordering?: string
}
type ActionFilter = 'all' | 'create' | 'update' | 'delete'

export const Route = createFileRoute('/_app/audit-logs')({
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    page: search.page ? Number(search.page) : undefined,
    page_size: search.page_size ? Number(search.page_size) : undefined,
    search: search.search as string | undefined,
    actor: search.actor as string | undefined,
    action: search.action as 'create' | 'update' | 'delete' | undefined,
    date_from: search.date_from as string | undefined,
    date_to: search.date_to as string | undefined,
    ordering: search.ordering as string | undefined,
  }),
  component: AuditLogsPage,
})

const OBJECT_TYPE_LABELS: Record<string, string> = {
  user: 'User',
  lead: 'Lead',
  leadnote: 'Note',
  task: 'Task',
  customer: 'Customer',
  pipelinestage: 'Pipeline Stage',
  telegramconfig: 'Telegram',
  instagramconfig: 'Instagram',
  whatsappconfig: 'WhatsApp',
  aiconfig: 'AI Config',
  leadgoal: 'Goal',
  knowledgeentry: 'Knowledge',
  knowledgedocument: 'Document',
}

function AuditLogsPage() {
  const { language, t } = useLanguage()
  const navigate = useNavigate()
  const searchParams = Route.useSearch()

  // Local state for search input (debounced before updating URL)
  const [searchInput, setSearchInput] = useState(searchParams.search || '')
  const isFirstRender = useRef(true)

  const page = searchParams.page ?? 1
  const pageSize = searchParams.page_size ?? 25
  const ordering = searchParams.ordering || '-timestamp'
  const actionFilter: ActionFilter = searchParams.action || 'all'
  const sortDirection = ordering.startsWith('-') ? 'desc' : 'asc'

  const dateRange =
    searchParams.date_from || searchParams.date_to
      ? { from: searchParams.date_from, to: searchParams.date_to }
      : undefined

  // Fetch users for actor filter dropdown
  const { data: usersData } = useQuery({
    queryKey: ['admin-users-list'],
    queryFn: () => getAdminUsers(),
    staleTime: 5 * 60 * 1000,
  })

  // Fetch audit logs with TanStack Query
  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', { page, pageSize, search: searchParams.search, actor: searchParams.actor, action: searchParams.action, date_from: searchParams.date_from, date_to: searchParams.date_to, ordering }],
    queryFn: () => getAuditLogs({
      page,
      page_size: pageSize,
      search: searchParams.search,
      actor: searchParams.actor,
      action: searchParams.action,
      date_from: searchParams.date_from,
      date_to: searchParams.date_to,
      ordering,
    }),
  })

  // Track latest search params without triggering effect
  const searchParamsRef = useRef(searchParams)
  useEffect(() => {
    searchParamsRef.current = searchParams
  }, [searchParams])

  // Debounced search
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }

    const timer = setTimeout(() => {
      if (searchInput !== (searchParamsRef.current.search || '')) {
        navigate({
          to: '/audit-logs',
          search: (prev) => ({
            ...prev,
            search: searchInput || undefined,
            page: 1,
          }),
          replace: true,
        })
      }
    }, 400)

    return () => clearTimeout(timer)
  }, [searchInput, navigate])

  const handleActorFilterChange = (value: string) => {
    navigate({
      to: '/audit-logs',
      search: (prev) => ({
        ...prev,
        actor: value === 'all' ? undefined : value,
        page: 1,
      }),
      replace: true,
    })
  }

  const handleActionFilterChange = (value: ActionFilter) => {
    navigate({
      to: '/audit-logs',
      search: (prev) => ({
        ...prev,
        action: value === 'all' ? undefined : value,
        page: 1,
      }),
      replace: true,
    })
  }

  const handleDateRangeChange = (range?: { from?: string; to?: string }) => {
    navigate({
      to: '/audit-logs',
      search: (prev) => ({
        ...prev,
        date_from: range?.from || undefined,
        date_to: range?.to || undefined,
        page: 1,
      }),
      replace: true,
    })
  }

  const handlePageChange = (page: number) => {
    navigate({
      to: '/audit-logs',
      search: (prev) => ({ ...prev, page }),
      replace: true,
    })
  }

  const handlePageSizeChange = (pageSize: number) => {
    navigate({
      to: '/audit-logs',
      search: (prev) => ({ ...prev, page_size: pageSize, page: 1 }),
      replace: true,
    })
  }

  const handleClearFilters = () => {
    setSearchInput('')
    navigate({
      to: '/audit-logs',
      search: {},
      replace: true,
    })
  }

  function handleSort() {
    const newOrdering = sortDirection === 'asc' ? '-timestamp' : 'timestamp'
    navigate({
      to: '/audit-logs',
      search: (prev) => ({ ...prev, ordering: newOrdering, page: 1 }),
      replace: true,
    })
  }

  function getActionBadge(action: AuditLog['action']) {
    switch (action) {
      case 'create':
        return (
          <Badge className="bg-green-100 text-green-700 hover:bg-green-100">
            {t('common.create')}
          </Badge>
        )
      case 'update':
        return (
          <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">
            {t('common.update')}
          </Badge>
        )
      case 'delete':
        return (
          <Badge className="bg-red-100 text-red-700 hover:bg-red-100">
            {t('common.delete')}
          </Badge>
        )
      default:
        return <Badge variant="secondary">{action}</Badge>
    }
  }

  function truncateValue(value: unknown, maxLength = 30): string {
    const str = String(value ?? 'null')
    if (str.length <= maxLength) return str
    return str.slice(0, maxLength) + '...'
  }

  function formatChanges(changes: AuditLog['changes']) {
    const entries = Object.entries(changes)
    if (entries.length === 0) return '-'

    const maxVisible = 3
    const visibleEntries = entries.slice(0, maxVisible)
    const hiddenCount = entries.length - maxVisible

    return (
      <div className="space-y-1">
        {visibleEntries.map(([field, [oldVal, newVal]]) => (
          <div key={field} className="text-xs truncate">
            <span className="font-medium">{field}:</span>{' '}
            <span className="text-muted-foreground">
              {truncateValue(oldVal)}
            </span>{' '}
            <span className="text-muted-foreground">&rarr;</span>{' '}
            <span>{truncateValue(newVal)}</span>
          </div>
        ))}
        {hiddenCount > 0 && (
          <div className="text-xs text-muted-foreground">
            {language === 'ru' ? (
              <>
                + еще {hiddenCount} {(() => {
                  const mod10 = hiddenCount % 10
                  const mod100 = hiddenCount % 100
                  if (mod10 === 1 && mod100 !== 11) return 'изменение'
                  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'изменения'
                  return 'изменений'
                })()}
              </>
            ) : (
              `+${hiddenCount} more change${hiddenCount > 1 ? 's' : ''}`
            )}
          </div>
        )}
      </div>
    )
  }

  const hasFilters = searchParams.search || searchParams.actor || searchParams.action || searchParams.date_from || searchParams.date_to

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 lg:p-6 min-w-0">
      <Card>
        <CardHeader>
          <CardTitle>{t('auditLogs.title')} ({data?.count ?? 0})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Filter section */}
          <div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">{t('common.search')}</label>
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('auditLogs.searchPlaceholder')}
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">{t('auditLogs.user')}</label>
                <Select value={searchParams.actor || 'all'} onValueChange={handleActorFilterChange}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('auditLogs.allUsers')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('auditLogs.allUsers')}</SelectItem>
                    {usersData?.map((user) => (
                      <SelectItem key={user.id} value={user.email}>
                        {user.name ? `${user.name} (${user.email})` : user.email}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">{t('auditLogs.action')}</label>
                <Select value={actionFilter} onValueChange={handleActionFilterChange}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('auditLogs.allActions')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('auditLogs.allActions')}</SelectItem>
                    <SelectItem value="create">{t('common.create')}</SelectItem>
                    <SelectItem value="update">{t('common.update')}</SelectItem>
                    <SelectItem value="delete">{t('common.delete')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">{t('auditLogs.dateRange')}</label>
                <DateRangePicker
                  value={dateRange}
                  onChange={handleDateRangeChange}
                  placeholder={t('auditLogs.selectDateRange')}
                />
              </div>
              {hasFilters && (
                <div className="flex items-end">
                  <Button variant="ghost" onClick={handleClearFilters}>
                    {t('auditLogs.clearFilters')}
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <Button
                      variant="ghost"
                      onClick={handleSort}
                      className="-ml-4 h-8 hover:bg-transparent"
                    >
                      {t('auditLogs.timestamp')}
                      {sortDirection === 'asc' ? (
                        <ArrowUp className="ml-2 h-4 w-4" />
                      ) : (
                        <ArrowDown className="ml-2 h-4 w-4" />
                      )}
                    </Button>
                  </TableHead>
                  <TableHead>{t('auditLogs.action')}</TableHead>
                  <TableHead>{t('auditLogs.user')}</TableHead>
                  <TableHead>{t('auditLogs.object')}</TableHead>
                  <TableHead>{t('auditLogs.changes')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center">
                      {t('common.loading')}
                    </TableCell>
                  </TableRow>
                ) : (data?.results?.length ?? 0) === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center">
                      {hasFilters
                        ? t('auditLogs.noLogsFiltered')
                        : t('auditLogs.noLogs')}
                    </TableCell>
                  </TableRow>
                ) : (
                  data?.results.map((log) => (
                    <TableRow key={log.id} className="h-16 max-h-16">
                      <TableCell className="whitespace-nowrap align-top py-2">
                        {new Date(log.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell className="align-top py-2">{getActionBadge(log.action)}</TableCell>
                      <TableCell className="align-top py-2">
                        {log.actor ? (
                          <div>
                            <div className="font-medium truncate max-w-[150px]">
                              {log.actor.email}
                            </div>
                            {log.actor.name && (
                              <div className="text-xs text-muted-foreground truncate max-w-[150px]">
                                {log.actor.name}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="align-top py-2 max-w-[200px]">
                        <div className="truncate">{log.object_repr}</div>
                        {log.object_type && (
                          <div className="text-xs text-muted-foreground">
                            {(() => {
                              const translatedType = t(`auditLogs.objectTypes.${log.object_type}`)
                              return translatedType.startsWith('auditLogs.objectTypes.')
                                ? (OBJECT_TYPE_LABELS[log.object_type] || log.object_type)
                                : translatedType
                            })()}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="align-top py-2 max-w-[300px]">
                        {formatChanges(log.changes)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>

            {/* Pagination */}
            {data && data.total_pages > 0 && (
              <TablePagination
                currentPage={data.current_page}
                totalPages={data.total_pages}
                pageSize={data.page_size}
                totalCount={data.count}
                onPageChange={handlePageChange}
                onPageSizeChange={handlePageSizeChange}
              />
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
