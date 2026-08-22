import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { BarChartIcon, PlusIcon, RefreshIcon, UndoIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { formatDateTime } from '../../shared/lib/format'
import type { ShoppingPurchase, ShoppingTrip } from './api'
import { useShoppingHistory } from './useShoppingWorkflow'

interface ShoppingHistoryPageProps {
  onUnauthorized: () => void
}

interface StatisticRow {
  name?: string
  username?: string
  count?: number
}

const asStatisticRows = (value: Array<{ [key: string]: unknown }> | undefined): StatisticRow[] =>
  (value ?? []).map((row) => ({
    name: typeof row.name === 'string' ? row.name : undefined,
    username: typeof row.username === 'string' ? row.username : undefined,
    count: typeof row.count === 'number' ? row.count : undefined,
  }))

export function ShoppingHistoryPage({ onUnauthorized }: ShoppingHistoryPageProps) {
  const { t } = useTranslation()
  const state = useShoppingHistory({ onUnauthorized })
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  const [unplannedNames, setUnplannedNames] = useState<Record<string, string>>({})
  const [unplannedCategories, setUnplannedCategories] = useState<Record<string, string>>({})
  const purchaserRows = asStatisticRows(state.statistics?.purchasers)
  const assigneeRows = asStatisticRows(state.statistics?.assignees)
  const purchaserCounts = new Map(
    purchaserRows.map((row) => [row.username ?? row.name ?? t('common.unknown'), row.count ?? 0]),
  )
  const assigneeCounts = new Map(
    assigneeRows.map((row) => [row.username ?? row.name ?? t('common.unknown'), row.count ?? 0]),
  )
  const comparisonNames = [...new Set([...purchaserCounts.keys(), ...assigneeCounts.keys()])]

  const saveAmount = async (trip: ShoppingTrip) => {
    const raw = amounts[trip.id] ?? (trip.total_amount_yen === null ? '' : String(trip.total_amount_yen))
    const amount = raw.trim() === '' ? null : Number(raw)
    if (amount !== null && (!Number.isInteger(amount) || amount < 0)) return
    await state.saveTripAmount(trip.id, amount)
  }

  const addUnplanned = async (event: FormEvent, trip: ShoppingTrip) => {
    event.preventDefault()
    const name = (unplannedNames[trip.id] ?? '').trim()
    if (!name) return
    if (await state.addUnplanned(trip.id, name, unplannedCategories[trip.id] || null)) {
      setUnplannedNames((current) => ({ ...current, [trip.id]: '' }))
    }
  }

  const renderPurchase = (purchase: ShoppingPurchase) => (
    <li
      className={purchase.reversed_at ? 'shopping-purchase shopping-purchase--reversed' : 'shopping-purchase'}
      key={purchase.id}
    >
      <div>
        <strong>{purchase.item_name}</strong>
        <span>
          {purchase.shopping_item_id ? t('shopping.plannedPurchase') : t('shopping.unplannedPurchase')}
          {purchase.reversed_at ? ` · ${t('shopping.reversed')}` : ''}
        </span>
      </div>
      <div className="shopping-purchase__edit">
        <select
          className="form-control"
          aria-label={t('shopping.purchaseCategory', { itemName: purchase.item_name })}
          value={purchase.category_id ?? ''}
          disabled={state.submitting || Boolean(purchase.reversed_at)}
          onChange={(event) =>
            void state.updatePurchase(purchase.id, event.target.value || null, purchase.purchased_by_user_id)
          }
        >
          <option value="">{t('shopping.noCategory')}</option>
          {state.categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
        <select
          className="form-control"
          aria-label={t('shopping.purchaseBuyer', { itemName: purchase.item_name })}
          value={purchase.purchased_by_user_id}
          disabled={state.submitting || Boolean(purchase.reversed_at)}
          onChange={(event) => void state.updatePurchase(purchase.id, purchase.category_id, event.target.value || null)}
        >
          {state.members.map((member) => (
            <option key={member.user_id} value={member.user_id}>
              {member.username}
            </option>
          ))}
        </select>
        {!purchase.reversed_at && (
          <button
            className="secondary-button icon-button"
            type="button"
            disabled={state.submitting}
            onClick={() => void state.reversePurchase(purchase.id)}
          >
            <UndoIcon />
            {t('shopping.reverse')}
          </button>
        )}
      </div>
    </li>
  )

  return (
    <main id="top" className="shopping-page">
      <section className="shopping-hero shopping-hero--compact">
        <p className="eyebrow">{t('shopping.historyEyebrow')}</p>
        <h1>{t('shopping.historyTitle')}</h1>
        <p>{t('shopping.historyDescription')}</p>
      </section>

      <section className="shopping-board shopping-history-page">
        <GroupScopedToolbar
          groups={state.groups}
          selectedGroupId={state.selectedGroupId}
          selectId="shopping-history-group"
          label={t('shopping.group')}
          selectDisabled={state.loading || state.submitting || state.groups.length === 0}
          refreshDisabled={state.loading || state.submitting}
          onSelectGroup={state.selectGroup}
          onRefresh={state.refresh}
        />
        {state.pageError && <PageMessage>{state.pageError}</PageMessage>}

        {state.groups.length === 0 ? (
          <EmptyState
            icon={<BarChartIcon />}
            title={t('shopping.groupNeeded')}
            description={t('shopping.groupNeededHelp')}
          />
        ) : (
          <>
            <div className="shopping-statistics-filter">
              <label>
                {t('shopping.fromDate')}
                <input
                  className="form-control"
                  type="date"
                  value={state.fromDate}
                  onChange={(event) => state.setFromDate(event.target.value)}
                />
              </label>
              <label>
                {t('shopping.toDate')}
                <input
                  className="form-control"
                  type="date"
                  value={state.toDate}
                  onChange={(event) => state.setToDate(event.target.value)}
                />
              </label>
            </div>

            {state.statistics && (
              <section className="shopping-statistics" aria-labelledby="shopping-statistics-heading">
                <div className="section-heading">
                  <div>
                    <h2 id="shopping-statistics-heading">{t('shopping.statistics')}</h2>
                    <p>{t('shopping.statisticsHelp')}</p>
                  </div>
                </div>
                <div className="shopping-statistics__cards">
                  <div>
                    <strong>{state.statistics.total_amount_yen.toLocaleString()}円</strong>
                    <span>{t('shopping.spendingTotal')}</span>
                  </div>
                  <div>
                    <strong>{state.statistics.trip_count}</strong>
                    <span>{t('shopping.tripCount')}</span>
                  </div>
                  <div>
                    <strong>{state.statistics.unrecorded_trip_count}</strong>
                    <span>{t('shopping.unrecordedTrips')}</span>
                  </div>
                  <div>
                    <strong>{state.statistics.purchase_count}</strong>
                    <span>{t('shopping.purchaseCount')}</span>
                  </div>
                  <div>
                    <strong>
                      {state.statistics.planned_purchase_count} / {state.statistics.unplanned_purchase_count}
                    </strong>
                    <span>{t('shopping.plannedVsUnplanned')}</span>
                  </div>
                </div>
                <div className="shopping-statistics__columns">
                  <div>
                    <h3>{t('shopping.assignmentComparison')}</h3>
                    <ul>
                      {comparisonNames.map((name) => (
                        <li key={name}>
                          {name}:{' '}
                          {t('shopping.assignmentComparisonValue', {
                            requested: assigneeCounts.get(name) ?? 0,
                            purchased: purchaserCounts.get(name) ?? 0,
                          })}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3>{t('shopping.categories')}</h3>
                    <ul>
                      {asStatisticRows(state.statistics.categories).map((row) => (
                        <li key={row.name}>
                          {row.name ?? t('shopping.noCategory')}: {row.count}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3>{t('shopping.monthlyTrend')}</h3>
                    <ul>
                      {state.statistics.monthly.map((row) => (
                        <li key={String(row.month)}>
                          {String(row.month)}: {String(row.amount_yen)}円
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </section>
            )}

            <div className="shopping-history-list">
              <div className="section-heading">
                <div>
                  <h2>{t('shopping.tripHistory')}</h2>
                  <p>{t('shopping.tripHistoryHelp')}</p>
                </div>
              </div>
              {state.loading ? (
                <p>{t('shopping.loading')}</p>
              ) : state.trips.length === 0 ? (
                <p className="shopping-muted">{t('shopping.historyEmpty')}</p>
              ) : (
                state.trips.map((trip) => (
                  <article className="shopping-trip" key={trip.id}>
                    <header className="shopping-trip__header">
                      <div>
                        <h3>{formatDateTime(trip.started_at)}</h3>
                        <p>
                          {t('shopping.startedBy', { username: trip.started_by_username })} ·{' '}
                          {t('shopping.purchaseSummary', { count: trip.active_purchase_count })}
                        </p>
                      </div>
                      <div className="shopping-trip__amount">
                        <label>
                          {t('shopping.tripAmount')}
                          <input
                            className="form-control"
                            inputMode="numeric"
                            type="number"
                            min="0"
                            step="1"
                            value={
                              amounts[trip.id] ?? (trip.total_amount_yen === null ? '' : String(trip.total_amount_yen))
                            }
                            placeholder={t('shopping.amountUnrecorded')}
                            onChange={(event) =>
                              setAmounts((current) => ({ ...current, [trip.id]: event.target.value }))
                            }
                          />
                        </label>
                        <button
                          className="success-button icon-button"
                          type="button"
                          disabled={state.submitting}
                          onClick={() => void saveAmount(trip)}
                        >
                          <RefreshIcon />
                          {t('shopping.saveAmount')}
                        </button>
                      </div>
                    </header>
                    {trip.total_amount_yen === null && (
                      <p className="shopping-unrecorded">{t('shopping.amountUnrecorded')}</p>
                    )}
                    <ul className="shopping-purchase-list">{(trip.purchases ?? []).map(renderPurchase)}</ul>
                    <form className="shopping-unplanned-form" onSubmit={(event) => void addUnplanned(event, trip)}>
                      <input
                        className="form-control"
                        value={unplannedNames[trip.id] ?? ''}
                        maxLength={120}
                        placeholder={t('shopping.unplannedPlaceholder')}
                        onChange={(event) =>
                          setUnplannedNames((current) => ({ ...current, [trip.id]: event.target.value }))
                        }
                      />
                      <select
                        className="form-control"
                        value={unplannedCategories[trip.id] ?? ''}
                        onChange={(event) =>
                          setUnplannedCategories((current) => ({ ...current, [trip.id]: event.target.value }))
                        }
                      >
                        <option value="">{t('shopping.noCategory')}</option>
                        {state.categories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                          </option>
                        ))}
                      </select>
                      <button
                        className="secondary-button icon-button"
                        type="submit"
                        disabled={state.submitting || !(unplannedNames[trip.id] ?? '').trim()}
                      >
                        <PlusIcon />
                        {t('shopping.addUnplanned')}
                      </button>
                    </form>
                  </article>
                ))
              )}
              {state.hasMore && (
                <button
                  className="secondary-button icon-button shopping-load-more"
                  type="button"
                  disabled={state.loadingMore}
                  onClick={() => void state.loadMore()}
                >
                  <PlusIcon />
                  {t('shopping.loadMore')}
                </button>
              )}
            </div>
          </>
        )}
      </section>
    </main>
  )
}
