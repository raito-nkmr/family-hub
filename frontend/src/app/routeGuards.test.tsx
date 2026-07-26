import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { RequireAdmin } from './routeGuards'

function Home() {
  return <main>Home</main>
}

function CurrentPath() {
  return <output aria-label="current path">{useLocation().pathname}</output>
}

function renderGuard(role: 'admin' | 'user') {
  return render(
    <MemoryRouter initialEntries={['/system']}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route
          path="/system"
          element={
            <RequireAdmin role={role}>
              <main>System status</main>
            </RequireAdmin>
          }
        />
      </Routes>
      <CurrentPath />
    </MemoryRouter>,
  )
}

describe('RequireAdmin', () => {
  it('redirects a regular user to home', () => {
    renderGuard('user')

    expect(screen.getByRole('main')).toHaveTextContent('Home')
    expect(screen.getByLabelText('current path')).toHaveTextContent('/')
  })

  it('renders the protected route for an administrator', () => {
    renderGuard('admin')

    expect(screen.getByRole('main')).toHaveTextContent('System status')
    expect(screen.getByLabelText('current path')).toHaveTextContent('/system')
  })
})
