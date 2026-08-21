import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router'
import { AppNavigation, SectionNavigation } from './AppNavigation'

function LocationProbe() {
  const location = useLocation()
  return (
    <>
      <output aria-label="current path">{location.pathname}</output>
      <output aria-label="current search">{location.search}</output>
    </>
  )
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

    expect(container.querySelectorAll('.app-navigation__mobile-only')).toHaveLength(3)
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

  it('groups cleaning destinations and preserves report filters', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/cleaning/daily?group=group-1&month=2026-07&view=chart']}>
        <AppNavigation showInvitations={false} photoUnseenCount={0} />
        <SectionNavigation showInvitations={false} photoUnseenCount={0} />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getAllByText('掃除').length).toBeGreaterThan(0)
    expect(
      screen
        .getAllByRole('link', { name: '日別' })
        .some((link) => link.getAttribute('href') === '/cleaning/daily?group=group-1&month=2026-07&view=chart'),
    ).toBe(true)
    const monthlyLink = screen
      .getAllByRole('link', { name: '月次' })
      .find((link) => link.closest('.section-navigation') !== null)
    expect(monthlyLink).toBeDefined()
    await user.click(monthlyLink!)
    expect(screen.getByLabelText('current path')).toHaveTextContent('/cleaning/reports')
    expect(screen.getByLabelText('current search')).toHaveTextContent('?group=group-1&month=2026-07&view=chart')
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
