export function isReportMonth(value: string | null): value is string {
  return value !== null && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)
}

export function getCurrentMonthForTimezone(timezone: string, now = new Date()): string {
  let parts: Intl.DateTimeFormatPart[]
  try {
    parts = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
    }).formatToParts(now)
  } catch {
    parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Tokyo',
      year: 'numeric',
      month: '2-digit',
    }).formatToParts(now)
  }
  const year = parts.find((part) => part.type === 'year')?.value ?? String(now.getUTCFullYear())
  const month = parts.find((part) => part.type === 'month')?.value ?? String(now.getUTCMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

export function formatReportDateTime(value: string, timezone: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}
