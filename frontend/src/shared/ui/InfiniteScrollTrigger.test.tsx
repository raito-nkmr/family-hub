import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { InfiniteScrollTrigger } from './InfiniteScrollTrigger'

const observe = vi.fn()
const unobserve = vi.fn()
const disconnect = vi.fn()
let observerCallback: IntersectionObserverCallback

class IntersectionObserverMock implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = '600px 0px'
  readonly scrollMargin = '0px'
  readonly thresholds = [0]

  constructor(callback: IntersectionObserverCallback) {
    observerCallback = callback
  }

  observe = observe
  disconnect = disconnect
  unobserve = unobserve
  takeRecords = () => []
}

describe('InfiniteScrollTrigger', () => {
  beforeEach(() => {
    observe.mockReset()
    unobserve.mockReset()
    disconnect.mockReset()
    vi.stubGlobal('IntersectionObserver', IntersectionObserverMock)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('loads the next page when the trigger approaches the viewport', () => {
    const onLoadMore = vi.fn()
    render(<InfiniteScrollTrigger hasMore loading={false} autoLoad onLoadMore={onLoadMore} />)

    act(() => {
      observerCallback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
    })

    expect(observe).toHaveBeenCalledOnce()
    expect(disconnect).toHaveBeenCalledOnce()
    expect(onLoadMore).toHaveBeenCalledOnce()
  })

  it('falls back to window scroll position checks when the observer does not notify', () => {
    const onLoadMore = vi.fn()
    const { container } = render(<InfiniteScrollTrigger hasMore loading={false} autoLoad onLoadMore={onLoadMore} />)
    const trigger = container.querySelector<HTMLElement>('.infinite-scroll-trigger')!
    vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue({
      top: window.innerHeight + 500,
    } as DOMRect)

    fireEvent.scroll(window)

    expect(onLoadMore).toHaveBeenCalledOnce()
    expect(disconnect).toHaveBeenCalledOnce()
  })

  it('stops automatic loading after an error and offers manual retry', () => {
    const onLoadMore = vi.fn()
    render(<InfiniteScrollTrigger hasMore loading={false} autoLoad={false} onLoadMore={onLoadMore} />)

    expect(observe).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '読み込みを再試行' }))
    expect(onLoadMore).toHaveBeenCalledOnce()
  })
})
