import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router'
import { AppFooter } from './AppFooter'

describe('AppFooter', () => {
  it('opens the privacy page through a real link', () => {
    render(
      <MemoryRouter>
        <AppFooter />
      </MemoryRouter>,
    )

    expect(screen.getByText('Family Hub · v1.0.0')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'プライバシー' })
    expect(link).toHaveAttribute('href', '/privacy')
  })
})
