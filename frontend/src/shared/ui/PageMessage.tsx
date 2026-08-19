import type { ReactNode } from 'react'

interface PageMessageProps {
  children: ReactNode
  variant?: 'error' | 'success' | 'neutral'
  role?: 'alert' | 'status'
  className?: string
}

export function PageMessage({ children, variant = 'error', role, className }: PageMessageProps) {
  const classes = ['page-message', `page-message--${variant}`, className].filter(Boolean).join(' ')
  const resolvedRole = role ?? (variant === 'error' ? 'alert' : 'status')

  return (
    <div className={classes} role={resolvedRole}>
      {children}
    </div>
  )
}
