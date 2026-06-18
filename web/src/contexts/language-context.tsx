import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react'
import { createT, type Language, type TFunction } from '@/lib/translations'
import { getAccessToken, updateUserLanguage } from '@/lib/api'

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  t: TFunction
}

const LanguageContext = createContext<LanguageContextType | null>(null)

function detectLanguage(): Language {
  try {
    const stored = localStorage.getItem('crm_language')
    if (stored === 'en' || stored === 'ru') return stored
  } catch {
    // localStorage недоступен (SSR или режим приватности)
  }
  return 'ru'
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  // Ленивый инициализатор — читает localStorage один раз при монтировании,
  // без лишнего useEffect и двойного рендера
  const [language, setLanguageState] = useState<Language>(detectLanguage)

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang)
    try {
      localStorage.setItem('crm_language', lang)
    } catch {
      // ignore
    }
    // Persist to backend if logged in
    if (getAccessToken()) {
      updateUserLanguage(lang).catch(() => {
        // Silently ignore — preference saved in localStorage regardless
      })
    }
  }, [])

  const t = useMemo(() => createT(language), [language])

  // Стабилизируем объект value — React гарантированно перерисует
  // всех consumer'ов только когда language или t реально изменятся
  const contextValue = useMemo(
    () => ({ language, setLanguage, t }),
    [language, setLanguage, t],
  )

  return (
    <LanguageContext.Provider value={contextValue}>
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
