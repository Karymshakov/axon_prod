import { createFileRoute, Navigate } from '@tanstack/react-router'

export const Route = createFileRoute('/adminka')({
  component: AdminkaRedirect,
})

function AdminkaRedirect() {
  return <Navigate to="/super-admin" />
}
