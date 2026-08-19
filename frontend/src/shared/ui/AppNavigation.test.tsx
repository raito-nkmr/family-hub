import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router'
import { AppNavigation, SectionNavigation } from './AppNavigation'

function LocationProbe() {
  return <output aria-label="current path">{useLocation().pathname}</output>
}

describe('AppNavigation', () => {
  it('groups photo destinations and management for mobile navigation', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <MemoryRouter initialEntries={['/photos/library']}>
        <AppNavigation showInvitations photoUnseenCount={3} />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(container.querySelectorAll('.app-navigation__mobile-only')).toHaveLength(2)
    expect(container.querySelector('.app-navigation__section')).toHaveTextContent('写真')
    expect(screen.getByRole('link', { name: 'ライブラリ' })).toHaveAttribute('aria-current', 'page')
    await user.click(screen.getByRole('link', { name: 'ホーム' }))
    expect(screen.getByLabelText('current path')).toHaveTextContent('/')
    await user.click(screen.getByRole('link', { name: 'その他' }))
    expect(screen.getByLabelText('current path')).toHaveTextContent('/groups')
  })

  it('switches between photo views using section tabs', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/photos/library']}>
        <SectionNavigation showInvitations photoUnseenCount={2} />
        <LocationProbe />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('link', { name: '新着2' }))
    expect(screen.getByLabelText('current path')).toHaveTextContent('/photos/new')
  })

  it('shows account security under management', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/groups']}>
        <SectionNavigation showInvitations photoUnseenCount={0} />
        <LocationProbe />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('link', { name: 'アカウント' }))
    expect(screen.getByLabelText('current path')).toHaveTextContent('/account')
  })

  it('keeps desktop management links in the same order as mobile management tabs', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/groups']}>
        <AppNavigation showInvitations photoUnseenCount={0} />
      </MemoryRouter>,
    )

    const desktopLinks = [...container.querySelectorAll<HTMLAnchorElement>('a.app-navigation__desktop-only')]
    expect(desktopLinks.slice(-4).map((link) => link.textContent?.trim())).toEqual([
      'グループ',
      '招待',
      'アカウント',
      'システム状態',
    ])
  })
})
