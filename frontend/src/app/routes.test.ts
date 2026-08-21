import { describe, expect, it } from 'vitest'
import { appPaths, getAppView } from './routes'

describe('app routes', () => {
  it.each(Object.entries(appPaths))('maps %s to its canonical path', (view, path) => {
    expect(getAppView(path)).toBe(view)
  })

  it('does not treat an unknown path as home', () => {
    expect(getAppView('/unknown')).toBeNull()
  })

  it('keeps cleaning navigation active on the report subpage', () => {
    expect(getAppView('/cleaning/reports')).toBe('cleaning-reports')
    expect(getAppView('/cleaning/daily')).toBe('cleaning-daily')
  })
})
