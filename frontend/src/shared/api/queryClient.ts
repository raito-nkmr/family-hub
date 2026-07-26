import { QueryClient } from '@tanstack/react-query'
import { isApiErrorWithStatus } from './errors'

export function createAppQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) =>
          ![400, 401, 403, 404].some((status) => isApiErrorWithStatus(error, status)) && failureCount < 1,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export const queryClient = createAppQueryClient()
