import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AlbumFormDialog } from './AlbumFormDialog'

describe('AlbumFormDialog', () => {
  it('shows icon actions and emphasizes cancel as destructive', () => {
    render(
      <AlbumFormDialog
        submitting={false}
        error={null}
        groups={[
          {
            id: 'group-1',
            name: 'Family',
            current_user_role: 'admin',
            member_count: 1,
            created_by_user_id: 'user-1',
            created_at: '2026-07-20T00:00:00Z',
            updated_at: '2026-07-20T00:00:00Z',
          },
        ]}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const cancelButton = screen.getByRole('button', { name: 'キャンセル' })
    const createButton = screen.getByRole('button', { name: 'アルバムを作成' })
    expect(cancelButton).toHaveClass('danger-button--filled')
    expect(cancelButton.querySelector('svg')).toBeInTheDocument()
    expect(createButton.querySelector('svg')).toBeInTheDocument()
  })

  it('announces save errors to assistive technology', () => {
    render(
      <AlbumFormDialog
        submitting={false}
        error="保存できませんでした"
        groups={[]}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('保存できませんでした')
  })
})
