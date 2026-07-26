import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router'
import '@fontsource-variable/noto-sans-jp'
import './i18n'
import './index.css'
import App from './App.tsx'
import { AppErrorBoundary } from './app/AppErrorBoundary.tsx'
import { queryClient } from './shared/api/queryClient.ts'
import { ConfirmationDialogProvider } from './shared/ui/ConfirmationDialog.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ConfirmationDialogProvider>
          <AppErrorBoundary>
            <App />
          </AppErrorBoundary>
        </ConfirmationDialogProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js').then(async () => {
      const badgeNavigator = navigator as Navigator & { clearAppBadge?: () => Promise<void> }
      await badgeNavigator.clearAppBadge?.().catch(() => undefined)
      const registration = await navigator.serviceWorker.ready
      registration.active?.postMessage({ type: 'CLEAR_BADGE' })
    })
  })
}
