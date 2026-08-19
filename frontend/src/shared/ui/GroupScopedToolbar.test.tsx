import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { GroupScopedToolbar } from './GroupScopedToolbar'

describe('GroupScopedToolbar', () => {
  it('selects a group and refreshes the current view', async () => {
    const user = userEvent.setup()
    const onSelectGroup = vi.fn()
    const onRefresh = vi.fn()

    render(
      <GroupScopedToolbar
        groups={[
          { id: 'group-1', name: '同居家族' },
          { id: 'group-2', name: '実家' },
        ]}
        selectedGroupId="group-1"
        selectId="group"
        label="グループ"
        selectDisabled={false}
        refreshDisabled={false}
        onSelectGroup={onSelectGroup}
        onRefresh={onRefresh}
      />,
    )

    expect(screen.getByRole('combobox', { name: 'グループ' })).toHaveValue('group-1')
    await user.selectOptions(screen.getByRole('combobox', { name: 'グループ' }), 'group-2')
    await user.click(screen.getByRole('button', { name: '更新' }))

    expect(onSelectGroup).toHaveBeenCalledWith('group-2')
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('keeps selection and refresh disabled independently', () => {
    render(
      <GroupScopedToolbar
        groups={[{ id: 'group-1', name: '同居家族' }]}
        selectedGroupId="group-1"
        selectId="group"
        label="グループ"
        selectDisabled
        refreshDisabled={false}
        onSelectGroup={vi.fn()}
        onRefresh={vi.fn()}
      />,
    )

    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByRole('button', { name: '更新' })).toBeEnabled()
  })
})
