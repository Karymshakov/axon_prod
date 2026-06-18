import { createFileRoute, Outlet, Link, useNavigate, Navigate } from '@tanstack/react-router'
import { UsersIcon, SettingsIcon, ChevronLeftIcon, ChevronRightIcon, MessageSquareIcon, LogOutIcon, UserIcon, Loader2Icon, FileTextIcon, LayoutDashboardIcon, ShieldIcon, HotelIcon, GitBranchIcon, BuildingIcon, CheckIcon, PlusCircleIcon, ChevronsUpDownIcon } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/contexts/auth-context'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCommunicationsUnreadCounts, fetchOrganizations, switchOrganization, type Organization, type User } from '@/lib/api'
import { useState } from 'react'

export const Route = createFileRoute('/_app')({
  component: AppLayout,
})

function isOrganizationAdmin(user: User | null | undefined) {
  return Boolean(
    user?.is_superadmin ||
    user?.is_admin ||
    user?.current_organization_role === 'owner' ||
    user?.current_organization_role === 'admin',
  )
}

function SidebarToggleButton() {
  const { toggleSidebar, state } = useSidebar()
  const isCollapsed = state === 'collapsed'

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleSidebar}
      className="ml-auto h-8 w-8 rounded-full bg-muted/50 hover:bg-muted"
    >
      {isCollapsed ? (
        <ChevronRightIcon className="h-4 w-4" />
      ) : (
        <ChevronLeftIcon className="h-4 w-4" />
      )}
      <span className="sr-only">Свернуть меню</span>
    </Button>
  )
}

