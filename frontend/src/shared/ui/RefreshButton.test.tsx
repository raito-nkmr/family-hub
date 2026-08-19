import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RefreshButton } from './RefreshButton'

describe('RefreshButton', () => {
  it('calls its handler and exposes its busy state', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(<RefreshButton onClick={onClick} />)
    await user.click(screen.getByRole('button', { name: '更新' }))

    expect(onClick).toHaveBeenCalledOnce()

    render(<RefreshButton onClick={vi.fn()} disabled />)
    expect(screen.getAllByRole('button', { name: '更新' })[1]).toBeDisabled()
  })
})
