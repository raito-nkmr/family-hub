import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ConfirmationDialogProvider } from './ConfirmationDialog'
import { useConfirmation } from './confirmation'

function ConfirmExample() {
  const confirm = useConfirmation()
  const [result, setResult] = useState('waiting')
  return (
    <>
      <button
        type="button"
        onClick={() =>
          void confirm('招待を取り消しますか？', {
            cancelLabel: '戻る',
            confirmLabel: '招待を取り消す',
          }).then((value) => setResult(String(value)))
        }
      >
        Open
      </button>
      <output>{result}</output>
    </>
  )
}

describe('ConfirmationDialogProvider', () => {
  it('resolves a destructive confirmation through the accessible shared dialog', async () => {
    const user = userEvent.setup()
    render(
      <ConfirmationDialogProvider>
        <ConfirmExample />
      </ConfirmationDialogProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('招待を取り消しますか？')
    expect(screen.getByRole('button', { name: '戻る' })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: '招待を取り消す' }))

    expect(screen.getByText('true')).toBeInTheDocument()
  })
})
