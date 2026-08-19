import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../shared/lib/format'
import { CheckIcon, PlusIcon, ShoppingCartIcon, UndoIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { useShopping } from './useShopping'

interface ShoppingPageProps {
  onUnauthorized: () => void
}

export function ShoppingPage({ onUnauthorized }: ShoppingPageProps) {
  const { t } = useTranslation()
  const state = useShopping({ onUnauthorized })
  const [name, setName] = useState('')
  const activeItems = state.items.filter((item) => item.purchased_at === null)
  const purchasedItems = state.items.filter((item) => item.purchased_at !== null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalized = name.trim()
    if (!normalized) return
    if (await state.addItem(normalized)) setName('')
  }

  return (
    <main id="top" className="shopping-page">
      <section className="shopping-hero">
        <h1>{t('shopping.title')}</h1>
        <p>{t('shopping.description')}</p>
      </section>

      <section className="shopping-board" aria-labelledby="shopping-board-heading">
        <GroupScopedToolbar
          groups={state.groups}
          selectedGroupId={state.selectedGroupId}
          selectId="shopping-group"
          label={t('shopping.group')}
          selectDisabled={
            state.loading || state.submitting || state.pendingItemIds.size > 0 || state.groups.length === 0
          }
          refreshDisabled={state.loading || state.submitting || state.pendingItemIds.size > 0}
          onSelectGroup={state.selectGroup}
          onRefresh={state.refresh}
        />

        {state.groups.length > 0 && (
          <form className="shopping-add" onSubmit={(event) => void submit(event)}>
            <label htmlFor="shopping-item-name">{t('shopping.itemName')}</label>
            <div>
              <input
                id="shopping-item-name"
                value={name}
                maxLength={120}
                placeholder={t('shopping.itemPlaceholder')}
                disabled={state.loading || state.submitting}
                aria-invalid={state.formError ? true : undefined}
                aria-describedby={state.formError ? 'shopping-item-error' : undefined}
                autoComplete="off"
                enterKeyHint="done"
                onChange={(event) => setName(event.target.value)}
              />
              <button type="submit" disabled={state.loading || state.submitting || name.trim().length === 0}>
                <PlusIcon />
                {t(state.submitting ? 'shopping.adding' : 'shopping.add')}
              </button>
            </div>
            {state.formError && (
              <p id="shopping-item-error" className="shopping-add__error" role="alert">
                {state.formError}
              </p>
            )}
          </form>
        )}

        <div className="section-heading shopping-board__heading">
          <div>
            <h2 id="shopping-board-heading">{t('shopping.list')}</h2>
            <p>{t('shopping.remaining', { count: activeItems.length })}</p>
          </div>
        </div>

        {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
        {state.loading ? (
          <div className="shopping-list" aria-label={t('shopping.loading')}>
            {Array.from({ length: 3 }, (_, index) => (
              <div className="shopping-item shopping-item--skeleton" key={index} />
            ))}
          </div>
        ) : state.groups.length === 0 ? (
          <EmptyState
            className="shopping-empty-state"
            icon={<ShoppingCartIcon />}
            title={t('shopping.groupNeeded')}
            description={t('shopping.groupNeededHelp')}
          />
        ) : activeItems.length === 0 ? (
          <EmptyState
            className="shopping-empty-state"
            icon={<CheckIcon />}
            title={t('shopping.empty')}
            description={t('shopping.emptyHelp')}
          />
        ) : (
          <div className="shopping-list">
            {activeItems.map((item) => (
              <article className="shopping-item" key={item.id}>
                <div>
                  <h3>{item.name}</h3>
                  <p>{t('shopping.waiting')}</p>
                </div>
                <button
                  type="button"
                  disabled={state.pendingItemIds.has(item.id)}
                  aria-label={t('shopping.purchaseLabel', { name: item.name })}
                  onClick={() => void state.changePurchaseState(item, true)}
                >
                  <CheckIcon />
                  <span>{t(state.pendingItemIds.has(item.id) ? 'shopping.purchasing' : 'shopping.purchased')}</span>
                </button>
              </article>
            ))}
          </div>
        )}

        {purchasedItems.length > 0 && (
          <details className="shopping-history">
            <summary>{t('shopping.history', { count: purchasedItems.length })}</summary>
            <div className="shopping-history__list">
              {purchasedItems.map((item) => (
                <div key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <span>
                      {t('shopping.purchasedMeta', {
                        username: item.purchased_by_username ?? t('common.unknown'),
                        date: item.purchased_at ? formatDateTime(item.purchased_at) : '',
                      })}
                    </span>
                  </div>
                  <button
                    type="button"
                    disabled={state.pendingItemIds.has(item.id)}
                    onClick={() => void state.changePurchaseState(item, false)}
                  >
                    <UndoIcon />
                    {t('shopping.restore')}
                  </button>
                </div>
              ))}
            </div>
          </details>
        )}
      </section>
    </main>
  )
}
