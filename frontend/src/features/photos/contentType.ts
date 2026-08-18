const CONTENT_TYPE_BY_EXTENSION: Record<string, string> = {
  heic: 'image/heic',
  heif: 'image/heif',
  jpeg: 'image/jpeg',
  jpg: 'image/jpeg',
  png: 'image/png',
}

const PHOTO_FORMAT_NAMES: Record<string, string> = {
  'image/jpeg': 'JPEG',
  'image/png': 'PNG',
  'image/heif': 'HEIF',
  'image/heic': 'HEIC',
}

export function getPhotoContentType(file: File): string {
  const declaredType = file.type.trim().toLowerCase()
  if (declaredType === 'image/jpg') return 'image/jpeg'
  if (declaredType) return declaredType

  const extension = file.name.toLowerCase().match(/\.([^.]+)$/)?.[1]
  return extension ? (CONTENT_TYPE_BY_EXTENSION[extension] ?? '') : ''
}

export function formatPhotoContentType(contentType: string): string {
  const normalized = contentType.split(';', 1)[0]?.trim().toLowerCase() ?? ''
  return PHOTO_FORMAT_NAMES[normalized] ?? (normalized || 'Unknown')
}
