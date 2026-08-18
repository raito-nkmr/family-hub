import { useTranslation } from 'react-i18next'
import { AlbumIcon, PlusIcon, RefreshIcon } from '../../shared/ui/icons'
import type { Photo, PhotoListItem } from '../photos/public'
import { AlbumCard } from './components/AlbumCard'
import { AlbumDetailView } from './components/AlbumDetailView'
import { AlbumFormDialog } from './components/AlbumFormDialog'
import { PhotoPickerDialog } from './components/PhotoPickerDialog'
import { useAlbums } from './useAlbums'

interface AlbumPageProps {
  onUnauthorized: () => void
  onSelectPhoto: (photo: Photo | PhotoListItem) => void
}

export function AlbumPage({ onUnauthorized, onSelectPhoto }: AlbumPageProps) {
  const { t } = useTranslation()
  const state = useAlbums({ onUnauthorized })

  if (state.detailLoading) {
    return (
      <main id="top" className="feature-loading" aria-label={t('albums.loading')}>
        <span className="spinner" />
      </main>
    )
  }

  return (
    <>
      {state.selectedAlbum ? (
        <AlbumDetailView
          key={state.selectedAlbum.id}
          album={state.selectedAlbum}
          error={state.pageError}
          removingPhotoIds={state.removingPhotoIds}
          hasMore={state.hasMore}
          loadingMore={state.loadingMore}
          loadMoreFailed={state.loadMoreFailed}
          onBack={state.backToList}
          onEdit={() => state.openDialog('edit')}
          onDelete={() => void state.remove()}
          onAddPhotos={() => state.openDialog('photos')}
          onSelectPhoto={onSelectPhoto}
          onRemovePhotos={state.removePhotos}
          onSetCover={state.setCover}
          onLoadMore={() => void state.loadMore()}
        />
      ) : (
        <main id="top" className="album-page">
          <section className="album-hero">
            <div>
              <h1>{t('albums.title')}</h1>
              <p>{t('albums.description')}</p>
            </div>
            <button className="primary-button icon-button" type="button" onClick={() => state.openDialog('create')}>
              <PlusIcon />
              {t('albums.create')}
            </button>
          </section>

          <section className="album-library" aria-labelledby="album-library-heading">
            <div className="section-heading">
              <div>
                <h2 id="album-library-heading">{t('albums.list')}</h2>
                <p>
                  {state.albums.length > 0
                    ? t('albums.count', { count: state.albums.length })
                    : t('albums.emptySummary')}
                </p>
              </div>
              <button
                className="refresh-button"
                type="button"
                onClick={() => void state.refresh()}
                disabled={state.loading}
              >
                <RefreshIcon />
                <span>{t('common.refresh')}</span>
              </button>
            </div>

            {state.pageError && (
              <div className="page-message page-message--error" role="alert">
                {state.pageError}
              </div>
            )}

            {state.loading ? (
              <div className="album-grid" aria-label={t('albums.loading')}>
                {Array.from({ length: 3 }, (_, index) => (
                  <div className="album-skeleton" key={index} />
                ))}
              </div>
            ) : state.albums.length > 0 ? (
              <div className="album-grid">
                {state.albums.map((album) => (
                  <AlbumCard key={album.id} album={album} onSelect={(item) => void state.openAlbum(item)} />
                ))}
              </div>
            ) : (
              <div className="empty-state album-empty-state">
                <span>
                  <AlbumIcon />
                </span>
                <h3>{t('albums.emptyTitle')}</h3>
                <p>{t('albums.emptyHelp')}</p>
              </div>
            )}
          </section>
        </main>
      )}

      {state.showCreateDialog && (
        <AlbumFormDialog
          submitting={state.submitting}
          error={state.dialogError}
          groups={state.groups}
          onSubmit={state.create}
          onClose={state.closeCreateDialog}
        />
      )}
      {state.showEditDialog && state.selectedAlbum && (
        <AlbumFormDialog
          album={state.selectedAlbum}
          submitting={state.submitting}
          error={state.dialogError}
          groups={state.groups}
          onSubmit={state.update}
          onClose={state.closeEditDialog}
        />
      )}
      {state.showPhotoPicker && state.selectedAlbum && (
        <PhotoPickerDialog
          albumId={state.selectedAlbum.id}
          groupId={state.selectedAlbum.group_id}
          searchOptions={state.searchOptions}
          searchOptionsLoading={state.searchOptionsLoading}
          submitting={state.submitting}
          error={state.dialogError}
          onUnauthorized={onUnauthorized}
          onSubmit={state.addPhotos}
          onClose={state.closePhotoPicker}
        />
      )}
    </>
  )
}
