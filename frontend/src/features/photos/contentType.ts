const CONTENT_TYPE_BY_EXTENSION: Record<string, string> = {
  heic: 'image/heic',
  heif: 'image/heif',
  jpeg: 'image/jpeg',
  jpg: 'image/jpeg',
  png: 'image/png',
  m4v: 'video/x-m4v',
  mov: 'video/quicktime',
  mp4: 'video/mp4',
}

const PHOTO_FORMAT_NAMES: Record<string, string> = {
  'image/jpeg': 'JPEG',
  'image/png': 'PNG',
  'image/heif': 'HEIF',
  'image/heic': 'HEIC',
  'video/mp4': 'MP4 video',
  'video/quicktime': 'QuickTime video',
  'video/x-m4v': 'M4V video',
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

export function isVideoContentType(contentType: string | undefined): boolean {
  return contentType?.split(';', 1)[0]?.trim().toLowerCase().startsWith('video/') ?? false
}
