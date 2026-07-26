/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

interface NotificationTargetScope {
  getSafeNotificationTarget?: (value: unknown, origin: string) => string
}

function loadTargetResolver() {
  const source = readFileSync(resolve(process.cwd(), 'public/notification-target.js'), 'utf8')
  const scope: NotificationTargetScope = {}
  Function('self', source)(scope)
  if (!scope.getSafeNotificationTarget) throw new Error('Notification target resolver was not registered')
  return scope.getSafeNotificationTarget
}

describe('notification target resolver', () => {
  const origin = 'https://family.example.com'

  it('allows application paths on the current origin', () => {
    expect(loadTargetResolver()('/photos/new', origin)).toBe('https://family.example.com/photos/new')
  })

  it.each(['https://attacker.example/phishing', 'https://user@family.example.com/private', 'https://[invalid'])(
    'falls back to the application root for unsafe target %s',
    (target) => {
      expect(loadTargetResolver()(target, origin)).toBe('https://family.example.com/')
    },
  )
})
