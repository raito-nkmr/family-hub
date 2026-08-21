import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { appPaths } from '../../app/routes'
import { TaskAltIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { useCleaningReport } from './useCleaningReport'

export type CleaningReportData = NonNullable<ReturnType<typeof useCleaningReport>['report']>
export type CleaningReportState = ReturnType<typeof useCleaningReport>

interface CleaningReportFrameProps {
  state: CleaningReportState
  title: string
  eyebrow: string
  description: string
  children: (report: CleaningReportData) => ReactNode
}

export function CleaningReportFrame({ state, title, eyebrow, description, children }: CleaningReportFrameProps) {
  const { t, i18n } = useTranslation()
  const location = useLocation()

  return (
    <main id="top" className="cleaning-report-page">
      <header className="cleaning-report-hero">
        <div>
          <Link className="cleaning-report__back" to={{ pathname: appPaths.cleaning, search: location.search }}>
            {t('cleaning.reportBack')}
          </Link>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </header>

      <section className="cleaning-report-board" aria-labelledby="cleaning-report-heading">
        <GroupScopedToolbar
          groups={state.groups}
          selectedGroupId={state.selectedGroupId}
          selectId="cleaning-report-group"
          label={t('cleaning.group')}
          selectDisabled={state.loading || state.groups.length === 0}
          refreshDisabled={state.loading}
          onSelectGroup={state.selectGroup}
          onRefresh={state.refresh}
        />

        {state.selectedGroup && (
          <div className="cleaning-report-month-picker">
            <button
              className="secondary-button"
              type="button"
              aria-label={t('cleaning.reportPreviousMonth')}
              disabled={state.loading}
              onClick={() => state.setMonth(state.previousMonth)}
            >
              ‹
            </button>
            <h2 id="cleaning-report-heading">{formatMonth(state.month, i18n.language)}</h2>
            <button
              className="secondary-button"
              type="button"
              aria-label={t('cleaning.reportNextMonth')}
              disabled={state.loading || !state.canGoNext}
              onClick={() => state.setMonth(state.nextMonth)}
            >
              ›
            </button>
          </div>
        )}

        {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
        {state.loading ? (
          <div className="cleaning-report-skeleton" aria-label={t('cleaning.reportLoading')} />
        ) : state.groups.length === 0 ? (
          <EmptyState
            className="cleaning-empty-state"
            icon={<TaskAltIcon />}
            title={t('cleaning.groupNeeded')}
            description={t('cleaning.groupNeededHelp')}
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
