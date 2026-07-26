import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { MoreVertIcon, RetryIcon } from './icons'

const LOAD_AHEAD_PIXELS = 600

interface InfiniteScrollTriggerProps {
  hasMore: boolean
  loading: boolean
  autoLoad: boolean
  onLoadMore: () => void
}

export function InfiniteScrollTrigger({ hasMore, loading, autoLoad, onLoadMore }: InfiniteScrollTriggerProps) {
  const { t } = useTranslation()
  const triggerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const trigger = triggerRef.current
    if (!trigger || !hasMore || loading || !autoLoad) return

    let requested = false
    let observer: IntersectionObserver | null = null

    const requestNextPage = () => {
      if (requested) return
      requested = true
      observer?.disconnect()
      onLoadMore()
    }
    const checkPosition = () => {
      const viewportHeight = Math.max(window.innerHeight, window.visualViewport?.height ?? 0)
      if (trigger.getBoundingClientRect().top <= viewportHeight + LOAD_AHEAD_PIXELS) requestNextPage()
    }

    if ('IntersectionObserver' in window) {
      observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) requestNextPage()
        },
        { rootMargin: `${LOAD_AHEAD_PIXELS}px 0px` },
      )
      observer.observe(trigger)
    }

    document.addEventListener('scroll', checkPosition, { capture: true, passive: true })
    window.addEventListener('scroll', checkPosition, { passive: true })
    window.addEventListener('touchmove', checkPosition, { passive: true })
    window.addEventListener('touchend', checkPosition, { passive: true })
    window.addEventListener('resize', checkPosition, { passive: true })
    window.visualViewport?.addEventListener('resize', checkPosition, { passive: true })
    window.visualViewport?.addEventListener('scroll', checkPosition, { passive: true })

    return () => {
      observer?.disconnect()
      document.removeEventListener('scroll', checkPosition, true)
      window.removeEventListener('scroll', checkPosition)
      window.removeEventListener('touchmove', checkPosition)
      window.removeEventListener('touchend', checkPosition)
      window.removeEventListener('resize', checkPosition)
      window.visualViewport?.removeEventListener('resize', checkPosition)
      window.visualViewport?.removeEventListener('scroll', checkPosition)
    }
  }, [autoLoad, hasMore, loading, onLoadMore])

  if (!hasMore) return null

  return (
    <div ref={triggerRef} className="infinite-scroll-trigger" aria-live="polite">
      {loading ? (
        <span className="infinite-scroll-trigger__status">
          <span className="spinner" aria-hidden="true" />
          {t('infiniteScroll.loading')}
        </span>
      ) : (
        <button className="infinite-scroll-trigger__button icon-button" type="button" onClick={onLoadMore}>
          {autoLoad ? <MoreVertIcon /> : <RetryIcon />}
          {t(autoLoad ? 'infiniteScroll.loadMore' : 'infiniteScroll.retry')}
        </button>
      )}
    </div>
  )
}
