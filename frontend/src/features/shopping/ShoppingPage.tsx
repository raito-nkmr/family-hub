import { useTranslation } from 'react-i18next'
import { CancelIcon, CheckCircleIcon, CheckIcon, StartIcon, StoreIcon, UndoIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { useShoppingStore } from './useShoppingWorkflow'

interface ShoppingPageProps {
  onUnauthorized: () => void
}

export function ShoppingPage({ onUnauthorized }: ShoppingPageProps) {
  const { t } = useTranslation()
  const state = useShoppingStore({ onUnauthorized })

  return (
    <main id="top" className="shopping-page shopping-page--store">
      <section className="shopping-hero shopping-hero--compact">
        <p className="eyebrow">{t('shopping.storeEyebrow')}</p>
        <h1>{t('shopping.storeTitle')}</h1>
        <p>{t('shopping.storeDescription')}</p>
      </section>

      <section className="shopping-board shopping-store" aria-labelledby="shopping-store-heading">
        <GroupScopedToolbar
          groups={state.groups}
          selectedGroupId={state.selectedGroupId}
          selectId="shopping-store-group"
          label={t('shopping.group')}
          selectDisabled={state.loading || state.submitting || state.groups.length === 0}
          refreshDisabled={state.loading || state.submitting}
          onSelectGroup={state.selectGroup}
          onRefresh={state.refresh}
        />

        {state.groups.length > 0 && (
          <div className="shopping-store__controls">
            <div>
              <h2 id="shopping-store-heading">{t('shopping.storeList')}</h2>
              <p>{t('shopping.remaining', { count: state.items.length })}</p>
            </div>
            <div className="shopping-store__trip-controls">
              {state.activeTrip ? (
                <>
                  <span className="shopping-trip-status">{t('shopping.tripInProgress')}</span>
                  <button
                    className="success-button icon-button"
                    type="button"
                    disabled={state.submitting}
                    onClick={() => void state.endTrip()}
                  >
                    <CheckIcon />
                    {t('shopping.endTrip')}
                  </button>
                  <button
                    className="secondary-button icon-button"
                    type="button"
                    disabled={state.submitting}
                    onClick={() => void state.discardTrip()}
                  >
                    <CancelIcon />
                    {t('shopping.discardTrip')}
                  </button>
                </>
              ) : (
                <button
                  className="secondary-button icon-button"
                  type="button"
                  disabled={state.submitting}
                  onClick={() => void state.beginTrip()}
                >
                  <StartIcon />
                  {t('shopping.startTrip')}
                </button>
              )}
            </div>
          </div>
        )}

        {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
        {state.loading ? (
          <div className="shopping-store-list" aria-label={t('shopping.loading')}>
            {Array.from({ length: 4 }, (_, index) => (
              <div className="shopping-store-item shopping-store-item--skeleton" key={index} />
            ))}
          </div>
        ) : state.groups.length === 0 ? (
          <EmptyState
            className="shopping-empty-state"
            icon={<StoreIcon />}
            title={t('shopping.groupNeeded')}
            description={t('shopping.groupNeededHelp')}
          />
        ) : state.items.length === 0 ? (
          <EmptyState
            className="shopping-empty-state"
            icon={<CheckCircleIcon />}
            title={t('shopping.storeEmpty')}
            description={t('shopping.storeEmptyHelp')}
          />
        ) : (
          <div className="shopping-store-list">
            {state.items.map((item) => (
              <button
                className="shopping-store-item"
                type="button"
                key={item.id}
                disabled={state.pendingItemIds.has(item.id)}
                aria-label={t('shopping.purchaseLabel', { itemName: item.name })}
                onClick={() => void state.purchase(item)}
              >
                <span className="shopping-store-item__name">{item.name}</span>
                {item.assignee_username && (
                  <span className="shopping-store-item__assignee">
                    {t('shopping.requestedTo', { username: item.assignee_username })}
                  </span>
                )}
                <CheckCircleIcon />
              </button>
            ))}
          </div>
        )}

        {state.lastPurchase && (
          <div className="shopping-undo" role="status">
            <span>{t('shopping.purchasedNotice', { itemName: state.lastPurchase.purchase.item_name })}</span>
            <button className="secondary-button icon-button" type="button" onClick={() => void state.undo()}>
              <UndoIcon />
              {t('shopping.undoImmediately')}
            </button>
          </div>
        )}
      </section>
    </main>
  )
}
