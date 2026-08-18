import { useInfiniteQuery } from '@tanstack/react-query'
import { queryKeys } from '../../shared/api/queryKeys'
import { getPhotos, type PhotoFilters } from './api'

interface UsePhotoListOptions {
  filters: PhotoFilters
  enabled?: boolean
}

export function usePhotoList({ filters, enabled = true }: UsePhotoListOptions) {
  const query = useInfiniteQuery({
    queryKey: queryKeys.photos(filters),
    queryFn: ({ pageParam, signal }) => getPhotos(filters, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled,
  })
  const pages = query.data?.pages ?? []

  return {
    photos: pages.flatMap((page) => page.items),
    totalCount: pages[0]?.total_count ?? 0,
    loading: query.isPending,
    loadingMore: query.isFetchingNextPage,
    hasMore: query.hasNextPage,
    error: query.error,
    loadMoreFailed: query.isFetchNextPageError,
    loadMore: async () => {
      if (query.hasNextPage && !query.isFetchingNextPage) await query.fetchNextPage()
    },
    refresh: async () => {
      await query.refetch()
    },
  }
}
