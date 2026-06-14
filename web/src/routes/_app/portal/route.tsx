import { createFileRoute, Outlet, Navigate } from '@tanstack/react-router'
import { useAuth } from '@/contexts/auth-context'

export const Route = createFileRoute('/_app/portal')({
  component: AdminGuard,
})

function AdminGuard() {
  const { user } = useAuth()

  if (!user?.is_admin) {
    return <Navigate to="/dashboard" />
  }

  return <Outlet />
}
