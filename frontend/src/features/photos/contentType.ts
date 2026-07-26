const CONTENT_TYPE_BY_EXTENSION: Record<string, string> = {
  heic: 'image/heic',
  heif: 'image/heif',
  jpeg: 'image/jpeg',
  jpg: 'image/jpeg',
  png: 'image/png',
}

export function getPhotoContentType(file: File): string {
  const declaredType = file.type.trim().toLowerCase()
  if (declaredType === 'image/jpg') return 'image/jpeg'
  if (declaredType) return declaredType

  const extension = file.name.toLowerCase().match(/\.([^.]+)$/)?.[1]
  return extension ? (CONTENT_TYPE_BY_EXTENSION[extension] ?? '') : ''
}
