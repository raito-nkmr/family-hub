import type { ReactNode } from 'react'

export type PhotoBadgeVariant = 'favorite' | 'video' | 'shared'
export type PhotoBadgePosition = 'top-left' | 'top-right' | 'bottom-right'

interface PhotoBadgeProps {
  variant: PhotoBadgeVariant
  position: PhotoBadgePosition
  label: string
  icon?: ReactNode
  children?: ReactNode
}

export function PhotoBadge({ variant, position, label, icon, children }: PhotoBadgeProps) {
  return (
    <span className={`photo-badge photo-badge--${variant} photo-badge--${position}`} aria-label={label} title={label}>
      {icon && (
        <span className="photo-badge__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      {children && <span className="photo-badge__label">{children}</span>}
    </span>
  )
}
