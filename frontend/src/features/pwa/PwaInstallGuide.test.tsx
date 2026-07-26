import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PwaInstallGuide } from './PwaInstallGuide'

describe('PwaInstallGuide', () => {
  it('shows the iPhone steps and closes from the completion button', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<PwaInstallGuide onClose={onClose} />)

    expect(screen.getByRole('heading', { name: 'iPhoneにFamily Hubを追加' })).toBeInTheDocument()
    expect(screen.getByText('「ホーム画面に追加」を選択')).toBeInTheDocument()
    expect(screen.getByText('「Webアプリとして開く」をオン')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '完了' }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
