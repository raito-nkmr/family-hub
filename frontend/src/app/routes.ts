export const appPaths = {
  home: '/',
  'photo-activity': '/photos/new',
  photos: '/photos/library',
  albums: '/photos/albums',
  'photo-trash': '/photos/trash',
  cleaning: '/cleaning',
  'cleaning-daily': '/cleaning/daily',
  'cleaning-reports': '/cleaning/reports',
  shopping: '/shopping',
  groups: '/groups',
  invitations: '/invitations',
  account: '/account',
  system: '/system',
} as const

export type AppView = keyof typeof appPaths

export const photoViews: AppView[] = ['photo-activity', 'photos', 'albums', 'photo-trash']
export const cleaningViews: AppView[] = ['cleaning', 'cleaning-daily', 'cleaning-reports']
export const managementViews: AppView[] = ['groups', 'invitations', 'account', 'system']

export function getAppView(pathname: string): AppView | null {
  const entry = Object.entries(appPaths).find(([, path]) => path === pathname)
  return (entry?.[0] as AppView | undefined) ?? null
}
