import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState } from '../../shared/ui/EmptyState'
import { TaskAltIcon } from '../../shared/ui/icons'
import { CleaningReportFrame, type CleaningReportData } from './CleaningReportFrame'
import { useCleaningReport } from './useCleaningReport'

interface CleaningReportPageProps {
  onUnauthorized: () => void
}

export function CleaningReportPage({ onUnauthorized }: CleaningReportPageProps) {
  const { t } = useTranslation()
  const state = useCleaningReport({ onUnauthorized })
  const maxCategoryCount = useMemo(
    () => Math.max(1, ...(state.report?.categories.map((category) => category.completion_count) ?? [])),
    [state.report?.categories],
  )

  return (
    <CleaningReportFrame
      state={state}
      eyebrow={t('cleaning.reportEyebrow')}
      title={t('cleaning.reportTitle')}
      description={t('cleaning.reportDescription')}
    >
      {(report) =>
        report.summary.completion_count === 0 ? (
          <>
            <ReportSummary report={report} t={t} />
            <EmptyState
              className="cleaning-empty-state cleaning-report-empty"
              icon={<TaskAltIcon />}
              title={t('cleaning.reportEmpty')}
              description={t('cleaning.reportEmptyHelp')}
            />
          </>
        ) : (
          <>
            <ReportSummary report={report} t={t} />
            <CategoryReport report={report} maxCount={maxCategoryCount} t={t} />
            <MemberReport report={report} t={t} />
            <TaskReport report={report} t={t} />
          </>
        )
      }
    </CleaningReportFrame>
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
      <div className="cleaning-report-member-cards" role="list" aria-label={t('cleaning.reportMembers')}>
        {report.members.map((member, index) => (
          <article className="cleaning-report-member-card" role="listitem" key={member.user_id}>
            <div className="cleaning-report-member-card__heading">
              <strong>
                {index + 1}. {member.username}
              </strong>
              <b>{Math.round(member.completion_ratio * 100)}%</b>
            </div>
            <dl>
              <div>
                <dt>{t('cleaning.reportCompletions')}</dt>
                <dd>{member.completion_count}</dd>
              </div>
              <div>
                <dt>{t('cleaning.reportUniqueTasks')}</dt>
                <dd>{member.unique_task_count}</dd>
              </div>
            </dl>
          </article>
        ))}
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
  report: CleaningReportData
  t: Translator
}

type Translator = (key: string, options?: Record<string, unknown>) => string
