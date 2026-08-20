import { useEffect, useRef, useState } from 'react'

export const PULL_TO_REFRESH_THRESHOLD = 88
const MAX_PULL_DISTANCE = 128
const MOBILE_MAX_WIDTH = 900

interface PullToRefreshOptions {
  onRefresh: () => Promise<unknown> | unknown
  enabled?: boolean
}

export function usePullToRefresh({ onRefresh, enabled = true }: PullToRefreshOptions) {
  const [pullDistance, setPullDistance] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const refreshingRef = useRef(false)
  const onRefreshRef = useRef(onRefresh)

  useEffect(() => {
    onRefreshRef.current = onRefresh
  }, [onRefresh])

  useEffect(() => {
    if (!enabled) return

    let startX = 0
    let startY = 0
    let distance = 0
    let tracking = false

    const reset = () => {
      tracking = false
      distance = 0
      setPullDistance(0)
    }

    const isAtTop = () => Math.max(window.scrollY, document.documentElement.scrollTop, document.body.scrollTop) <= 0
    const isMobileWidth = () => window.innerWidth <= MOBILE_MAX_WIDTH
    const isIgnoredTarget = (target: EventTarget | null) =>
      target instanceof Element &&
      Boolean(target.closest('a, button, input, select, textarea, [role="dialog"], [data-pull-to-refresh-ignore]'))

    const handleTouchStart = (event: TouchEvent) => {
      if (
        !isMobileWidth() ||
        refreshingRef.current ||
        event.touches.length !== 1 ||
        !isAtTop() ||
        isIgnoredTarget(event.target)
      ) {
        return
      }
      const touch = event.touches[0]
      startX = touch.clientX
      startY = touch.clientY
      distance = 0
      tracking = true
    }

    const handleTouchMove = (event: TouchEvent) => {
      if (!tracking || event.touches.length !== 1) return
      const touch = event.touches[0]
      const deltaX = touch.clientX - startX
      const deltaY = touch.clientY - startY

      if (deltaY <= 0 || Math.abs(deltaX) > Math.abs(deltaY)) {
        reset()
        return
      }
      if (!isAtTop()) {
        reset()
        return
      }

      distance = deltaY
      setPullDistance(Math.min(deltaY * 0.65, MAX_PULL_DISTANCE))
      event.preventDefault()
    }

    const handleTouchEnd = () => {
      if (!tracking) return
      const shouldRefresh = distance * 0.65 >= PULL_TO_REFRESH_THRESHOLD
      reset()
      if (!shouldRefresh || refreshingRef.current) return

      refreshingRef.current = true
      setRefreshing(true)
      void Promise.resolve(onRefreshRef.current())
        .catch(() => undefined)
        .finally(() => {
          refreshingRef.current = false
          setRefreshing(false)
        })
    }

    window.addEventListener('touchstart', handleTouchStart, { passive: true })
    window.addEventListener('touchmove', handleTouchMove, { passive: false })
    window.addEventListener('touchend', handleTouchEnd, { passive: true })
    window.addEventListener('touchcancel', reset, { passive: true })

    return () => {
      window.removeEventListener('touchstart', handleTouchStart)
      window.removeEventListener('touchmove', handleTouchMove)
      window.removeEventListener('touchend', handleTouchEnd)
      window.removeEventListener('touchcancel', reset)
    }
  }, [enabled])

  return {
    pullDistance,
    refreshing,
    ready: pullDistance >= PULL_TO_REFRESH_THRESHOLD,
  }
}
