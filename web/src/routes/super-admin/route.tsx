import { createFileRoute, Outlet, Link, useNavigate, Navigate } from '@tanstack/react-router'
import { BuildingIcon, LayoutDashboardIcon, LogOutIcon, ChevronLeftIcon, Loader2Icon } from 'lucide-react'
import { useAuth } from '@/contexts/auth-context'

export const Route = createFileRoute('/super-admin')({
  component: SuperAdminLayout,
})

function SuperAdminLayout() {
  const { user, isLoading, logout } = useAuth()
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-950">
        <Loader2Icon className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!user || !user.is_superadmin) {
    return <Navigate to="/dashboard" />
  }

  const handleLogout = async () => {
    await logout()
    navigate({ to: '/' })
  }

  return (
    <div className="flex min-h-screen bg-gray-950 text-gray-100">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-5 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-violet-600 flex items-center justify-center">
              <BuildingIcon className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-xs font-bold text-white">Super Admin</p>
              <p className="text-xs text-gray-500">{user.email}</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          <Link
            to="/super-admin"
            className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors [&.active]:bg-gray-800 [&.active]:text-white"
          >
            <LayoutDashboardIcon className="h-4 w-4" />
            Dashboard
          </Link>
          <Link
            to="/super-admin/organizations"
            className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors [&.active]:bg-gray-800 [&.active]:text-white"
          >
            <BuildingIcon className="h-4 w-4" />
            Organizations
          </Link>
        </nav>
        <div className="p-3 border-t border-gray-800 space-y-1">
          <Link
            to="/dashboard"
            className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <ChevronLeftIcon className="h-4 w-4" />
            Back to app
          </Link>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-800 hover:text-red-400 transition-colors"
          >
            <LogOutIcon className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
