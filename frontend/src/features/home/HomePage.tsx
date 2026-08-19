import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { appPaths } from '../../app/routes'
import { formatDateTime } from '../../shared/lib/format'
import {
  CheckCircleIcon,
  CleaningIcon,
  PhotoActivityIcon,
  PhotoLibraryIcon,
  ShoppingCartIcon,
} from '../../shared/ui/icons'
import { LoadingState } from '../../shared/ui/LoadingState'
import { PageMessage } from '../../shared/ui/PageMessage'
import { RefreshButton } from '../../shared/ui/RefreshButton'
import { getCleaningDueStatus } from '../cleaning/status'
import type { FamilyGroup } from '../groups/api'
import { PwaInstallCard } from '../pwa/PwaInstallCard'
import type { PhotoListItem } from '../photos/api'
import { PhotoCard } from '../photos/components/PhotoCard'
import type { GroupCleaningTask, GroupShoppingItem } from './useHome'

interface HomePageProps {
  recentPhotos: PhotoListItem[]
  unseenPhotoCount: number
  groups: FamilyGroup[]
  cleaningTasks: GroupCleaningTask[]
  shoppingItems: GroupShoppingItem[]
  loading: boolean
  error: string | null
  onRefresh: () => void
  onSelectPhoto: (photo: PhotoListItem) => void
  showPwaInstallPrompt: boolean
  onShowPwaInstallGuide: () => void
  onDismissPwaInstallPrompt: () => void
}

export function HomePage({
  recentPhotos,
  unseenPhotoCount,
  groups,
  cleaningTasks,
  shoppingItems,
  loading,
  error,
  onRefresh,
  onSelectPhoto,
  showPwaInstallPrompt,
  onShowPwaInstallGuide,
  onDismissPwaInstallPrompt,
}: HomePageProps) {
  const { t } = useTranslation()
  const upcomingCleaning = [...cleaningTasks]
    .sort((left, right) => new Date(left.task.next_due_at).getTime() - new Date(right.task.next_due_at).getTime())
    .slice(0, 3)
  const nextShoppingItems = [...shoppingItems]
    .sort((left, right) => new Date(left.item.created_at).getTime() - new Date(right.item.created_at).getTime())
    .slice(0, 5)

  return (
    <main id="top" className="home-page">
      <header className="home-hero">
        <div>
          <h1>{t('home.title')}</h1>
          <p>{t('home.description')}</p>
        </div>
        <RefreshButton onClick={onRefresh} disabled={loading} />
      </header>

      {showPwaInstallPrompt && (
        <PwaInstallCard
          variant="home"
          onShowInstallGuide={onShowPwaInstallGuide}
          onDismiss={onDismissPwaInstallPrompt}
        />
      )}

      {error && <PageMessage>{error}</PageMessage>}
      {loading ? (
        <LoadingState label={t('home.loading')} />
      ) : (
        <div className="home-grid">
          <section className="home-panel home-panel--photos" aria-labelledby="home-photos-heading">
            <header>
              <span className="home-panel__icon">
                <PhotoActivityIcon />
              </span>
              <div>
                <h2 id="home-photos-heading">{t('home.photos')}</h2>
                <p>{t('home.unseenPhotos', { count: unseenPhotoCount })}</p>
              </div>
            </header>
            {recentPhotos.length > 0 ? (
              <div className="home-photo-grid">
                {recentPhotos.map((photo) => (
                  <PhotoCard key={photo.id} photo={photo} onSelect={onSelectPhoto} />
                ))}
              </div>
            ) : (
              <p className="home-panel__empty">{t('home.noPhotos')}</p>
            )}
            <Link className="secondary-button icon-button home-panel__action" to={appPaths.photos}>
              <PhotoLibraryIcon />
              {t('home.openPhotos')}
            </Link>
          </section>

          <section className="home-panel" aria-labelledby="home-cleaning-heading">
            <header>
              <span className="home-panel__icon">
                <CleaningIcon />
              </span>
              <div>
                <h2 id="home-cleaning-heading">{t('home.cleaning')}</h2>
                <p>{t('home.cleaningCount', { count: cleaningTasks.length })}</p>
              </div>
            </header>
            {upcomingCleaning.length > 0 ? (
              <ul className="home-summary-list">
                {upcomingCleaning.map(({ group, task }) => {
                  const due = getCleaningDueStatus(task)
                  return (
                    <li key={task.id}>
                      <CheckCircleIcon />
                      <span>
                        <strong>{task.name}</strong>
                        <small>
                          {group.name} · {due.label}
                        </small>
                      </span>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="home-panel__empty">{groups.length === 0 ? t('home.groupNeeded') : t('home.noCleaning')}</p>
            )}
            <Link className="secondary-button icon-button home-panel__action" to={appPaths.cleaning}>
              <CleaningIcon />
              {t('home.openCleaning')}
            </Link>
          </section>

          <section className="home-panel" aria-labelledby="home-shopping-heading">
            <header>
              <span className="home-panel__icon">
                <ShoppingCartIcon />
              </span>
              <div>
                <h2 id="home-shopping-heading">{t('home.shopping')}</h2>
                <p>{t('home.shoppingCount', { count: shoppingItems.length })}</p>
              </div>
            </header>
            {nextShoppingItems.length > 0 ? (
              <ul className="home-summary-list">
                {nextShoppingItems.map(({ group, item }) => (
                  <li key={item.id}>
                    <ShoppingCartIcon />
                    <span>
                      <strong>{item.name}</strong>
                      <small>
                        {group.name} · {formatDateTime(item.created_at)}
                      </small>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="home-panel__empty">{groups.length === 0 ? t('home.groupNeeded') : t('home.noShopping')}</p>
            )}
            <Link className="secondary-button icon-button home-panel__action" to={appPaths.shopping}>
              <ShoppingCartIcon />
              {t('home.openShopping')}
            </Link>
          </section>
        </div>
      )}
    </main>
  )
}
