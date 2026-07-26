import { ApiError } from '../../shared/api/client'
import i18n from '../../i18n'

export function getAlbumErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback
  if (error.status === 404) return i18n.t('errors.albumNotFound')
  if (error.status === 422) return i18n.t('errors.albumInput')
  return fallback
}
