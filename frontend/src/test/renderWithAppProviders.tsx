import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import type { PropsWithChildren } from 'react'
import { createAppQueryClient } from '../shared/api/queryClient'

export function createAppWrapper(initialEntry = '/') {
  const queryClient = createAppQueryClient()
  queryClient.setDefaultOptions({
    queries: { ...queryClient.getDefaultOptions().queries, gcTime: Infinity, retry: false },
    mutations: { retry: false },
  })

  return function AppWrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
      </QueryClientProvider>
    )
  }
}
