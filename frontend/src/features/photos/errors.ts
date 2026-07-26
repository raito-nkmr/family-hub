import { ApiError } from '../../shared/api/client'
import i18n from '../../i18n'

export function getUploadErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return i18n.t('photoUpload.errorConnection')
  switch (error.status) {
    case 409:
      return i18n.t('photoUpload.errorDuplicate')
    case 413:
      return i18n.t('photoUpload.errorTooLarge')
    case 415:
      return i18n.t('photoUpload.errorUnsupported')
    case 422:
      return i18n.t('photoUpload.errorInvalidBatch')
    case 503:
      return i18n.t('photoUpload.errorStorage')
    case 507:
      return i18n.t('photoUpload.errorCapacity')
    default:
      return i18n.t('photoUpload.errorGeneric')
  }
}
