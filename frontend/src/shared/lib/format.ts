import i18n from '../../i18n'

const locale = () => (i18n.resolvedLanguage === 'ja' ? 'ja-JP' : 'en-US')

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Tokyo' }).format(
    new Date(value),
  )
}

export function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  const formatter = new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 })
  if (value < 1024 ** 2) return `${formatter.format(value / 1024)} KB`
  if (value < 1024 ** 3) return `${formatter.format(value / 1024 ** 2)} MB`
  return `${formatter.format(value / 1024 ** 3)} GB`
}
