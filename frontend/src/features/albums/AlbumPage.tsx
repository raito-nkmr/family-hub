import { useTranslation } from 'react-i18next'
import { EmptyState } from '../../shared/ui/EmptyState'
import { LoadingState } from '../../shared/ui/LoadingState'
import { PageMessage } from '../../shared/ui/PageMessage'
import { RefreshButton } from '../../shared/ui/RefreshButton'
import { AlbumIcon, PlusIcon } from '../../shared/ui/icons'
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
    return <LoadingState as="main" id="top" label={t('albums.loading')} />
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
              <RefreshButton onClick={state.refresh} disabled={state.loading} />
            </div>

            {state.pageError && <PageMessage>{state.pageError}</PageMessage>}

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
              <EmptyState
                className="album-empty-state"
                icon={<AlbumIcon />}
                title={t('albums.emptyTitle')}
                description={t('albums.emptyHelp')}
              />
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