function OrgSwitcher() {
  const { user, updateUser } = useAuth()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const { state: sidebarState } = useSidebar()
  const isCollapsed = sidebarState === 'collapsed'
  const canManageOrganization = isOrganizationAdmin(user)

  const { data: orgs = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: fetchOrganizations,
    enabled: !!user,
    networkMode: 'always',
  })

  const handleSwitch = async (org: Organization) => {
    if (org.slug === user?.current_organization_slug) {
      setOpen(false)
      return
    }
    await switchOrganization(org.slug)
    updateUser({
      current_organization_id: org.id,
      current_organization_slug: org.slug,
      current_organization_name: org.name,
      current_organization_role: org.current_user_role,
    })
    queryClient.clear()
    setOpen(false)
  }

  const currentOrgName = user?.current_organization_name || 'Без организации'

  if (isCollapsed) {
    return (
      <div className="flex items-center justify-center p-1">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
          <BuildingIcon className="h-4 w-4 text-primary" />
        </div>
      </div>
    )
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10">
            <BuildingIcon className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="flex-1 truncate font-semibold">{currentOrgName}</span>
          {orgs.length > 1 && <ChevronsUpDownIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
        </button>
      </DropdownMenuTrigger>
      {orgs.length > 0 && (
        <DropdownMenuContent className="w-64" align="start" side="bottom">
          {orgs.map(org => (
            <DropdownMenuItem key={org.id} onClick={() => handleSwitch(org)} className="gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-muted">
                <BuildingIcon className="h-3 w-3" />
              </div>
              <span className="flex-1 truncate">{org.name}</span>
              {org.slug === user?.current_organization_slug && (
                <CheckIcon className="h-3.5 w-3.5 text-primary" />
              )}
            </DropdownMenuItem>
          ))}
          {canManageOrganization && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/settings" search={{ tab: 'organization' }} className="gap-2 cursor-pointer">
                  <PlusCircleIcon className="h-3.5 w-3.5" />
                  <span>Управление организацией</span>
                </Link>
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      )}
    </DropdownMenu>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const { t } = useLanguage()
  const navigate = useNavigate()
  const canUseAdminTools = isOrganizationAdmin(user) || Boolean(user?.is_admin)

  const handleLogout = async () => {
    await logout()
    navigate({ to: '/' })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton
          size="lg"
          className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-400 to-cyan-500 text-white">
            <UserIcon className="h-4 w-4" />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-semibold">{user?.name || 'Пользователь'}</span>
            <span className="truncate text-xs text-muted-foreground">{user?.email}</span>
          </div>
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="w-[--radix-dropdown-menu-trigger-width] min-w-56"
        side="top"
        align="start"
        sideOffset={4}
      >
        {user?.is_superadmin && (
          <>
            <DropdownMenuItem onClick={() => navigate({ to: '/super-admin' })}>
              <ShieldIcon className="mr-2 h-4 w-4 text-violet-500" />
              Супер-админ
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        {canUseAdminTools && (
          <>
            <DropdownMenuItem onClick={() => navigate({ to: '/portal/users', search: { search: '', role: '', status: '', ordering: '-created_at' } })}>
              <ShieldIcon className="mr-2 h-4 w-4" />
              {t('nav.adminPortal')}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate({ to: '/audit-logs' })}>
              <FileTextIcon className="mr-2 h-4 w-4" />
              {t('nav.auditLogs')}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onClick={handleLogout} className="text-red-600">
          <LogOutIcon className="mr-2 h-4 w-4" />
          {t('nav.signOut')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function AppLayout() {
  const { isAuthenticated, isLoading, user } = useAuth()
  const { t } = useLanguage()
  const canManageWorkspace = isOrganizationAdmin(user)

  const { data: unreadData } = useQuery({
    queryKey: ['communications-unread-counts'],
    queryFn: fetchCommunicationsUnreadCounts,
    refetchInterval: 30_000,
    networkMode: 'always',
  })
  const totalUnread = unreadData?.total ?? 0

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" />
  }

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full overflow-hidden crm-shell">
        <Sidebar collapsible="icon" className="border-r-border/70">
          <SidebarHeader className="p-2 crm-panel">
            <div className="flex items-center gap-1 group-data-[collapsible=icon]:justify-center">
              <div className="flex-1 min-w-0 group-data-[collapsible=icon]:hidden">
                <OrgSwitcher />
              </div>
              <SidebarToggleButton />
            </div>
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild tooltip={t('nav.dashboard')} className="crm-list-row">
                      <Link to="/dashboard">
                        <LayoutDashboardIcon />
                        <span>{t('nav.dashboard')}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild tooltip={t('nav.leads')} className="crm-list-row">
                      <Link to="/leads">
                        <UsersIcon />
                        <span>{t('nav.leads')}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild tooltip={t('nav.communications')} className="crm-list-row">
                      <Link to="/communications" search={{ leadId: undefined, channel: undefined }}>
                        <MessageSquareIcon />
                        <span>{t('nav.communications')}</span>
                        {totalUnread > 0 && (
                          <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[11px] font-semibold text-white crm-live-dot">
                            {totalUnread > 99 ? '99+' : totalUnread}
                          </span>
                        )}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  {canManageWorkspace && (
                    <SidebarMenuItem>
                      <SidebarMenuButton asChild tooltip={t('nav.aiFlows')} className="crm-list-row">
                        <Link to="/flows">
                          <GitBranchIcon />
                          <span>{t('nav.aiFlows')}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )}
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild tooltip={t('nav.hotelDetails')} className="crm-list-row">
                      <Link to="/hotel-details">
                        <HotelIcon />
                        <span>{t('nav.hotelDetails')}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild tooltip={t('nav.settings')} className="crm-list-row">
                      <Link to="/settings" search={{ tab: canManageWorkspace ? 'general' : 'preferences' }}>
                        <SettingsIcon />
                        <span>{t('nav.settings')}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter className="crm-panel">
            <SidebarMenu>
              <SidebarMenuItem>
                <UserMenu />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarFooter>
        </Sidebar>
        <div className="flex flex-1 flex-col min-w-0 min-h-0 overflow-hidden">
          <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4 md:hidden">
            <SidebarTrigger />
            <Separator orientation="vertical" className="h-4" />
            <span className="font-semibold">{t('nav.crm')}</span>
          </header>
          <main className="flex flex-1 flex-col min-w-0 min-h-0 overflow-auto crm-workspace">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}
