import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { superAdminListOrgs, superAdminUpdateOrg, type SuperAdminOrg } from '@/lib/api'
import { BuildingIcon, SearchIcon } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger } from '@/components/ui/select'

export const Route = createFileRoute('/super-admin/organizations')({
  component: SuperAdminOrgs,
})

const PLAN_COLORS: Record<string, string> = {
  free: 'bg-gray-700 text-gray-300',
  starter: 'bg-blue-900/50 text-blue-300',
  pro: 'bg-violet-900/50 text-violet-300',
  enterprise: 'bg-amber-900/50 text-amber-300',
}

const PLAN_OPTIONS: { value: SuperAdminOrg['plan']; label: string }[] = [
  { value: 'free', label: 'Free' },
  { value: 'starter', label: 'Starter' },
  { value: 'pro', label: 'Pro' },
  { value: 'enterprise', label: 'Enterprise' },
]

const FILTER_OPTIONS = [
  { value: 'all', label: 'All plans' },
  { value: 'free', label: 'Free' },
  { value: 'starter', label: 'Starter' },
  { value: 'pro', label: 'Pro' },
  { value: 'enterprise', label: 'Enterprise' },
]

function SuperAdminOrgs() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState('all')

  const { data: orgs = [], isLoading } = useQuery({
    queryKey: ['superadmin-orgs'],
    queryFn: superAdminListOrgs,
    networkMode: 'always',
  })

  const updateMutation = useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: Parameters<typeof superAdminUpdateOrg>[1] }) =>
      superAdminUpdateOrg(slug, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['superadmin-orgs'] }),
  })

  const filtered = orgs.filter(o => {
    const matchSearch = !search || o.name.toLowerCase().includes(search.toLowerCase()) || o.owner_email.toLowerCase().includes(search.toLowerCase())
    const matchPlan = planFilter === 'all' || o.plan === planFilter
    return matchSearch && matchPlan
  })

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Organizations</h1>
        <p className="text-gray-400 text-sm mt-1">{orgs.length} total organizations</p>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1 max-w-sm">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <Input
            name="search"
            placeholder="Search organizations..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9 bg-gray-900 border-gray-700 text-white placeholder:text-gray-500"
          />
        </div>
        <Select value={planFilter} onValueChange={setPlanFilter}>
          <SelectTrigger name="plan-filter" className="w-36 bg-gray-900 border-gray-700 text-gray-300">
            <span>{FILTER_OPTIONS.find(o => o.value === planFilter)?.label}</span>
          </SelectTrigger>
          <SelectContent className="bg-gray-900 border-gray-700">
            {FILTER_OPTIONS.map(o => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Card className="bg-gray-900 border-gray-800">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No organizations found</div>
          ) : (
            <div className="divide-y divide-gray-800">
              {filtered.map(org => (
                <div key={org.id} className="flex items-center gap-4 px-4 py-3 hover:bg-gray-800/50 transition-colors">
                  <div className="h-8 w-8 rounded bg-violet-900/50 flex items-center justify-center shrink-0">
                    <BuildingIcon className="h-4 w-4 text-violet-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-white text-sm truncate">{org.name}</p>
                    <p className="text-xs text-gray-500 truncate">{org.owner_email} · {org.member_count} member{org.member_count !== 1 ? 's' : ''}</p>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${PLAN_COLORS[org.plan] || PLAN_COLORS.free}`}>
                    {org.plan}
                  </span>
                  <Select
                    value={org.plan}
                    onValueChange={plan => updateMutation.mutate({ slug: org.slug, data: { plan: plan as SuperAdminOrg['plan'] } })}
                  >
                    <SelectTrigger name={`plan-${org.slug}`} className="h-7 w-28 bg-gray-800 border-gray-700 text-xs text-gray-300">
                      <span>{PLAN_OPTIONS.find(o => o.value === org.plan)?.label}</span>
                    </SelectTrigger>
                    <SelectContent className="bg-gray-900 border-gray-700">
                      {PLAN_OPTIONS.map(o => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Switch
                    checked={org.is_active}
                    onCheckedChange={checked => updateMutation.mutate({ slug: org.slug, data: { is_active: checked } })}
                    className="data-[state=checked]:bg-emerald-500"
                  />
                  <span className="text-xs text-gray-500">{new Date(org.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
