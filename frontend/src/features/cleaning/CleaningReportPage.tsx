import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CleaningIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { useCleaningReport } from './useCleaningReport'

interface CleaningReportPageProps {
  onUnauthorized: () => void
}

export function CleaningReportPage({ onUnauthorized }: CleaningReportPageProps) {
  const { t, i18n } = useTranslation()
  const state = useCleaningReport({ onUnauthorized })
  const report = state.report
  const maxDailyCount = useMemo(
    () => Math.max(1, ...(report?.daily.map((day) => day.completion_count) ?? [])),
    [report?.daily],
  )
  const maxCategoryCount = useMemo(
    () => Math.max(1, ...(report?.categories.map((category) => category.completion_count) ?? [])),
    [report?.categories],
  )

  return (
    <main id="top" className="cleaning-report-page">
      <header className="cleaning-report-hero">
        <div>
          <Link className="cleaning-report__back" to="/cleaning">
            {t('cleaning.reportBack')}
          </Link>
          <p className="eyebrow">{t('cleaning.reportEyebrow')}</p>
          <h1>{t('cleaning.reportTitle')}</h1>
          <p>{t('cleaning.reportDescription')}</p>
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
            icon={<CleaningIcon />}
            title={t('cleaning.groupNeeded')}
            description={t('cleaning.groupNeededHelp')}
          />
        ) : report ? (
          report.summary.completion_count === 0 ? (
            <>
              <ReportSummary report={report} t={t} />
              <EmptyState
                className="cleaning-empty-state cleaning-report-empty"
                icon={<CleaningIcon />}
                title={t('cleaning.reportEmpty')}
                description={t('cleaning.reportEmptyHelp')}
              />
            </>
          ) : (
            <>
              <ReportSummary report={report} t={t} />
              <DailyReport report={report} maxCount={maxDailyCount} t={t} />
              <CategoryReport report={report} maxCount={maxCategoryCount} t={t} />
              <MemberReport report={report} t={t} />
              <TaskReport report={report} t={t} />
            </>
          )
        ) : null}
      </section>
    </main>
  )
}

