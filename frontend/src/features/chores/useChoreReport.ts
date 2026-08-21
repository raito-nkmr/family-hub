import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import i18n from '../../i18n'
import { isApiErrorWithStatus } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useGroupSelection } from '../../shared/routing/useGroupSelection'
import { getGroups } from '../groups/api'
import { getChoreMonthlyReport } from './api'
import { getCurrentMonthForTimezone, isReportMonth } from './reportDate'

interface UseChoreReportOptions {
  onUnauthorized: () => void
}

export function useChoreReport({ onUnauthorized }: UseChoreReportOptions) {
  const [searchParams, setSearchParams] = useSearchParams()
  const groupsQuery = useQuery({
    queryKey: queryKeys.groups,
    queryFn: ({ signal }) => getGroups(signal),
  })
  const groups = groupsQuery.data ?? []
  const { selectedGroupId, selectGroup: selectGroupInUrl } = useGroupSelection(groups)
  const selectedGroup = groups.find((group) => group.id === selectedGroupId) ?? null
  const currentMonth = getCurrentMonthForTimezone(selectedGroup?.timezone ?? 'Asia/Tokyo')
  const requestedMonth = searchParams.get('month')
  const effectiveMonth = isReportMonth(requestedMonth) && requestedMonth <= currentMonth ? requestedMonth : currentMonth
  const reportQuery = useQuery({
    queryKey: queryKeys.choreReport(selectedGroupId ?? '', effectiveMonth),
    queryFn: ({ signal }) => getChoreMonthlyReport(selectedGroupId!, effectiveMonth, signal),
    enabled: selectedGroupId !== null,
  })
  const previousGroupId = useRef<string | null>(null)

  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(reportQuery.error, onUnauthorized)

  useEffect(() => {
    if (!selectedGroupId) return
    const groupChanged = previousGroupId.current !== null && previousGroupId.current !== selectedGroupId
    previousGroupId.current = selectedGroupId
    if (groupChanged || requestedMonth !== effectiveMonth) {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.set('month', groupChanged ? currentMonth : effectiveMonth)
          return next
        },
        { replace: true },
      )
    }
  }, [currentMonth, effectiveMonth, requestedMonth, selectedGroupId, setSearchParams])

  const selectGroup = async (groupId: string) => {
    const group = groups.find((item) => item.id === groupId)
    if (!group) return
    await selectGroupInUrl(groupId)
    const groupMonth = getCurrentMonthForTimezone(group.timezone)
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('month', groupMonth)
        return next
      },
      { replace: true },
    )
  }

  const setMonth = (month: string) => {
    if (!isReportMonth(month) || month > currentMonth) return
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('month', month)
        return next
      },
      { replace: true },
    )
  }

  const previousMonth = shiftReportMonth(effectiveMonth, -1)
  const nextMonth = shiftReportMonth(effectiveMonth, 1)
  const queryError = groupsQuery.error
    ? i18n.t('errors.choreReportData')
    : reportQuery.error
      ? isApiErrorWithStatus(reportQuery.error, 404)
        ? i18n.t('errors.choreReportForbidden')
        : i18n.t('errors.choreReportLoad')
      : null

  return {
    groups,
    selectedGroupId,
    selectedGroup,
    report: reportQuery.data ?? null,
    month: effectiveMonth,
    loading: groupsQuery.isPending || (selectedGroupId !== null && reportQuery.isPending),
    pageError: queryError,
    canGoNext: effectiveMonth < currentMonth,
    previousMonth,
    nextMonth,
    selectGroup,
    setMonth,
    refresh: async () => {
      if (selectedGroupId) await reportQuery.refetch()
      else await groupsQuery.refetch()
    },
  }
}

function shiftReportMonth(month: string, offset: number): string {
  const [year, monthNumber] = month.split('-').map(Number)
  const date = new Date(Date.UTC(year, monthNumber - 1 + offset, 1))
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`
}
