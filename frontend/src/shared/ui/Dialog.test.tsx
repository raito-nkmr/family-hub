import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Dialog } from './Dialog'

describe('Dialog', () => {
  it('expresses panel size and surface through explicit variants', () => {
    render(
      <Dialog titleId="media-title" size="large" surface="media" onClose={vi.fn()}>
        <h2 id="media-title">Media</h2>
      </Dialog>,
    )

    const panel = screen.getByRole('dialog').firstElementChild
    expect(panel).toHaveClass('dialog__panel--size-large', 'dialog__panel--surface-media')
  })

  it('does not dismiss while a mutation is busy', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <Dialog titleId="dialog-title" busy onClose={onClose}>
        <h2 id="dialog-title">Edit</h2>
      </Dialog>,
    )

    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('dialog'))
    await user.click(screen.getByRole('button', { name: 'ダイアログを閉じる' }))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('moves and traps focus, marks the background inert, and restores focus', async () => {
    const user = userEvent.setup()
    function Example() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Open
          </button>
          {open && (
            <Dialog titleId="focus-title" onClose={() => setOpen(false)}>
              <h2 id="focus-title">Focus test</h2>
              <button type="button">Action</button>
            </Dialog>
          )}
        </>
      )
    }

    render(<Example />)
    const opener = screen.getByRole('button', { name: 'Open' })
    await user.click(opener)

    const close = screen.getByRole('button', { name: 'ダイアログを閉じる' })
    const action = screen.getByRole('button', { name: 'Action' })
    expect(close).toHaveFocus()
    expect(opener).toHaveProperty('inert', true)

    action.focus()
    await user.tab()
    expect(close).toHaveFocus()
    await user.tab({ shift: true })
    expect(action).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(opener).toHaveFocus()
    expect(opener).toHaveProperty('inert', false)
  })
})
