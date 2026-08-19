import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: ReactNode
  title: ReactNode
  description: ReactNode
  titleAs?: 'h2' | 'h3' | 'strong'
  className?: string
}

export function EmptyState({ icon, title, description, titleAs = 'h3', className }: EmptyStateProps) {
  const Title = titleAs
  const classes = ['empty-state', className].filter(Boolean).join(' ')

  return (
    <div className={classes}>
      <span>{icon}</span>
      <Title>{title}</Title>
      <p>{description}</p>
    </div>
  )
}
