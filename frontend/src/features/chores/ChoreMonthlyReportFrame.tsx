import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { TaskAltIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { useChoreMonthlyReport } from './useChoreMonthlyReport'

export type ChoreMonthlyReportData = NonNullable<ReturnType<typeof useChoreMonthlyReport>['report']>
export type ChoreMonthlyReportState = ReturnType<typeof useChoreMonthlyReport>

interface ChoreMonthlyReportFrameProps {
  state: ChoreMonthlyReportState
  title: string
  eyebrow: string
  description: string
  children: (report: ChoreMonthlyReportData) => ReactNode
}

export function ChoreMonthlyReportFrame({
  state,
  title,
  eyebrow,
  description,
  children,
}: ChoreMonthlyReportFrameProps) {
  const { t, i18n } = useTranslation()

  return (
    <main id="top" className="chore-monthly-report-page">
      <header className="chore-monthly-report-hero">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </header>

      <section className="chore-monthly-report-board" aria-labelledby="chore-monthly-report-heading">
        <GroupScopedToolbar
          groups={state.groups}
          selectedGroupId={state.selectedGroupId}
          selectId="chore-monthly-report-group"
          label={t('chores.group')}
          selectDisabled={state.loading || state.groups.length === 0}
          refreshDisabled={state.loading}
          onSelectGroup={state.selectGroup}
          onRefresh={state.refresh}
        />

        {state.selectedGroup && (
          <div className="chore-monthly-report-month-picker">
            <button
              className="secondary-button"
              type="button"
              aria-label={t('chores.reportPreviousMonth')}
              disabled={state.loading}
              onClick={() => state.setMonth(state.previousMonth)}
            >
              ‹
            </button>
            <h2 id="chore-monthly-report-heading">{formatMonth(state.month, i18n.language)}</h2>
            <button
              className="secondary-button"
              type="button"
              aria-label={t('chores.reportNextMonth')}
              disabled={state.loading || !state.canGoNext}
              onClick={() => state.setMonth(state.nextMonth)}
            >
              ›
            </button>
          </div>
        )}

        {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
        {state.loading ? (
          <div className="chore-monthly-report-skeleton" aria-label={t('chores.reportLoading')} />
        ) : state.groups.length === 0 ? (
          <EmptyState
            className="chore-empty-state"
            icon={<TaskAltIcon />}
            title={t('chores.groupNeeded')}
            description={t('chores.groupNeededHelp')}
          />
        ) : (
          state.report && children(state.report)
        )}
      </section>
    </main>
  )
}

function formatMonth(month: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'long', timeZone: 'UTC' }).format(
    new Date(`${month}-01T00:00:00Z`),
  )
}
