import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { en } from './resources/en'
import { ja } from './resources/ja'

export type AppLanguage = 'en' | 'ja'

export const DEFAULT_LANGUAGE: AppLanguage = 'en'
export const LANGUAGE_STORAGE_KEY = 'family-hub-language'

function readStoredLanguage(): AppLanguage {
  try {
    return localStorage.getItem(LANGUAGE_STORAGE_KEY) === 'ja' ? 'ja' : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, ja: { translation: ja } },
  lng: readStoredLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: ['en', 'ja'],
  interpolation: { escapeValue: false },
})

export function setDocumentLanguage(language: AppLanguage): void {
  document.documentElement.lang = language
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  } catch {
    // The language still applies when browser storage is unavailable.
  }
}

setDocumentLanguage(i18n.resolvedLanguage === 'ja' ? 'ja' : DEFAULT_LANGUAGE)
i18n.on('languageChanged', (language) => setDocumentLanguage(language === 'ja' ? 'ja' : DEFAULT_LANGUAGE))

export default i18n
