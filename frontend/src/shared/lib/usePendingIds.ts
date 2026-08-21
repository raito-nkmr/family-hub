import { useCallback, useRef, useState } from 'react'

export function usePendingIds() {
  const [pendingIds, setPendingIds] = useState<ReadonlySet<string>>(() => new Set())
  const pendingIdsRef = useRef(new Set<string>())

  const start = useCallback((id: string): boolean => {
    if (pendingIdsRef.current.has(id)) return false
    pendingIdsRef.current.add(id)
    setPendingIds((current) => new Set(current).add(id))
    return true
  }, [])

  const finish = useCallback((id: string) => {
    pendingIdsRef.current.delete(id)
    setPendingIds((current) => {
      const next = new Set(current)
      next.delete(id)
      return next
    })
  }, [])

  return { pendingIds, start, finish }
}
