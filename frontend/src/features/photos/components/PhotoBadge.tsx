import type { ReactNode } from 'react'

export type PhotoBadgeVariant = 'favorite' | 'video' | 'shared' | 'selection'
export type PhotoBadgePosition = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

interface PhotoBadgeProps {
  variant: PhotoBadgeVariant
  position: PhotoBadgePosition
  label: string
  icon?: ReactNode
  active?: boolean
  children?: ReactNode
}

export function PhotoBadge({ variant, position, label, icon, active = false, children }: PhotoBadgeProps) {
  return (
    <span
      className={`photo-badge photo-badge--${variant} photo-badge--${position}${active ? ' photo-badge--active' : ''}`}
      aria-label={label}
      title={label}
    >
      {icon && (
        <span className="photo-badge__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      {children && <span className="photo-badge__label">{children}</span>}
    </span>
  )
}
