import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { getChoreTasks, type ChoreTask } from '../chores/api'
import { getGroups, type FamilyGroup } from '../groups/api'
import { getPhotos } from '../photos/api'
import { getShoppingItems, type ShoppingItem } from '../shopping/api'

export interface GroupChoreTask {
  group: FamilyGroup
  task: ChoreTask
}

export interface GroupShoppingItem {
  group: FamilyGroup
  item: ShoppingItem
}

interface UseHomeOptions {
  userId: string | null
  active: boolean
  onUnauthorized: () => void
}

export function useHome({ userId, active, onUnauthorized }: UseHomeOptions) {
  const queryClient = useQueryClient()
  const enabled = Boolean(userId && active)
  const groupsQuery = useQuery({
    queryKey: queryKeys.groups,
    queryFn: ({ signal }) => getGroups(signal),
    enabled,
  })
  const photosQuery = useQuery({
    queryKey: queryKeys.recentPhotos,
    queryFn: ({ signal }) => getPhotos({}, undefined, signal, 4),
    enabled,
  })
  const groups = groupsQuery.data ?? []
  const choreQueries = useQueries({
    queries: groups.map((group) => ({
      queryKey: queryKeys.choreTasks(group.id),
      queryFn: ({ signal }: { signal: AbortSignal }) => getChoreTasks(group.id, signal),
      enabled,
    })),
  })
  const shoppingQueries = useQueries({
    queries: groups.map((group) => ({
      queryKey: queryKeys.shoppingItems(group.id),
      queryFn: ({ signal }: { signal: AbortSignal }) => getShoppingItems(group.id, signal),
      enabled,
    })),
  })
  const unauthorizedCandidate = [
    groupsQuery.error,
    photosQuery.error,
    ...choreQueries.map((query) => query.error),
    ...shoppingQueries.map((query) => query.error),
  ].find(isUnauthorizedError)
  useUnauthorizedError(unauthorizedCandidate, onUnauthorized)

  const allQueries = [groupsQuery, photosQuery, ...choreQueries, ...shoppingQueries]
  const hasError = allQueries.some((query) => query.error && !isUnauthorizedError(query.error))
  return {
    groups,
    recentPhotos: photosQuery.data?.items ?? [],
    choreTasks: groups.flatMap((group, index) =>
      (choreQueries[index]?.data ?? []).filter((task) => task.is_active).map((task) => ({ group, task })),
    ),
    shoppingItems: groups.flatMap((group, index) =>
      (shoppingQueries[index]?.data ?? [])
        .filter((item) => item.purchased_at === null)
        .map((item) => ({ group, item })),
    ),
    loading: enabled && allQueries.some((query) => query.isPending),
    error: hasError ? i18n.t('home.loadFailed') : null,
    refresh: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.groups }),
        queryClient.invalidateQueries({ queryKey: queryKeys.recentPhotos }),
        ...groups.flatMap((group) => [
          queryClient.invalidateQueries({ queryKey: queryKeys.choreTasks(group.id) }),
          queryClient.invalidateQueries({ queryKey: queryKeys.shoppingItems(group.id) }),
        ]),
      ])
    },
  }
}
