self.getSafeNotificationTarget = (value, origin) => {
  const fallback = new URL('/', origin).href
  try {
    const candidate = new URL(typeof value === 'string' ? value : '/', origin)
    if (candidate.origin === origin && !candidate.username && !candidate.password) return candidate.href
  } catch {
    // Keep the safe application root for malformed notification data.
  }
  return fallback
}
