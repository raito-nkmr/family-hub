/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

interface BadgeCountScope {
  normalizeBadgeCount?: (value: unknown) => number
  nextBadgeCount?: (value: unknown) => number
}

function loadBadgeCountHelpers() {
  const source = readFileSync(resolve(process.cwd(), 'public/badge-count.js'), 'utf8')
  const scope: BadgeCountScope = {}
  Function('self', source)(scope)
  if (!scope.normalizeBadgeCount || !scope.nextBadgeCount) throw new Error('Badge count helpers were not registered')
  return scope as Required<BadgeCountScope>
}

describe('app badge count helpers', () => {
  it.each([
    [undefined, 0],
    ['invalid', 0],
    [-1, 0],
    ['4', 4],
    [1200, 999],
  ])('normalizes %s to %i', (value, expected) => {
    expect(loadBadgeCountHelpers().normalizeBadgeCount(value)).toBe(expected)
  })

  it('increments the stored count and caps the icon badge', () => {
    const { nextBadgeCount } = loadBadgeCountHelpers()
    expect(nextBadgeCount('4')).toBe(5)
    expect(nextBadgeCount(999)).toBe(999)
  })
})
