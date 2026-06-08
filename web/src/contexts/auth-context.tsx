import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getAccessToken, clearTokens, login as loginApi, logout as logoutApi, getMe, type User } from '@/lib/api'
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
  const { language: currentLang, setLanguage } = useLanguage()

  useEffect(() => {
    const token = getAccessToken()
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => clearTokens())
        .finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [])

  // Sync language with user preference from DB
  useEffect(() => {
    if (user?.language && user.language !== currentLang) {
      setLanguage(user.language)
    }
  }, [user?.language, currentLang, setLanguage])

  // When the API client fails to refresh the access token, clear state so the
  // route guard redirects to /login instead of staying stuck "logged in"
  useEffect(() => {
    const handleSessionExpired = () => {
      clearTokens()
      queryClient.clear()
      setUser(null)
    }
    window.addEventListener('auth:session-expired', handleSessionExpired)
    return () => window.removeEventListener('auth:session-expired', handleSessionExpired)
  }, [])

  const login = async (email: string, password: string) => {
    const response = await loginApi(email, password)
    setUser(response.user)
  }

  const logout = async () => {
    await logoutApi()
    queryClient.clear()
    setUser(null)
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
