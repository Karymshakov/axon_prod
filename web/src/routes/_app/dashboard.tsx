import { createFileRoute, Link } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery } from '@tanstack/react-query'
import { TrendingUpIcon, UsersIcon, ArrowRightIcon, CheckCircleIcon, BadgeCheckIcon } from 'lucide-react'
import { fetchLeadStats, fetchLeads, fetchPipelineStages, fetchLeadSourceStats, getDiscoverySourceLabel, getLeadStatusLabel } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'

export const Route = createFileRoute('/_app/dashboard')({
  component: DashboardPage,
})

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)
  if (diffMins < 1) return 'только что'
  if (diffMins < 60) return `${diffMins} мин назад`
  if (diffHours < 24) return `${diffHours} ч назад`
  if (diffDays < 7) return `${diffDays} д назад`
  return date.toLocaleDateString('ru-RU')
}

const BAR_COLORS = [
  'bg-blue-500',
  'bg-violet-500',
  'bg-amber-500',
  'bg-orange-500',
  'bg-cyan-500',
  'bg-pink-500',
  'bg-emerald-500',
  'bg-indigo-500',
]

const PIE_COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#f97316', '#06b6d4', '#ec4899', '#10b981', '#6366f1']

function DashboardPage() {
  const { t } = useLanguage()
  const { data: stages, status: stagesStatus } = useQuery({
    queryKey: ['pipeline-stages'],
    queryFn: () => fetchPipelineStages(),
    staleTime: 5 * 60 * 1000,
  })

  const { data: stats, status: statsStatus } = useQuery({
    queryKey: ['lead-stats'],
    queryFn: () => fetchLeadStats(),
    staleTime: 5 * 60 * 1000,
  })

  const { data: leads, status: leadsStatus } = useQuery({
    queryKey: ['leads'],
    queryFn: () => fetchLeads(),
    staleTime: 5 * 60 * 1000,
  })

  const { data: sourceStats } = useQuery({
    queryKey: ['lead-source-stats'],
    queryFn: () => fetchLeadSourceStats(),
    staleTime: 5 * 60 * 1000,
  })

  // Build key→name map; deduplicate by name across segments, summing counts
  const stageNameMap: Record<string, string> = {}
  const finalKeys = new Set<string>()
  // uniqueStages: one entry per unique stage name, with all matching keys
  const uniqueStages: Array<{ id: number; name: string; keys: string[]; is_final: boolean }> = []
  const seenNames = new Map<string, number>() // name → index in uniqueStages
  if (stages) {
    for (const stage of stages) {
      const displayName = getLeadStatusLabel(stage.key, stages)
      stageNameMap[stage.key] = displayName
      if (stage.is_final) finalKeys.add(stage.key)
      const idx = seenNames.get(displayName)
      if (idx !== undefined) {
        if (!uniqueStages[idx].keys.includes(stage.key)) {
          uniqueStages[idx].keys.push(stage.key)
        }
        if (stage.is_final) uniqueStages[idx].is_final = true
      } else {
        seenNames.set(displayName, uniqueStages.length)
        uniqueStages.push({ id: stage.id, name: displayName, keys: [stage.key], is_final: stage.is_final })
      }
    }
  }

  // Leads in final stages = "converted/done"
  const finalCount = stats
    ? Object.entries(stats)
        .filter(([k]) => k !== 'total' && finalKeys.has(k))
        .reduce((sum, [, v]) => sum + v, 0)
    : 0

  const conversionRate =
    stats && stats.total > 0 ? Math.round((finalCount / stats.total) * 100) : 0

  const activeLeads = (stats?.total ?? 0) - finalCount

  const recentLeads = leads
    ? [...leads].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5)
    : []

  const isLoading = stagesStatus === 'pending' || statsStatus === 'pending'

  return (
    <div className="flex flex-1 flex-col crm-enter">
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
          {/* Page header */}
          <div className="px-4 lg:px-6">
            <h1 className="text-2xl font-bold crm-page-title">{t('dashboard.title')}</h1>
            <p className="text-muted-foreground text-sm mt-0.5">{t('dashboard.subtitle')}</p>
          </div>

          {/* Welcome banner for new empty orgs */}
          {!isLoading && (stats?.total ?? 0) === 0 ? (
            <div className="px-4 lg:px-6">
              <div className="rounded-xl bg-gradient-to-r from-blue-50 to-violet-50 border border-blue-200/60 p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4 crm-card">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-[#2461FF] to-[#7C3AED] flex items-center justify-center shrink-0 crm-icon-tile">
                  <ArrowRightIcon className="h-5 w-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-[#0A1628]">Добро пожаловать в OmniOS!</p>
                  <p className="text-sm text-slate-500 mt-0.5">Начните с добавления первого лида — AI-агент возьмёт всё остальное на себя.</p>
                </div>
                <Link to="/leads">
                  <Button size="sm" className="bg-gradient-to-r from-[#2461FF] to-[#7C3AED] text-white border-0 shrink-0">
                     Добавить первый лид
                  </Button>
                </Link>
              </div>
            </div>
          ) : null}

          {/* Stat cards */}
          <div className="px-4 lg:px-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 crm-stagger">
              <Card className="border-l-4 border-l-blue-500 rounded-lg crm-card">
                <CardContent className="px-4 pt-4 pb-4">
                  <div className="flex items-start justify-between mb-4">
                    <span className="text-sm font-medium text-muted-foreground">{t('dashboard.totalLeads')}</span>
                    <div className="h-8 w-8 rounded-lg bg-blue-50 dark:bg-blue-950 flex items-center justify-center shrink-0 crm-icon-tile">
                      <UsersIcon className="h-4 w-4 text-blue-500" />
                    </div>
                  </div>
                  <p className="text-3xl font-bold">{isLoading ? '—' : (stats?.total ?? 0)}</p>
                  <p className="text-xs text-muted-foreground mt-1">{t('dashboard.allLeadsInSystem')}</p>
                </CardContent>
              </Card>

              <Card className="border-l-4 border-l-emerald-500 rounded-lg crm-card">
                <CardContent className="px-4 pt-4 pb-4">
                  <div className="flex items-start justify-between mb-4">
                    <span className="text-sm font-medium text-muted-foreground">{t('dashboard.finalStage')}</span>
                    <div className="h-8 w-8 rounded-lg bg-emerald-50 dark:bg-emerald-950 flex items-center justify-center shrink-0 crm-icon-tile">
                      <CheckCircleIcon className="h-4 w-4 text-emerald-500" />
                    </div>
                  </div>
                  <p className="text-3xl font-bold">{isLoading ? '—' : finalCount}</p>
                  <p className="text-xs text-muted-foreground mt-1">{conversionRate}{t('dashboard.ofTotal')}</p>
                </CardContent>
              </Card>

              <Card className="border-l-4 border-l-violet-500 rounded-lg crm-card">
                <CardContent className="px-4 pt-4 pb-4">
                  <div className="flex items-start justify-between mb-4">
                    <span className="text-sm font-medium text-muted-foreground">{t('dashboard.convRate')}</span>
                    <div className="h-8 w-8 rounded-lg bg-violet-50 dark:bg-violet-950 flex items-center justify-center shrink-0 crm-icon-tile">
                      <BadgeCheckIcon className="h-4 w-4 text-violet-500" />
                    </div>
                  </div>
                  <p className="text-3xl font-bold">{isLoading ? '—' : `${conversionRate}%`}</p>
                  <p className="text-xs text-muted-foreground mt-1">{isLoading ? '—' : finalCount} {t('dashboard.inFinalStage')}</p>
                </CardContent>
              </Card>

              <Card className="border-l-4 border-l-orange-500 rounded-lg crm-card">
                <CardContent className="px-4 pt-4 pb-4">
                  <div className="flex items-start justify-between mb-4">
                    <span className="text-sm font-medium text-muted-foreground">{t('dashboard.inPipeline')}</span>
                    <div className="h-8 w-8 rounded-lg bg-orange-50 dark:bg-orange-950 flex items-center justify-center shrink-0 crm-icon-tile">
                      <TrendingUpIcon className="h-4 w-4 text-orange-500" />
                    </div>
                  </div>
                  <p className="text-3xl font-bold">{isLoading ? '—' : activeLeads}</p>
                  <p className="text-xs text-muted-foreground mt-1">{isLoading ? '—' : uniqueStages.length} {t('dashboard.stages')}</p>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Charts section */}
          <div className="px-4 lg:px-6">
            <div className="grid gap-4 md:grid-cols-2 crm-stagger">
              {/* Leads by Status - Pie Chart */}
              <Card className="crm-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">{t('dashboard.leadsByStatus')}</CardTitle>
                  <CardDescription className="text-xs">{t('dashboard.distributionAcrossStages')}</CardDescription>
                </CardHeader>
                <CardContent>
                  {statsStatus === 'pending' || stagesStatus === 'pending' ? (
                    <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
                  ) : (() => {
                    const pieData = uniqueStages
                      .map(stage => ({
                        name: stage.name,
                        value: stage.keys.reduce((sum, k) => sum + (stats?.[k] ?? 0), 0),
                      }))
                      .filter(d => d.value > 0)
                    return pieData.length === 0 ? (
                      <p className="text-sm text-muted-foreground">{t('common.noData')}</p>
                    ) : (
                      <div className="flex items-center gap-4">
                        <ResponsiveContainer width="50%" height={180}>
                          <PieChart>
                            <Pie
                              data={pieData}
                              cx="50%"
                              cy="50%"
                              innerRadius={45}
                              outerRadius={75}
                              paddingAngle={2}
                              dataKey="value"
                            >
                              {pieData.map((_, i) => (
                                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip
                              formatter={(value: number, name: string) => [value, name]}
                              contentStyle={{ fontSize: 12, borderRadius: 8 }}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                        <div className="flex flex-col gap-1.5 min-w-0">
                          {pieData.map((entry, i) => (
                            <div key={entry.name} className="flex items-center gap-2 min-w-0">
                              <span
                                className="h-2.5 w-2.5 rounded-full shrink-0"
                                style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                              />
                              <span className="text-xs text-muted-foreground truncate">{entry.name}</span>
                              <span className="text-xs font-medium ml-auto shrink-0">{entry.value}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })()}
                </CardContent>
              </Card>

              {/* Leads by Source - Bar Chart */}
              <Card className="crm-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">{t('dashboard.leadsBySource')}</CardTitle>
                  <CardDescription className="text-xs">{t('dashboard.whereLeadsComeFrom')}</CardDescription>
                </CardHeader>
                <CardContent>
                  {(() => {
                    const barData = sourceStats?.map(s => ({ source: getDiscoverySourceLabel(s.source), count: s.count })) ?? []
                    return barData.length === 0 ? (
                      <p className="text-sm text-muted-foreground">{t('dashboard.noSourceData')}</p>
                    ) : (
                      <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={barData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-muted" />
                          <XAxis
                            dataKey="source"
                            tick={{ fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                          />
                          <YAxis
                            tick={{ fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            allowDecimals={false}
                          />
                          <Tooltip
                            formatter={(value: number) => [value, 'Лиды']}
                            contentStyle={{ fontSize: 12, borderRadius: 8 }}
                          />
                          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                            {barData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    )
                  })()}
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Bottom section */}
          <div className="px-4 lg:px-6">
            <div className="grid gap-4 md:grid-cols-2 crm-stagger">
              {/* Lead pipeline breakdown */}
              <Card className="crm-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">{t('dashboard.leadPipeline')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {statsStatus === 'pending' || stagesStatus === 'pending' ? (
                    <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
                  ) : stats && uniqueStages && uniqueStages.length > 0 ? (
                    uniqueStages.map((stage, i) => {
                      const count = stage.keys.reduce((sum, k) => sum + (stats[k] ?? 0), 0)
                      const total = stats.total || 1
                      const pct = Math.round((count / total) * 100)
                      const color = BAR_COLORS[i % BAR_COLORS.length]
                      return (
                        <div key={stage.id} className="flex items-center gap-3">
                          <span className="w-28 text-sm text-muted-foreground shrink-0 truncate" title={stage.name}>{stage.name}</span>
                          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden min-w-0">
                            <div
                              className={`h-full rounded-full ${color} crm-progress-fill`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="w-6 text-sm font-medium text-right shrink-0">{count}</span>
                        </div>
                      )
                    })
                  ) : (
                    <p className="text-sm text-muted-foreground">{t('dashboard.noStagesConfigured')}</p>
                  )}
                  <div className="pt-2">
                    <Link to="/leads">
                      <Button variant="outline" size="sm" className="w-full">
                        {t('dashboard.viewAllLeads')}
                        <ArrowRightIcon className="h-3.5 w-3.5 ml-1.5" />
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>

              {/* Recent leads */}
              <Card className="crm-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">{t('dashboard.recentLeads')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  {leadsStatus === 'pending' ? (
                    <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
                  ) : recentLeads.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{t('dashboard.noLeadsYet')}</p>
                  ) : (
                    recentLeads.map(lead => (
                      <Link key={lead.id} to="/leads/$leadId" params={{ leadId: String(lead.id) }} className="block">
                        <div className="flex items-center justify-between py-2 px-2 rounded-md hover:bg-muted/50 crm-list-row">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{lead.contact_person}</p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0 ml-2">
                            <Badge variant="outline" className="text-xs hidden sm:inline-flex">
                              {stageNameMap[lead.status] ?? getLeadStatusLabel(lead.status)}
                            </Badge>
                            <span className="text-xs text-muted-foreground">{formatRelativeTime(lead.created_at)}</span>
                          </div>
                        </div>
                      </Link>
                    ))
                  )}
                  <div className="pt-2">
                    <Link to="/leads">
                      <Button variant="outline" size="sm" className="w-full">
                        {t('dashboard.viewAllLeads')}
                        <ArrowRightIcon className="h-3.5 w-3.5 ml-1.5" />
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
