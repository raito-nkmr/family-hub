import { useEffect } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { getPhotoActivity, markPhotoActivitySeen, type PhotoActivity } from './api'

interface PhotoActivityOptions {
  enabled: boolean
  userId: string | null
  active: boolean
  onUnauthorized: () => void
}

export function usePhotoActivity({ enabled, userId, active, onUnauthorized }: PhotoActivityOptions) {
  const queryClient = useQueryClient()
  const queryKey = queryKeys.photoActivity(userId ?? '')
  const activityQuery = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam, signal }) => getPhotoActivity(pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: enabled && Boolean(userId),
  })
  const markSeenMutation = useMutation({
    mutationFn: markPhotoActivitySeen,
    onSuccess: () => {
      queryClient.setQueryData<InfiniteData<PhotoActivity>>(queryKey, (current) =>
        current ? { ...current, pages: current.pages.map((page) => ({ ...page, unseen_count: 0 })) } : current,
      )
    },
  })
  useUnauthorizedError(activityQuery.error, onUnauthorized)
  useUnauthorizedError(markSeenMutation.error, onUnauthorized)

  const pages = activityQuery.data?.pages ?? []
  const items = pages.flatMap((page) => page.items)
  const unseenCount = pages[0]?.unseen_count ?? 0
  const latest = items[0]

  useEffect(() => {
    if (!enabled || !active || !latest || unseenCount === 0 || markSeenMutation.isPending) return
    markSeenMutation.mutate(latest.id)
  }, [active, enabled, latest, markSeenMutation, unseenCount])

  return {
    items,
    unseenCount,
    loading: activityQuery.isPending,
    loadingMore: activityQuery.isFetchingNextPage,
    hasMore: activityQuery.hasNextPage,
    error:
      activityQuery.error && !isUnauthorizedError(activityQuery.error)
        ? i18n.t(activityQuery.isFetchNextPageError ? 'photoActivity.moreFailed' : 'photoActivity.loadFailed')
        : null,
    refresh: async () => {
      await activityQuery.refetch()
    },
    loadMore: async () => {
      if (activityQuery.hasNextPage && !activityQuery.isFetchingNextPage) await activityQuery.fetchNextPage()
    },
  }
}
