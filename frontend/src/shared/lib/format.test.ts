import { describe, expect, it } from 'vitest'
import { formatBytes, formatDateTime } from './format'

describe('formatDateTime', () => {
  it('always displays UTC timestamps in Asia/Tokyo', () => {
    expect(formatDateTime('2026-07-14T03:00:00Z')).toContain('2026/07/14 12:00')
  })
})

describe('formatBytes', () => {
  it.each([
    [512, '512 B'],
    [1024, '1 KB'],
    [1024 ** 2 * 1.5, '1.5 MB'],
    [1024 ** 3 * 2, '2 GB'],
  ])('formats %i bytes as %s', (value, expected) => {
    expect(formatBytes(value)).toBe(expected)
  })
})
