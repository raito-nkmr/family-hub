import { describe, expect, it } from 'vitest'
import { en } from './en'
import { ja } from './ja'

function translationKeys(value: unknown, prefix = ''): string[] {
  if (typeof value !== 'object' || value === null) return [prefix]
  return Object.entries(value).flatMap(([key, child]) => translationKeys(child, prefix ? `${prefix}.${key}` : key))
}

function normalizedKeys(value: unknown): string[] {
  return [...new Set(translationKeys(value).map((key) => key.replace(/_(one|other)$/, '')))].sort()
}

describe('translation resources', () => {
  it('keeps the English and Japanese key sets synchronized', () => {
    expect(normalizedKeys(ja)).toEqual(normalizedKeys(en))
  })
})
