import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { appPaths } from '../../app/routes'
import { TaskAltIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { useChoreReport } from './useChoreReport'

export type ChoreReportData = NonNullable<ReturnType<typeof useChoreReport>['report']>
export type ChoreReportState = ReturnType<typeof useChoreReport>

interface ChoreReportFrameProps {
  state: ChoreReportState
  title: string
  eyebrow: string
  description: string
  children: (report: ChoreReportData) => ReactNode
}

export function ChoreReportFrame({ state, title, eyebrow, description, children }: ChoreReportFrameProps) {
  const { t, i18n } = useTranslation()
  const location = useLocation()

  return (
    <main id="top" className="chore-report-page">
      <header className="chore-report-hero">
        <div>
          <Link className="chore-report__back" to={{ pathname: appPaths.chores, search: location.search }}>
            {t('chores.reportBack')}
          </Link>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </header>

      <section className="chore-report-board" aria-labelledby="chore-report-heading">
        <GroupScopedToolbar
          groups={state.groups}
          selectedGroupId={state.selectedGroupId}
          selectId="chore-report-group"
          label={t('chores.group')}
          selectDisabled={state.loading || state.groups.length === 0}
          refreshDisabled={state.loading}
          onSelectGroup={state.selectGroup}
          onRefresh={state.refresh}
        />

        {state.selectedGroup && (
          <div className="chore-report-month-picker">
            <button
              className="secondary-button"
              type="button"
              aria-label={t('chores.reportPreviousMonth')}
              disabled={state.loading}
              onClick={() => state.setMonth(state.previousMonth)}
            >
              ‹
            </button>
            <h2 id="chore-report-heading">{formatMonth(state.month, i18n.language)}</h2>
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
          <div className="chore-report-skeleton" aria-label={t('chores.reportLoading')} />
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
