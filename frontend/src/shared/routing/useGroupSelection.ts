import { useEffect } from 'react'
import { useSearchParams } from 'react-router'

interface GroupIdentity {
  id: string
}

export const LAST_SELECTED_GROUP_STORAGE_KEY = 'family-hub-last-selected-group'

function readLastSelectedGroupId(): string | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(LAST_SELECTED_GROUP_STORAGE_KEY)
  } catch {
    return null
  }
}

function rememberSelectedGroup(groupId: string): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(LAST_SELECTED_GROUP_STORAGE_KEY, groupId)
  } catch {
    // Continue with the URL-only selection when browser storage is unavailable.
  }
}

export function useGroupSelection(groups: GroupIdentity[]) {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedGroupId = searchParams.get('group')
  const lastSelectedGroupId = readLastSelectedGroupId()
  const selectedGroupId = groups.some((group) => group.id === requestedGroupId)
    ? requestedGroupId
    : groups.some((group) => group.id === lastSelectedGroupId)
      ? lastSelectedGroupId
      : (groups[0]?.id ?? null)

  const selectGroup = async (groupId: string) => {
    if (!groups.some((group) => group.id === groupId)) return
    rememberSelectedGroup(groupId)
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
    if (!selectedGroupId) return
    rememberSelectedGroup(selectedGroupId)
    if (requestedGroupId === selectedGroupId) return
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
