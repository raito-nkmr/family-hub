import { useEffect, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CloseIcon } from './icons'

interface DialogProps {
  titleId: string
  children: ReactNode
  className?: string
  overlayClassName?: string
  closeClassName?: string
  closeLabel?: string
  size?: 'compact' | 'default' | 'medium' | 'large' | 'extra-large'
  surface?: 'default' | 'media'
  busy?: boolean
  onClose: () => void
}

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function Dialog({
  titleId,
  children,
  className = '',
  overlayClassName = '',
  closeClassName = '',
  closeLabel,
  size = 'default',
  surface = 'default',
  busy = false,
  onClose,
}: DialogProps) {
  const { t } = useTranslation()
  const panelRef = useRef<HTMLDivElement>(null)
  const busyRef = useRef(busy)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    busyRef.current = busy
    onCloseRef.current = onClose
  }, [busy, onClose])
  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const panel = panelRef.current
    const backgroundElements: Array<{ element: HTMLElement; wasInert: boolean }> = []
    let current: HTMLElement | null = panel?.closest<HTMLElement>('[role="dialog"]') ?? null
    while (current?.parentElement && current.parentElement !== document.body) {
      for (const sibling of current.parentElement.children) {
        if (sibling !== current && sibling instanceof HTMLElement) {
          backgroundElements.push({ element: sibling, wasInert: Boolean(sibling.inert) })
          sibling.inert = true
        }
      }
      current = current.parentElement
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busyRef.current) {
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const focusable = [...(panel?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [])]
      if (focusable.length === 0) {
        event.preventDefault()
        panel?.focus()
        return
      }
      const first = focusable[0]
      const last = focusable.at(-1)
      if (event.shiftKey && (document.activeElement === first || !panel?.contains(document.activeElement))) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && (document.activeElement === last || !panel?.contains(document.activeElement))) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    document.body.classList.add('modal-open')
    const initialFocus =
      panel?.querySelector<HTMLElement>('[data-dialog-autofocus="true"]') ??
      panel?.querySelector<HTMLElement>('[autofocus]') ??
      panel?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
    initialFocus?.focus()
    if (!initialFocus) panel?.focus()
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.classList.remove('modal-open')
      for (const { element, wasInert } of backgroundElements) element.inert = wasInert
      previouslyFocused?.focus()
    }
  }, [])

  return (
    <div
      className={`dialog ${overlayClassName}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-busy={busy || undefined}
      onMouseDown={(event) => {
        if (!busy && event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        className={`dialog__panel dialog__panel--size-${size} dialog__panel--surface-${surface} ${className}`}
        tabIndex={-1}
      >
        <button
          className={`dialog__close ${closeClassName}`}
          type="button"
          onClick={onClose}
          disabled={busy}
          aria-label={closeLabel ?? t('common.closeDialog')}
        >
          <CloseIcon />
        </button>
        {children}
      </div>
    </div>
  )
}
