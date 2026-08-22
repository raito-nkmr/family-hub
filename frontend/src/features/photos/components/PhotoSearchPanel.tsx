import { useEffect, useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { FilterIcon, FilterOffIcon } from '../../../shared/ui/icons'
import type { PhotoFilters, PhotoSearchOptions, PhotoTimeline, PhotoVisibility } from '../api'

interface PhotoSearchPanelProps {
  filters: PhotoFilters
  timeline: PhotoTimeline | null
  searchOptions?: PhotoSearchOptions | null
  searchOptionsLoading?: boolean
  showSharingGroupFilter?: boolean
  disabled: boolean
  onSearch: (filters: PhotoFilters) => void
  onTimelineYearChange?: (year: number) => void
}

function monthRange(monthValue: string): Pick<PhotoFilters, 'dateFrom' | 'dateTo'> {
  const [year, month] = monthValue.split('-').map(Number)
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate()
  return { dateFrom: `${monthValue}-01`, dateTo: `${monthValue}-${String(lastDay).padStart(2, '0')}` }
}

export function PhotoSearchPanel({
  filters,
  timeline,
  searchOptions = null,
  searchOptionsLoading = false,
  showSharingGroupFilter = true,
  disabled,
  onSearch,
  onTimelineYearChange,
}: PhotoSearchPanelProps) {
  const { t } = useTranslation()
  const optionsId = useId()
  const [expanded, setExpanded] = useState(false)
  const [keyword, setKeyword] = useState(filters.q ?? '')
  const [dateFrom, setDateFrom] = useState(filters.dateFrom ?? '')
  const [dateTo, setDateTo] = useState(filters.dateTo ?? '')
  const [mineOnly, setMineOnly] = useState(filters.mineOnly ?? false)
  const [favoriteOnly, setFavoriteOnly] = useState(filters.favorite ?? false)
  const [visibility, setVisibility] = useState<PhotoVisibility | ''>(filters.visibility ?? '')
  const [uploaderId, setUploaderId] = useState(filters.uploaderId ?? '')
  const [sharingGroupId, setSharingGroupId] = useState(filters.sharingGroupId ?? '')
  const [capturedStatus, setCapturedStatus] = useState<'all' | 'known' | 'unknown'>(
    filters.capturedAtKnown === true ? 'known' : filters.capturedAtKnown === false ? 'unknown' : 'all',
  )

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      setKeyword(filters.q ?? '')
      setDateFrom(filters.dateFrom ?? '')
      setDateTo(filters.dateTo ?? '')
      setMineOnly(filters.mineOnly ?? false)
      setFavoriteOnly(filters.favorite ?? false)
      setVisibility(filters.visibility ?? '')
      setUploaderId(filters.uploaderId ?? '')
      setSharingGroupId(filters.sharingGroupId ?? '')
      setCapturedStatus(
        filters.capturedAtKnown === true ? 'known' : filters.capturedAtKnown === false ? 'unknown' : 'all',
      )
    })
    return () => {
      cancelled = true
    }
  }, [
    filters.q,
    filters.dateFrom,
    filters.dateTo,
    filters.mineOnly,
    filters.favorite,
    filters.visibility,
    filters.uploaderId,
    filters.sharingGroupId,
    filters.capturedAtKnown,
  ])

  const activeFilterCount = [
    filters.q,
    filters.dateFrom,
    filters.dateTo,
    filters.mineOnly,
    filters.favorite,
    filters.visibility,
    filters.uploaderId,
    showSharingGroupFilter && filters.sharingGroupId,
    filters.capturedAtKnown !== undefined,
  ].filter(Boolean).length

  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSearch({
      q: keyword.trim() || undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      mineOnly: mineOnly || undefined,
      favorite: favoriteOnly || undefined,
      visibility: visibility || undefined,
      uploaderId: uploaderId || undefined,
      capturedAtKnown: capturedStatus === 'all' ? undefined : capturedStatus === 'known',
      ...(showSharingGroupFilter ? { sharingGroupId: sharingGroupId || undefined } : {}),
    })
    setExpanded(false)
  }

  const clear = () => {
    setKeyword('')
    setDateFrom('')
    setDateTo('')
    setMineOnly(false)
    setFavoriteOnly(false)
    setVisibility('')
    setUploaderId('')
    setSharingGroupId('')
    setCapturedStatus('all')
    onSearch({})
    setExpanded(false)
  }

  return (
    <div className={`photo-search${expanded ? ' photo-search--expanded' : ''}`}>
      <button
        className="photo-search__toggle"
        type="button"
        aria-expanded={expanded}
        aria-controls={optionsId}
        aria-label={t(expanded ? 'photoSearch.hideConditions' : 'photoSearch.showConditions')}
        onClick={() => setExpanded((current) => !current)}
      >
        <span>
          <FilterIcon />
          {t('photoSearch.conditions')}
        </span>
        {activeFilterCount > 0 && <small>{t('photoSearch.activeCount', { count: activeFilterCount })}</small>}
        <span aria-hidden="true">{expanded ? '−' : '+'}</span>
      </button>

      <div className="photo-search__body" id={optionsId}>
        <form className="photo-search__form" onSubmit={submit}>
          <label className="photo-search__keyword">
            <span>{t('photoSearch.keyword')}</span>
            <input
              className="form-control form-control--page"
              type="search"
              value={keyword}
              maxLength={100}
              placeholder={t('photoSearch.keywordPlaceholder')}
              onChange={(event) => setKeyword(event.target.value)}
            />
          </label>
          <label>
            <span>{t('photoSearch.startDate')}</span>
            <input
              className="form-control form-control--page"
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label>
            <span>{t('photoSearch.uploader')}</span>
            <select
              className="form-control form-control--page"
              value={uploaderId}
              disabled={disabled || searchOptionsLoading || mineOnly}
              onChange={(event) => {
                setUploaderId(event.target.value)
                if (event.target.value) setMineOnly(false)
              }}
            >
              <option value="">{t('photoSearch.all')}</option>
              {searchOptions?.uploaders.map((uploader) => (
                <option key={uploader.id} value={uploader.id}>
                  {uploader.label}
                </option>
              ))}
            </select>
          </label>
          {showSharingGroupFilter && (
            <label>
              <span>{t('photoSearch.sharedGroup')}</span>
              <select
                className="form-control form-control--page"
                value={sharingGroupId}
                disabled={disabled || searchOptionsLoading}
                onChange={(event) => setSharingGroupId(event.target.value)}
              >
                <option value="">{t('photoSearch.all')}</option>
                {searchOptions?.groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            <span>{t('photoSearch.endDate')}</span>
            <input
              className="form-control form-control--page"
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          <label>
            <span>{t('photoSearch.visibility')}</span>
            <select
              className="form-control form-control--page"
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as PhotoVisibility | '')}
            >
              <option value="">{t('photoSearch.all')}</option>
              <option value="private">{t('photoSearch.private')}</option>
              <option value="shared">{t('photoSearch.shared')}</option>
            </select>
          </label>
          <label>
            <span>{t('photoSearch.capturedAt')}</span>
            <select
              className="form-control form-control--page"
              value={capturedStatus}
              onChange={(event) => setCapturedStatus(event.target.value as typeof capturedStatus)}
            >
              <option value="all">{t('photoSearch.all')}</option>
              <option value="known">{t('photoSearch.known')}</option>
              <option value="unknown">{t('photoSearch.unknown')}</option>
            </select>
          </label>
          <label className="photo-search__mine">
            <input
              type="checkbox"
              checked={mineOnly}
              onChange={(event) => {
                setMineOnly(event.target.checked)
                if (event.target.checked) setUploaderId('')
              }}
            />
            <span>{t('photoSearch.mineOnly')}</span>
          </label>
          <label className="photo-search__mine">
            <input type="checkbox" checked={favoriteOnly} onChange={(event) => setFavoriteOnly(event.target.checked)} />
            <span>{t('photoSearch.favoriteOnly')}</span>
          </label>
          <div className="photo-search__actions">
            <button className="secondary-button icon-button" type="button" onClick={clear} disabled={disabled}>
              <FilterOffIcon />
              {t('photoSearch.clear')}
            </button>
            <button
              className="primary-button icon-button"
              type="submit"
              disabled={disabled || Boolean(dateFrom && dateTo && dateFrom > dateTo)}
            >
              <FilterIcon />
              {t('photoSearch.filter')}
            </button>
          </div>
        </form>

        {timeline && (
          <div className="photo-search__timeline" aria-label={t('photoSearch.timelineLabel', { year: timeline.year })}>
            <span className="photo-search__year">
              {onTimelineYearChange && (
                <button
                  type="button"
                  disabled={disabled || timeline.year <= 1}
                  onClick={() => onTimelineYearChange(timeline.year - 1)}
                >
                  ‹
                </button>
              )}
              {t('photoSearch.year', { year: timeline.year })}
              {onTimelineYearChange && (
                <button
                  type="button"
                  disabled={disabled || timeline.year >= 9998}
                  onClick={() => onTimelineYearChange(timeline.year + 1)}
                >
                  ›
                </button>
              )}
            </span>
            <div>
              {timeline.months.map(({ month, count }) => (
                <button
                  type="button"
                  key={month}
                  disabled={disabled}
                  onClick={() => {
                    const range = monthRange(month)
                    setDateFrom(range.dateFrom ?? '')
                    setDateTo(range.dateTo ?? '')
                    onSearch({ ...filters, ...range })
                    setExpanded(false)
                  }}
                >
                  {t('photoSearch.month', { month: Number(month.slice(5)) })} <small>{count}</small>
                </button>
              ))}
              {timeline.months.length === 0 && <small>{t('photoSearch.noPhotosInYear')}</small>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
