import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { TaskAltIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { CleaningReportFrame, type CleaningReportData } from './CleaningReportFrame'
import { useCleaningReport } from './useCleaningReport'

type DailyView = 'calendar' | 'chart'

interface CleaningDailyPageProps {
  onUnauthorized: () => void
}

export function CleaningDailyPage({ onUnauthorized }: CleaningDailyPageProps) {
  const { t, i18n } = useTranslation()
  const state = useCleaningReport({ onUnauthorized })
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
    <CleaningReportFrame
      state={state}
      eyebrow={t('cleaning.dailyEyebrow')}
      title={t('cleaning.dailyTitle')}
      description={t('cleaning.dailyDescription')}
    >
      {(report) =>
        report.summary.completion_count === 0 ? (
          <EmptyState
            className="cleaning-empty-state cleaning-report-empty"
            icon={<TaskAltIcon />}
            title={t('cleaning.reportEmpty')}
            description={t('cleaning.reportEmptyHelp')}
          />
        ) : (
          <section className="cleaning-report-section cleaning-report-daily-page" aria-labelledby="daily-view-heading">
            <div className="cleaning-report-section__heading cleaning-report-daily-page__heading">
              <div>
                <h2 id="daily-view-heading">{t('cleaning.reportDaily')}</h2>
                <span>{t('cleaning.reportCompletionCount')}</span>
              </div>
              <div className="cleaning-report-view-switcher" role="group" aria-label={t('cleaning.dailyViewLabel')}>
                <button
                  className={view === 'calendar' ? 'secondary-button is-active' : 'secondary-button'}
                  type="button"
                  aria-pressed={view === 'calendar'}
                  onClick={() => setView('calendar')}
                >
                  {t('cleaning.dailyCalendar')}
                </button>
                <button
                  className={view === 'chart' ? 'secondary-button is-active' : 'secondary-button'}
                  type="button"
                  aria-pressed={view === 'chart'}
                  onClick={() => setView('chart')}
                >
                  {t('cleaning.dailyChart')}
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
    </CleaningReportFrame>
  )
}

function DailyCalendar({ report, locale, t }: { report: CleaningReportData; locale: string; t: Translator }) {
  const firstDay = report.daily[0]?.day
  const leadingDays = firstDay ? getWeekday(firstDay) : 0
  const maxCount = Math.max(1, ...report.daily.map((day) => day.completion_count))
  const weekdayLabels = Array.from({ length: 7 }, (_, index) =>
    new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' }).format(
      new Date(Date.UTC(2026, 0, 4 + index)),
    ),
  )

  return (
    <div className="cleaning-report-calendar" role="grid" aria-label={t('cleaning.dailyCalendarLabel')}>
      {weekdayLabels.map((label) => (
        <div className="cleaning-report-calendar__weekday" role="columnheader" key={label}>
          {label}
        </div>
      ))}
      {Array.from({ length: leadingDays }, (_, index) => (
        <div
          className="cleaning-report-calendar__cell cleaning-report-calendar__cell--empty"
          role="gridcell"
          key={`empty-${index}`}
        />
      ))}
      {report.daily.map((day) => {
        const count = day.completion_count
        const level = count === 0 ? 0 : Math.max(1, Math.ceil((count / maxCount) * 4))
        return (
          <div
            className={`cleaning-report-calendar__cell cleaning-report-calendar__cell--level-${level}`}
            role="gridcell"
            aria-label={t('cleaning.dailyDateAria', {
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

function DailyChart({ report, t }: { report: CleaningReportData; t: Translator }) {
  const maxCount = Math.max(1, ...report.daily.map((day) => day.completion_count))
  return (
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
