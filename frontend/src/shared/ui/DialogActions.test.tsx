import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DialogActions } from './DialogActions'

describe('DialogActions', () => {
  it('shares the cancel action while preserving the submit child', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()

    render(
      <DialogActions disabled={false} onCancel={onCancel}>
        <button type="submit">保存</button>
      </DialogActions>,
    )

    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'キャンセル' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('disables the cancel action while busy', () => {
    render(
      <DialogActions disabled onCancel={vi.fn()}>
        <button type="submit">保存</button>
      </DialogActions>,
    )

    expect(screen.getByRole('button', { name: 'キャンセル' })).toBeDisabled()
  })
})
