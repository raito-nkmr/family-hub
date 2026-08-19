import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders its icon, title level, and description consistently', () => {
    render(
      <EmptyState
        className="photo-empty-state"
        icon={<span data-testid="empty-icon" />}
        title="写真はありません"
        description="写真を追加するとここに表示されます。"
        titleAs="h2"
      />,
    )

    expect(screen.getByTestId('empty-icon')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: '写真はありません' })).toBeInTheDocument()
    expect(screen.getByText('写真を追加するとここに表示されます。')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2 }).parentElement).toHaveClass('empty-state', 'photo-empty-state')
  })
})
