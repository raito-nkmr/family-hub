import { Component, type ErrorInfo, type ReactNode } from 'react'
import i18n from '../i18n'
import { RetryIcon } from '../shared/ui/icons'

interface AppErrorBoundaryProps {
  children: ReactNode
}

interface AppErrorBoundaryState {
  hasError: boolean
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Uncaught application error', error, info.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <main className="fatal-error" role="alert">
        <div className="fatal-error__panel">
          <p className="fatal-error__eyebrow">FAMILY HUB</p>
          <h1>{i18n.t('appError.title')}</h1>
          <p>{i18n.t('appError.description')}</p>
          <button className="secondary-button icon-button" type="button" onClick={() => window.location.reload()}>
            <RetryIcon />
            {i18n.t('appError.reload')}
          </button>
        </div>
      </main>
    )
  }
}
