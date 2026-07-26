import { useEffect } from 'react'
import { useSearchParams } from 'react-router'

interface GroupIdentity {
  id: string
}

export function useGroupSelection(groups: GroupIdentity[]) {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedGroupId = searchParams.get('group')
  const selectedGroupId = groups.some((group) => group.id === requestedGroupId)
    ? requestedGroupId
    : (groups[0]?.id ?? null)

  const selectGroup = async (groupId: string) => {
    if (!groups.some((group) => group.id === groupId)) return
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('group', groupId)
        return next
      },
      { replace: true },
    )
  }

  useEffect(() => {
    if (!selectedGroupId || requestedGroupId === selectedGroupId) return
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('group', selectedGroupId)
        return next
      },
      { replace: true },
    )
  }, [requestedGroupId, selectedGroupId, setSearchParams])

  return { selectedGroupId, selectGroup }
}
