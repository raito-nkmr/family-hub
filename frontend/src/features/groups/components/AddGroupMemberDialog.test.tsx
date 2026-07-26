import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AddGroupMemberDialog } from './AddGroupMemberDialog'

describe('AddGroupMemberDialog', () => {
  it('adds a selected user without requiring their id to be typed', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)

    render(
      <AddGroupMemberDialog
        submitting={false}
        loadingCandidates={false}
        candidates={[{ user_id: 'user-1', username: 'たろう' }]}
        error={null}
        onSubmit={onSubmit}
        onClose={vi.fn()}
      />,
    )

    await user.selectOptions(screen.getByLabelText('ユーザー'), 'user-1')
    await user.click(screen.getByRole('button', { name: '追加する' }))

    expect(onSubmit).toHaveBeenCalledWith('user-1', 'member')
  })

  it('explains when every active user is already a member', () => {
    render(
      <AddGroupMemberDialog
        submitting={false}
        loadingCandidates={false}
        candidates={[]}
        error={null}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('追加できるユーザーはいません。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '追加する' })).toBeDisabled()
  })

  it('announces a submission error', () => {
    render(
      <AddGroupMemberDialog
        submitting={false}
        loadingCandidates={false}
        candidates={[]}
        error="メンバーを追加できませんでした。"
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('メンバーを追加できませんでした。')
  })
})
