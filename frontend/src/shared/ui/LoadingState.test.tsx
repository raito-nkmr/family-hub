import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LoadingState } from './LoadingState'

describe('LoadingState', () => {
  it('supports a main element and a custom layout class', () => {
    render(<LoadingState as="main" id="top" className="photo-activity-loading" label="写真を読み込み中" />)

    const loading = screen.getByRole('main', { name: '写真を読み込み中' })
    expect(loading).toHaveAttribute('id', 'top')
    expect(loading).toHaveClass('photo-activity-loading')
    expect(loading.querySelector('.spinner')).toBeInTheDocument()
  })
})
