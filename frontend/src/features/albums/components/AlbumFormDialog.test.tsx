import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
            timezone: 'Asia/Tokyo',
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
    expect(screen.getByText('共有する家族グループ')).toBeInTheDocument()
    expect(
      screen.getByText(
        '自分が所有する写真は必要に応じて選択したグループへ共有されます。他のユーザーの写真は、すべての選択グループに共有済みである必要があります。',
      ),
    ).toBeInTheDocument()
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

  it('submits all selected family groups', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
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
            timezone: 'Asia/Tokyo',
          },
          {
            id: 'group-2',
            name: 'Extended family',
            current_user_role: 'member',
            member_count: 2,
            created_by_user_id: 'user-2',
            created_at: '2026-07-20T00:00:00Z',
            updated_at: '2026-07-20T00:00:00Z',
            timezone: 'Asia/Tokyo',
          },
        ]}
        onSubmit={onSubmit}
        onClose={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('アルバム名'), '夏休み')
    await user.click(screen.getAllByRole('checkbox')[1])
    await user.click(screen.getByRole('button', { name: 'アルバムを作成' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        title: '夏休み',
        description: null,
        group_ids: ['group-1', 'group-2'],
      }),
    )
  })
})
