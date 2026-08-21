import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { TaskAltIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { ChoreReportFrame, type ChoreReportData } from './ChoreReportFrame'
import { useChoreReport } from './useChoreReport'

type DailyView = 'calendar' | 'chart'

interface ChoreDailyPageProps {
  onUnauthorized: () => void
}

export function ChoreDailyPage({ onUnauthorized }: ChoreDailyPageProps) {
  const { t, i18n } = useTranslation()
  const state = useChoreReport({ onUnauthorized })
  const [searchParams, setSearchParams] = useSearchParams()
  const view: DailyView = searchParams.get('view') === 'chart' ? 'chart' : 'calendar'

  const setView = (nextView: DailyView) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('view', nextView)
        return next
      },
      { replace: true },
    )
  }

  return (
    <ChoreReportFrame
      state={state}
      eyebrow={t('chores.dailyEyebrow')}
      title={t('chores.dailyTitle')}
      description={t('chores.dailyDescription')}
    >
      {(report) =>
        report.summary.completion_count === 0 ? (
          <EmptyState
            className="chore-empty-state chore-report-empty"
            icon={<TaskAltIcon />}
            title={t('chores.reportEmpty')}
            description={t('chores.reportEmptyHelp')}
          />
        ) : (
          <section className="chore-report-section chore-report-daily-page" aria-labelledby="daily-view-heading">
            <div className="chore-report-section__heading chore-report-daily-page__heading">
              <div>
                <h2 id="daily-view-heading">{t('chores.reportDaily')}</h2>
                <span>{t('chores.reportCompletionCount')}</span>
              </div>
              <div className="chore-report-view-switcher" role="group" aria-label={t('chores.dailyViewLabel')}>
                <button
                  className={view === 'calendar' ? 'secondary-button is-active' : 'secondary-button'}
                  type="button"
                  aria-pressed={view === 'calendar'}
                  onClick={() => setView('calendar')}
                >
                  {t('chores.dailyCalendar')}
                </button>
                <button
                  className={view === 'chart' ? 'secondary-button is-active' : 'secondary-button'}
                  type="button"
                  aria-pressed={view === 'chart'}
                  onClick={() => setView('chart')}
                >
                  {t('chores.dailyChart')}
                </button>
              </div>
            </div>
            {view === 'calendar' ? (
              <DailyCalendar report={report} locale={i18n.language} t={t} />
            ) : (
              <DailyChart report={report} t={t} />
            )}
          </section>
        )
      }
    </ChoreReportFrame>
  )
}

function DailyCalendar({ report, locale, t }: { report: ChoreReportData; locale: string; t: Translator }) {
  const firstDay = report.daily[0]?.day
  const leadingDays = firstDay ? getWeekday(firstDay) : 0
  const maxCount = Math.max(1, ...report.daily.map((day) => day.completion_count))
  const weekdayLabels = Array.from({ length: 7 }, (_, index) =>
    new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' }).format(
      new Date(Date.UTC(2026, 0, 4 + index)),
    ),
  )

  return (
    <div className="chore-report-calendar" role="grid" aria-label={t('chores.dailyCalendarLabel')}>
      {weekdayLabels.map((label) => (
        <div className="chore-report-calendar__weekday" role="columnheader" key={label}>
          {label}
        </div>
      ))}
      {Array.from({ length: leadingDays }, (_, index) => (
        <div
          className="chore-report-calendar__cell chore-report-calendar__cell--empty"
          role="gridcell"
          key={`empty-${index}`}
        />
      ))}
      {report.daily.map((day) => {
        const count = day.completion_count
        const level = count === 0 ? 0 : Math.max(1, Math.ceil((count / maxCount) * 4))
        return (
          <div
            className={`chore-report-calendar__cell chore-report-calendar__cell--level-${level}`}
            role="gridcell"
            aria-label={t('chores.dailyDateAria', {
              day: formatDate(day.day, locale),
              count,
            })}
            key={day.day}
          >
            <span>{Number(day.day.slice(-2))}</span>
            <strong>{count}</strong>
          </div>
        )
      })}
    </div>
  )
}

function DailyChart({ report, t }: { report: ChoreReportData; t: Translator }) {
  const maxCount = Math.max(1, ...report.daily.map((day) => day.completion_count))
  return (
    <div className="chore-report-daily" role="list">
      {report.daily.map((day) => (
        <div className="chore-report-daily__item" role="listitem" key={day.day}>
          <div className="chore-report-daily__label">
            <span>{formatDay(day.day)}</span>
            <strong>{day.completion_count}</strong>
          </div>
          <div
            className="chore-report-bar"
            role="img"
            aria-label={t('chores.reportDailyAria', { day: formatDay(day.day), count: day.completion_count })}
          >
            <span style={{ width: `${(day.completion_count / maxCount) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

type Translator = (key: string, options?: Record<string, unknown>) => string

function getWeekday(day: string): number {
  const [year, month] = day.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, 1)).getUTCDay()
}

function formatDate(day: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { month: 'long', day: 'numeric', timeZone: 'UTC' }).format(
    new Date(`${day}T00:00:00Z`),
  )
}

function formatDay(day: string): string {
  const [, month, date] = day.split('-')
  return `${Number(month)}/${Number(date)}`
}
