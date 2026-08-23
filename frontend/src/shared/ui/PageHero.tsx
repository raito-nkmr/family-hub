import type { ReactNode } from 'react'

interface PageHeroProps {
  eyebrow: string
  title: string
  description: string
  actions?: ReactNode
}

export function PageHero({ eyebrow, title, description, actions }: PageHeroProps) {
  return (
    <section className={`page-hero${actions ? ' page-hero--with-action' : ''}`}>
      <div className="page-hero__content">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-hero__description">{description}</p>
      </div>
      {actions && <div className="page-hero__actions">{actions}</div>}
    </section>
  )
}
