import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { superAdminListOrgs } from '@/lib/api'
import { BuildingIcon, UsersIcon, TrendingUpIcon, ActivityIcon } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export const Route = createFileRoute('/super-admin/')({
  component: SuperAdminDashboard,
})

function SuperAdminDashboard() {
  const { data: orgs = [], isLoading } = useQuery({
    queryKey: ['superadmin-orgs'],
    queryFn: superAdminListOrgs,
  })

  const totalOrgs = orgs.length
  const activeOrgs = orgs.filter(o => o.is_active).length
  const totalMembers = orgs.reduce((sum, o) => sum + (o.member_count || 0), 0)
  const planCounts = orgs.reduce((acc, o) => {
    acc[o.plan] = (acc[o.plan] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const stats = [
    { label: 'Total Organizations', value: totalOrgs, icon: BuildingIcon, color: 'text-violet-400' },
    { label: 'Active Organizations', value: activeOrgs, icon: ActivityIcon, color: 'text-emerald-400' },
    { label: 'Total Members', value: totalMembers, icon: UsersIcon, color: 'text-blue-400' },
    { label: 'Enterprise Plans', value: planCounts['enterprise'] || 0, icon: TrendingUpIcon, color: 'text-amber-400' },
  ]

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 text-sm mt-1">Platform overview</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(s => (
          <Card key={s.label} className="bg-gray-900 border-gray-800">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-gray-400">{s.label}</CardTitle>
              <s.icon className={`h-4 w-4 ${s.color}`} />
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-white">{isLoading ? '—' : s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white text-base">Organizations by Plan</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {['free', 'starter', 'pro', 'enterprise'].map(plan => (
                <div key={plan} className="flex items-center justify-between">
                  <span className="capitalize text-sm text-gray-300">{plan}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-violet-500 rounded-full origin-left"
                        style={{ transform: `scaleX(${totalOrgs > 0 ? (planCounts[plan] || 0) / totalOrgs : 0})` }}
                      />
                    </div>
                    <span className="text-sm font-mono text-gray-400 w-6 text-right">{planCounts[plan] || 0}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white text-base">Recent Organizations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {orgs.slice(0, 6).map(org => (
                <div key={org.id} className="flex items-center justify-between text-sm">
                  <span className="text-gray-200 font-medium truncate flex-1">{org.name}</span>
                  <span className={`ml-2 px-1.5 py-0.5 rounded text-xs capitalize ${
                    org.is_active ? 'bg-emerald-900/50 text-emerald-400' : 'bg-red-900/50 text-red-400'
                  }`}>{org.is_active ? 'active' : 'inactive'}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
