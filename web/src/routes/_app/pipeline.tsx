import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/pipeline')({
  beforeLoad: () => {
    throw redirect({ to: '/leads' })
  },
  component: () => null,
})
