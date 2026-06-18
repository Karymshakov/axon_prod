import { createContext, useContext, useState, useRef, useCallback, useMemo, type ReactNode } from 'react'
import { createT, type Language, type TFunction } from '@/lib/translations'
import { getAccessToken, updateUserLanguage } from '@/lib/api'

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  /** Синхронизировать язык из сервера — только если пользователь не менял сам */
  syncFromServer: (lang: Language) => void
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

  // Флаг: менял ли пользователь язык вручную в этой сессии.
  // Если да — не позволяем auth-context перетирать выбор.
  const userOverrodeRef = useRef(false)

  const setLanguage = useCallback((lang: Language, isUserAction = true) => {
    if (isUserAction) {
      userOverrodeRef.current = true
    }
    setLanguageState(lang)
    try {
      localStorage.setItem('crm_language', lang)
    } catch {
      // ignore
    }
    // Persist to backend only on explicit user action
    if (isUserAction && getAccessToken()) {
      updateUserLanguage(lang).catch(() => {
        // Silently ignore — preference saved in localStorage regardless
      })
    }
  }, [])

  // Метод для auth-context: синхронизировать язык из БД ТОЛЬКО если
  // пользователь НЕ менял язык вручную в этой сессии
  const syncFromServer = useCallback((lang: Language) => {
    if (!userOverrodeRef.current) {
      setLanguageState(lang)
      try {
        localStorage.setItem('crm_language', lang)
      } catch {
        // ignore
      }
    }
  }, [])

  const t = useMemo(() => createT(language), [language])

  const contextValue = useMemo(
    () => ({ language, setLanguage, t, syncFromServer }),
    [language, setLanguage, t, syncFromServer],
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
