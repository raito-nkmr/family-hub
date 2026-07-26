import { useSearchParams } from 'react-router'

export function useSearchSelection(key: string) {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get(key)
  const select = (id: string | null) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (id) next.set(key, id)
        else next.delete(key)
        return next
      },
      { replace: true },
    )
  }
  return [selectedId, select] as const
}