function ReportSummary({ report, t }: ReportSectionProps) {
  const summary = report.summary
  const items = [
    { label: t('cleaning.reportCompletions'), value: summary.completion_count },
    { label: t('cleaning.reportUniqueTasks'), value: summary.unique_task_count },
    { label: t('cleaning.reportParticipants'), value: summary.participant_count },
    { label: t('cleaning.reportCategories'), value: summary.category_count },
  ]
  return (
    <section className="cleaning-report-section" aria-labelledby="cleaning-report-summary-heading">
      <h2 id="cleaning-report-summary-heading">{t('cleaning.reportSummary')}</h2>
      <dl className="cleaning-report-summary">
        {items.map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function DailyReport({ report, maxCount, t }: ReportSectionProps & { maxCount: number }) {
  return (
    <section className="cleaning-report-section" aria-labelledby="cleaning-report-daily-heading">
      <div className="cleaning-report-section__heading">
        <h2 id="cleaning-report-daily-heading">{t('cleaning.reportDaily')}</h2>
        <span>{t('cleaning.reportCompletionCount')}</span>
      </div>
      <div className="cleaning-report-daily" role="list">
        {report.daily.map((day) => (
          <div className="cleaning-report-daily__item" role="listitem" key={day.day}>
            <div className="cleaning-report-daily__label">
              <span>{formatDay(day.day)}</span>
              <strong>{day.completion_count}</strong>
            </div>
            <div
              className="cleaning-report-bar"
              role="img"
              aria-label={t('cleaning.reportDailyAria', { day: formatDay(day.day), count: day.completion_count })}
            >
              <span style={{ width: `${(day.completion_count / maxCount) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function CategoryReport({ report, maxCount, t }: ReportSectionProps & { maxCount: number }) {
  return (
    <section className="cleaning-report-section" aria-labelledby="cleaning-report-category-heading">
      <div className="cleaning-report-section__heading">
        <h2 id="cleaning-report-category-heading">{t('cleaning.reportCategoriesByCount')}</h2>
        <span>{t('cleaning.reportCompletionCount')}</span>
      </div>
      <div className="cleaning-report-category-list">
        {report.categories.map((category) => (
          <div className="cleaning-report-category" key={`${category.category_id ?? 'snapshot'}-${category.name}`}>
            <div className="cleaning-report-category__heading">
              <strong>{category.name}</strong>
              <span>
                {t('cleaning.reportCategoryMeta', {
                  completions: category.completion_count,
                  tasks: category.unique_task_count,
                })}
              </span>
            </div>
            <div className="cleaning-report-bar" role="img" aria-label={category.name}>
              <span style={{ width: `${(category.completion_count / maxCount) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function MemberReport({ report, t }: ReportSectionProps) {
  return (
    <section className="cleaning-report-section" aria-labelledby="cleaning-report-member-heading">
      <div className="cleaning-report-section__heading">
        <h2 id="cleaning-report-member-heading">{t('cleaning.reportMembers')}</h2>
        <span>{t('cleaning.reportRanking')}</span>
      </div>
      <div className="cleaning-report-table-wrapper">
        <table className="cleaning-report-table">
          <thead>
            <tr>
              <th scope="col">{t('cleaning.reportUser')}</th>
              <th scope="col">{t('cleaning.reportCompletions')}</th>
              <th scope="col">{t('cleaning.reportUniqueTasks')}</th>
              <th scope="col">{t('cleaning.reportShare')}</th>
            </tr>
          </thead>
          <tbody>
            {report.members.map((member) => (
              <tr key={member.user_id}>
                <th scope="row">{member.username}</th>
                <td>{member.completion_count}</td>
                <td>{member.unique_task_count}</td>
                <td>{Math.round(member.completion_ratio * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function TaskReport({ report, t }: ReportSectionProps) {
  return (
    <section className="cleaning-report-section" aria-labelledby="cleaning-report-task-heading">
      <div className="cleaning-report-section__heading">
        <h2 id="cleaning-report-task-heading">{t('cleaning.reportTasks')}</h2>
        <span>{t('cleaning.reportTaskDescription')}</span>
      </div>
      <div className="cleaning-report-task-table-wrapper">
        <table className="cleaning-report-table cleaning-report-task-table">
          <thead>
            <tr>
              <th scope="col">{t('cleaning.place')}</th>
              <th scope="col">{t('cleaning.category')}</th>
              <th scope="col">{t('cleaning.reportCompletions')}</th>
              <th scope="col">{t('cleaning.reportParticipants')}</th>
              <th scope="col">{t('cleaning.reportBreakdown')}</th>
            </tr>
          </thead>
          <tbody>
            {report.tasks.map((task) => (
              <tr key={task.task_id}>
                <th scope="row">{task.name}</th>
                <td>{task.category_name}</td>
                <td>{task.completion_count}</td>
                <td>{task.participant_count}</td>
                <td>
                  <MemberBreakdown task={task} t={t} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="cleaning-report-task-collapsible">
        {report.tasks.map((task) => (
          <details key={task.task_id}>
            <summary>
              <span>
                <strong>{task.name}</strong>
                <small>{task.category_name}</small>
              </span>
              <b>{task.completion_count}</b>
            </summary>
            <dl>
              <div>
                <dt>{t('cleaning.reportParticipants')}</dt>
                <dd>{task.participant_count}</dd>
              </div>
            </dl>
            <MemberBreakdown task={task} t={t} />
          </details>
        ))}
      </div>
    </section>
  )
}

function MemberBreakdown({ task, t }: { task: ReportSectionProps['report']['tasks'][number]; t: Translator }) {
  return (
    <ul className="cleaning-report-member-breakdown">
      {task.members.map((member) => (
        <li key={member.user_id}>
          <span>{member.username}</span>
          <strong>{t('cleaning.reportMemberCount', { count: member.completion_count })}</strong>
        </li>
      ))}
    </ul>
  )
}

type ReportSectionProps = {
  report: NonNullable<ReturnType<typeof useCleaningReport>['report']>
  t: Translator
}

type Translator = (key: string, options?: Record<string, unknown>) => string

function formatMonth(month: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'long', timeZone: 'UTC' }).format(
    new Date(`${month}-01T00:00:00Z`),
  )
}

function formatDay(day: string): string {
  const [, month, date] = day.split('-')
  return `${Number(month)}/${Number(date)}`
}
