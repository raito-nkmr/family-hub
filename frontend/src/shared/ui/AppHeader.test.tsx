import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router'
import { AppHeader } from './AppHeader'

function LocationProbe() {
  return <output aria-label="current path">{useLocation().pathname}</output>
}

it('uses the brand control to navigate home', async () => {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/account']}>
      <AppHeader username="family-member" theme="light" onLogout={vi.fn()} onToggleTheme={vi.fn()} />
      <LocationProbe />
    </MemoryRouter>,
  )

  expect(screen.getByText('HOME APPS')).toHaveAttribute('lang', 'en')
  await user.click(screen.getByRole('link', { name: /Family Hub/ }))

  expect(screen.getByLabelText('current path')).toHaveTextContent('/')
})
