import { act, render, screen } from '@testing-library/react'
import { useTranslation } from 'react-i18next'
import { describe, expect, it, vi } from 'vitest'
import { usePullToRefresh } from './usePullToRefresh'

function touchEvent(type: 'touchstart' | 'touchmove' | 'touchend', clientX: number, clientY: number) {
  const event = new Event(type, { cancelable: true })
  const touch = { clientX, clientY }
  Object.defineProperty(event, type === 'touchend' ? 'changedTouches' : 'touches', { value: [touch] })
  return event
}

function PullProbe({ onRefresh }: { onRefresh: () => Promise<void> }) {
  const { t } = useTranslation()
  const state = usePullToRefresh({ onRefresh })
  return (
    <output>
      {state.refreshing ? t('pullToRefresh.refreshing') : state.ready ? t('pullToRefresh.release') : state.pullDistance}
    </output>
  )
}

describe('usePullToRefresh', () => {
  it('refreshes after a large downward pull from the top on mobile', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    render(<PullProbe onRefresh={onRefresh} />)

    act(() => {
      window.dispatchEvent(touchEvent('touchstart', 100, 100))
      window.dispatchEvent(touchEvent('touchmove', 100, 250))
    })
    expect(screen.getByText('離して更新')).toBeInTheDocument()

    await act(async () => {
      window.dispatchEvent(touchEvent('touchend', 100, 250))
    })

    expect(onRefresh).toHaveBeenCalledOnce()
    expect(screen.queryByText('更新しています…')).not.toBeInTheDocument()
  })

  it('ignores short and horizontal pulls', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    render(<PullProbe onRefresh={onRefresh} />)

    act(() => {
      window.dispatchEvent(touchEvent('touchstart', 100, 100))
      window.dispatchEvent(touchEvent('touchmove', 180, 140))
      window.dispatchEvent(touchEvent('touchend', 180, 140))
    })

    expect(onRefresh).not.toHaveBeenCalled()
    expect(screen.queryByText('離して更新')).not.toBeInTheDocument()
  })
})
