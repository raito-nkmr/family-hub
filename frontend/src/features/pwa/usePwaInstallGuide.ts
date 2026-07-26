import { useState } from 'react'

const DISMISSED_STORAGE_KEY = 'family-hub-pwa-install-prompt-dismissed'

interface NavigatorWithStandalone extends Navigator {
  standalone?: boolean
}

export function isStandaloneMode(): boolean {
  const displayModeStandalone =
    typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches
  const iosStandalone = (window.navigator as NavigatorWithStandalone).standalone === true
  return displayModeStandalone || iosStandalone
}

function readPromptDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

export function usePwaInstallGuide() {
  const [standalone] = useState(isStandaloneMode)
  const [guideOpen, setGuideOpen] = useState(false)
  const [homePromptVisible, setHomePromptVisible] = useState(() => !standalone && !readPromptDismissed())

  const dismissHomePrompt = () => {
    setHomePromptVisible(false)
    try {
      localStorage.setItem(DISMISSED_STORAGE_KEY, 'true')
    } catch {
      // The prompt still closes when browser storage is unavailable.
    }
  }

  return {
    guideOpen,
    homePromptVisible,
    installGuideAvailable: !standalone,
    openGuide: () => setGuideOpen(true),
    closeGuide: () => setGuideOpen(false),
    dismissHomePrompt,
  }
}
