import { createContext, useContext, useState, useEffect, useRef, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getAccessToken, getRefreshToken, clearTokens, login as loginApi, logout as logoutApi, getMe, type User } from '@/lib/api'
import { useLanguage } from '@/contexts/language-context'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  updateUser: (updates: Partial<User>) => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const queryClient = useQueryClient()
  const { syncFromServer } = useLanguage()
  // Синхронизируем язык из БД только ОДИН РАЗ — при первой загрузке профиля
  const didSyncLanguage = useRef(false)

  useEffect(() => {
    const token = getAccessToken()
    if (token) {
      getMe()
        .then((me) => {
          setUser(me)
          // Синхронизируем язык из профиля только при первом входе/загрузке
          if (!didSyncLanguage.current && me.language) {
            didSyncLanguage.current = true
            syncFromServer(me.language)
          }
        })
        .catch(() => clearTokens())
        .finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [syncFromServer])

  // When the API client fails to refresh the access token, clear state so the
  // route guard redirects to /login instead of staying stuck "logged in"
  useEffect(() => {
    const handleSessionExpired = () => {
      clearTokens()
      queryClient.clear()
      setUser(null)
      didSyncLanguage.current = false
    }
    window.addEventListener('auth:session-expired', handleSessionExpired)
    return () => window.removeEventListener('auth:session-expired', handleSessionExpired)
  }, [queryClient])

  // Keep browser tabs in sync: a real logout (tokens cleared) in one tab
  // must log out the others too, instead of leaving them silently "logged in"
  // against a session that no longer exists server-side.
  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== 'access_token' && event.key !== 'refresh_token') return
      if (!getAccessToken() && !getRefreshToken()) {
        queryClient.clear()
        setUser(null)
        didSyncLanguage.current = false
      }
    }
    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [queryClient])

  const login = async (email: string, password: string) => {
    const response = await loginApi(email, password)
    setUser(response.user)
    // При логине тоже синхронизируем язык из профиля (если пользователь не менял сам)
    if (response.user.language) {
      syncFromServer(response.user.language)
    }
    didSyncLanguage.current = true
  }

  const logout = async () => {
    await logoutApi()
    queryClient.clear()
    setUser(null)
    didSyncLanguage.current = false
  }

  const updateUser = (updates: Partial<User>) => {
    setUser(prev => prev ? { ...prev, ...updates } : null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
