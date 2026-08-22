import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState } from '../../shared/ui/EmptyState'
import { TaskAltIcon } from '../../shared/ui/icons'
import { ChoreMonthlyReportFrame, type ChoreMonthlyReportData } from './ChoreMonthlyReportFrame'
import { useChoreMonthlyReport } from './useChoreMonthlyReport'

interface ChoreMonthlyReportPageProps {
  onUnauthorized: () => void
}

export function ChoreMonthlyReportPage({ onUnauthorized }: ChoreMonthlyReportPageProps) {
  const { t } = useTranslation()
  const state = useChoreMonthlyReport({ onUnauthorized })
  const maxCategoryCount = useMemo(
    () => Math.max(1, ...(state.report?.categories.map((category) => category.completion_count) ?? [])),
    [state.report?.categories],
  )

  return (
    <ChoreMonthlyReportFrame
      state={state}
      eyebrow={t('chores.reportEyebrow')}
      title={t('chores.reportTitle')}
      description={t('chores.reportDescription')}
    >
      {(report) =>
        report.summary.completion_count === 0 ? (
          <>
            <ReportSummary report={report} t={t} />
            <EmptyState
              className="chore-empty-state chore-monthly-report-empty"
              icon={<TaskAltIcon />}
              title={t('chores.reportEmpty')}
              description={t('chores.reportEmptyHelp')}
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
    </ChoreMonthlyReportFrame>
  )
}

function ReportSummary({ report, t }: ReportSectionProps) {
  const summary = report.summary
  const items = [
    { label: t('chores.reportCompletions'), value: summary.completion_count },
    { label: t('chores.reportUniqueTasks'), value: summary.unique_task_count },
    { label: t('chores.reportParticipants'), value: summary.participant_count },
    { label: t('chores.reportCategories'), value: summary.category_count },
  ]
  return (
    <section className="chore-monthly-report-section" aria-labelledby="chore-monthly-report-summary-heading">
      <h2 id="chore-monthly-report-summary-heading">{t('chores.reportSummary')}</h2>
      <dl className="chore-monthly-report-summary">
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
    <section className="chore-monthly-report-section" aria-labelledby="chore-monthly-report-category-heading">
      <div className="chore-monthly-report-section__heading">
        <h2 id="chore-monthly-report-category-heading">{t('chores.reportCategoriesByCount')}</h2>
        <span>{t('chores.reportCompletionCount')}</span>
      </div>
      <div className="chore-monthly-report-category-list">
        {report.categories.map((category) => (
          <div className="chore-monthly-report-category" key={`${category.category_id ?? 'snapshot'}-${category.name}`}>
            <div className="chore-monthly-report-category__heading">
              <strong>{category.name}</strong>
              <span>
                {t('chores.reportCategoryMeta', {
                  completions: category.completion_count,
                  tasks: category.unique_task_count,
                })}
              </span>
            </div>
            <div className="chore-monthly-report-bar" role="img" aria-label={category.name}>
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
    <section className="chore-monthly-report-section" aria-labelledby="chore-monthly-report-member-heading">
      <div className="chore-monthly-report-section__heading">
        <h2 id="chore-monthly-report-member-heading">{t('chores.reportMembers')}</h2>
        <span>{t('chores.reportRanking')}</span>
      </div>
      <div className="chore-monthly-report-table-wrapper">
        <table className="chore-monthly-report-table">
          <thead>
            <tr>
              <th scope="col">{t('chores.reportUser')}</th>
              <th scope="col">{t('chores.reportCompletions')}</th>
              <th scope="col">{t('chores.reportUniqueTasks')}</th>
              <th scope="col">{t('chores.reportCompletionRate')}</th>
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
      <div className="chore-monthly-report-member-cards" role="list" aria-label={t('chores.reportMembers')}>
        {report.members.map((member, index) => (
          <article className="chore-monthly-report-member-card" role="listitem" key={member.user_id}>
            <div className="chore-monthly-report-member-card__heading">
              <strong>
                {index + 1}. {member.username}
              </strong>
              <b>{Math.round(member.completion_ratio * 100)}%</b>
            </div>
            <dl>
              <div>
                <dt>{t('chores.reportCompletions')}</dt>
                <dd>{member.completion_count}</dd>
              </div>
              <div>
                <dt>{t('chores.reportUniqueTasks')}</dt>
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
    <section className="chore-monthly-report-section" aria-labelledby="chore-monthly-report-task-heading">
      <div className="chore-monthly-report-section__heading">
        <h2 id="chore-monthly-report-task-heading">{t('chores.reportTasks')}</h2>
        <span>{t('chores.reportTaskDescription')}</span>
      </div>
      <div className="chore-monthly-report-task-table-wrapper">
        <table className="chore-monthly-report-table chore-monthly-report-task-table">
          <thead>
            <tr>
              <th scope="col">{t('chores.taskName')}</th>
              <th scope="col">{t('chores.category')}</th>
              <th scope="col">{t('chores.reportCompletions')}</th>
              <th scope="col">{t('chores.reportParticipants')}</th>
              <th scope="col">{t('chores.reportBreakdown')}</th>
            </tr>
          </thead>
          <tbody>
            {report.tasks.map((task) => (
              <tr key={task.task_id}>
                <th scope="row">{task.task_name}</th>
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
      <div className="chore-monthly-report-task-collapsible">
        {report.tasks.map((task) => (
          <details key={task.task_id}>
            <summary>
              <span>
                <strong>{task.task_name}</strong>
                <small>{task.category_name}</small>
              </span>
              <b>{task.completion_count}</b>
            </summary>
            <dl>
              <div>
                <dt>{t('chores.reportParticipants')}</dt>
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
    <ul className="chore-monthly-report-member-breakdown">
      {task.members.map((member) => (
        <li key={member.user_id}>
          <span>{member.username}</span>
          <strong>{t('chores.reportMemberCount', { count: member.completion_count })}</strong>
        </li>
      ))}
    </ul>
  )
}

type ReportSectionProps = {
  report: ChoreMonthlyReportData
  t: Translator
}

type Translator = (key: string, options?: Record<string, unknown>) => string
