self.normalizeBadgeCount = (value) => {
  const count = Number.parseInt(String(value), 10)
  return Number.isSafeInteger(count) && count > 0 ? Math.min(count, 999) : 0
}

self.nextBadgeCount = (value) => Math.min(self.normalizeBadgeCount(value) + 1, 999)
