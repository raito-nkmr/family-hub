import { describe, expect, it } from 'vitest'
import { appPaths, getAppView } from './routes'

describe('app routes', () => {
  it.each(Object.entries(appPaths))('maps %s to its canonical path', (view, path) => {
    expect(getAppView(path)).toBe(view)
  })

  it('does not treat an unknown path as home', () => {
    expect(getAppView('/unknown')).toBeNull()
  })
})
