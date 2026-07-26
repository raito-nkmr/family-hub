import { useEffect, useRef } from 'react'
import { isUnauthorizedError } from './errors'

export function useUnauthorizedError(error: unknown, onUnauthorized: () => void) {
  const handledError = useRef<unknown>(null)

  useEffect(() => {
    if (!isUnauthorizedError(error) || handledError.current === error) return
    handledError.current = error
    onUnauthorized()
  }, [error, onUnauthorized])
}
