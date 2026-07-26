import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { isStandaloneMode, usePwaInstallGuide } from './usePwaInstallGuide'

const DISMISSED_STORAGE_KEY = 'family-hub-pwa-install-prompt-dismissed'

describe('usePwaInstallGuide', () => {
  beforeEach(() => {
    localStorage.removeItem(DISMISSED_STORAGE_KEY)
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: false })),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('remembers when the Home prompt is dismissed while keeping the account entry available', () => {
    const { result, unmount } = renderHook(() => usePwaInstallGuide())

    expect(result.current.homePromptVisible).toBe(true)
    expect(result.current.installGuideAvailable).toBe(true)
    act(() => result.current.dismissHomePrompt())
    expect(result.current.homePromptVisible).toBe(false)
    expect(localStorage.getItem(DISMISSED_STORAGE_KEY)).toBe('true')

    unmount()
    const next = renderHook(() => usePwaInstallGuide())
    expect(next.result.current.homePromptVisible).toBe(false)
    expect(next.result.current.installGuideAvailable).toBe(true)
  })

  it('hides both install entries in standalone mode', () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: true })),
    )

    expect(isStandaloneMode()).toBe(true)
    const { result } = renderHook(() => usePwaInstallGuide())
    expect(result.current.homePromptVisible).toBe(false)
    expect(result.current.installGuideAvailable).toBe(false)
  })
})
