import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { InviteGroupMemberDialog } from './InviteGroupMemberDialog'

describe('InviteGroupMemberDialog', () => {
  it('invites a selected user without requiring their id to be typed', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)

    render(
      <InviteGroupMemberDialog
        submitting={false}
        loadingCandidates={false}
        candidates={[{ user_id: 'user-1', username: 'たろう' }]}
        error={null}
        onSubmit={onSubmit}
        onClose={vi.fn()}
      />,
    )

    await user.selectOptions(screen.getByLabelText('ユーザー'), 'user-1')
    await user.click(screen.getByRole('button', { name: '招待する' }))

    expect(onSubmit).toHaveBeenCalledWith('user-1', 'member')
  })

  it('explains when every active user is already a member', () => {
    render(
      <InviteGroupMemberDialog
        submitting={false}
        loadingCandidates={false}
        candidates={[]}
        error={null}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('招待できるユーザーはいません。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '招待する' })).toBeDisabled()
  })

  it('announces a submission error', () => {
    render(
      <InviteGroupMemberDialog
        submitting={false}
        loadingCandidates={false}
        candidates={[]}
        error="メンバーを招待できませんでした。"
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('メンバーを招待できませんでした。')
  })
})
