import type { CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { RefreshIcon } from './icons'

interface PullToRefreshIndicatorProps {
  pullDistance: number
  refreshing: boolean
  ready: boolean
}

export function PullToRefreshIndicator({ pullDistance, refreshing, ready }: PullToRefreshIndicatorProps) {
  const { t } = useTranslation()
  if (!refreshing && pullDistance === 0) return null

  const style = { '--pull-to-refresh-distance': `${pullDistance}px` } as CSSProperties
  const message = refreshing
    ? t('pullToRefresh.refreshing')
    : ready
      ? t('pullToRefresh.release')
      : t('pullToRefresh.pull')

  return (
    <div
      className={`pull-to-refresh${ready ? ' pull-to-refresh--ready' : ''}${refreshing ? ' pull-to-refresh--refreshing' : ''}`}
      style={style}
      role="status"
      aria-live="polite"
    >
      <RefreshIcon />
      <span>{message}</span>
    </div>
  )
}
