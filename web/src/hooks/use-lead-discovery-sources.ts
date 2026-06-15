import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchOrganizations } from '@/lib/api'
import { getLeadDiscoverySourceOptions } from '@/lib/org-settings'
import { useAuth } from '@/contexts/auth-context'

export function useLeadDiscoverySources() {
  const { user } = useAuth()
  const { data: organizations = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: fetchOrganizations,
    enabled: !!user,
  })

  const currentOrganization = organizations.find((organization) => (
    organization.slug === user?.current_organization_slug
  ))

  return useMemo(
    () => getLeadDiscoverySourceOptions(currentOrganization?.org_settings),
    [currentOrganization?.org_settings],
  )
}
