import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageHero } from './PageHero'

describe('PageHero', () => {
  it('renders the shared compact heading structure and action slot', () => {
    const { container } = render(
      <PageHero eyebrow="TASK LIST" title="家事タスク" description="説明" actions={<button>追加</button>} />,
    )

    expect(screen.getByText('TASK LIST')).toHaveClass('eyebrow')
    expect(screen.getByRole('heading', { name: '家事タスク' })).toBeInTheDocument()
    expect(screen.getByText('説明')).toHaveClass('page-hero__description')
    expect(container.querySelector('.page-hero')).toHaveClass('page-hero--with-action')
  })
})
