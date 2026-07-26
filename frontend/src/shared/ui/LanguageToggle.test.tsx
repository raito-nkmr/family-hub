import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import i18n from '../../i18n'
import { LanguageToggle } from './LanguageToggle'

describe('LanguageToggle', () => {
  it('switches the document language and persists the selection', async () => {
    await i18n.changeLanguage('ja')
    const user = userEvent.setup()
    render(<LanguageToggle />)

    const switchToEnglish = screen.getByRole('button', { name: '表示言語をENに切り替える' })
    expect(switchToEnglish).toHaveAttribute('lang', 'en')
    await user.click(switchToEnglish)

    expect(i18n.resolvedLanguage).toBe('en')
    expect(document.documentElement.lang).toBe('en')
    expect(localStorage.getItem('family-hub-language')).toBe('en')

    await user.click(screen.getByRole('button', { name: 'Switch language to JA' }))

    expect(i18n.resolvedLanguage).toBe('ja')
    expect(document.documentElement.lang).toBe('ja')
    expect(localStorage.getItem('family-hub-language')).toBe('ja')
  })
})
