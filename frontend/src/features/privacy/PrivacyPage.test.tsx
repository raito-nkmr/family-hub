import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router'
import { PrivacyPage } from './PrivacyPage'

function LocationProbe() {
  const location = useLocation()
  return (
    <output aria-label="current path">
      {location.pathname}
      {location.search}
    </output>
  )
}

describe('PrivacyPage', () => {
  it('explains data handling and returns to the app', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/privacy']}>
        <PrivacyPage theme="light" onToggleTheme={vi.fn()} />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: 'プライバシー' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '保存場所と保持期間' })).toBeInTheDocument()
    expect(screen.getByText(/広告配信やデータ販売/)).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: /Family Hub/ }))
    expect(screen.getByLabelText('current path')).toHaveTextContent('/')
  })

  it('returns to the authenticated route recorded by the footer link', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[{ pathname: '/privacy', state: { returnTo: '/photos/library' } }]}>
        <PrivacyPage theme="light" onToggleTheme={vi.fn()} />
        <LocationProbe />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('link', { name: /Family Hub/ }))
    expect(screen.getByLabelText('current path')).toHaveTextContent('/photos/library')
  })

  it('preserves safe application query parameters and rejects external return targets', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <MemoryRouter
        initialEntries={[{ pathname: '/privacy', state: { returnTo: '/photos/library?q=北海道&year=2026#unsafe' } }]}
      >
        <PrivacyPage theme="light" onToggleTheme={vi.fn()} />
        <LocationProbe />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('link', { name: /Family Hub/ }))
    expect(screen.getByLabelText('current path')).toHaveTextContent(
      '/photos/library?q=%E5%8C%97%E6%B5%B7%E9%81%93&year=2026',
    )

    rerender(
      <MemoryRouter initialEntries={[{ pathname: '/privacy', state: { returnTo: 'https://example.com/account' } }]}>
        <PrivacyPage theme="light" onToggleTheme={vi.fn()} />
        <LocationProbe />
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('link', { name: /Family Hub/ }))
    expect(screen.getByLabelText('current path')).toHaveTextContent('/')
  })
})
