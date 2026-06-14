import { Outlet, createRootRoute, Link } from '@tanstack/react-router'
import { AuthProvider } from '@/contexts/auth-context'
import { LanguageProvider } from '@/contexts/language-context'

function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Страница не найдена</h1>
        <p className="text-gray-600 mb-4">Запрашиваемая страница не существует.</p>
        <Link to="/" className="text-blue-500 hover:underline">На главную</Link>
      </div>
    </div>
  )
}

export const Route = createRootRoute({
  component: () => (
    <LanguageProvider>
      <AuthProvider>
        <div className="min-h-screen bg-gray-50">
          <Outlet />
        </div>
      </AuthProvider>
    </LanguageProvider>
  ),
  notFoundComponent: NotFound,
})
