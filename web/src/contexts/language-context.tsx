import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { createT, type Language, type TFunction } from '@/lib/translations'
import { getAccessToken, updateUserLanguage } from '@/lib/api'

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  t: TFunction
}

const LanguageContext = createContext<LanguageContextType | null>(null)

function detectLanguage(): Language {
  // 1. Check localStorage first
  const stored = localStorage.getItem('crm_language')
  if (stored === 'en' || stored === 'ru') return stored
  // 2. Check browser language
  const browserLang = navigator.language?.slice(0, 2).toLowerCase()
  if (browserLang === 'ru') return 'ru'
  // 3. Default to Russian
  return 'ru'
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>('ru')

  // Detect language on client side to avoid SSR mismatch
  useEffect(() => {
    setLanguageState(detectLanguage())
  }, [])

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang)
    localStorage.setItem('crm_language', lang)
    // Persist to backend if logged in
    if (getAccessToken()) {
      updateUserLanguage(lang).catch(() => {
        // Silently ignore — preference saved in localStorage regardless
      })
    }
  }, [])

  const t = createT(language)

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider')
  }
  return context
}
