export const appPaths = {
  home: '/',
  'photo-activity': '/photos/new',
  photos: '/photos/library',
  albums: '/photos/albums',
  'photo-trash': '/photos/trash',
  chores: '/chores',
  'chores-daily': '/chores/daily',
  'chores-monthly': '/chores/monthly',
  shopping: '/shopping',
  'shopping-list': '/shopping/list',
  'shopping-history': '/shopping/history',
  groups: '/groups',
  invitations: '/invitations',
  account: '/account',
  system: '/system',
} as const

export type AppView = keyof typeof appPaths

export const photoViews: AppView[] = ['photo-activity', 'photos', 'albums', 'photo-trash']
export const choreViews: AppView[] = ['chores', 'chores-daily', 'chores-monthly']
export const shoppingViews: AppView[] = ['shopping', 'shopping-list', 'shopping-history']
export const managementViews: AppView[] = ['groups', 'invitations', 'account', 'system']

export function getAppView(pathname: string): AppView | null {
  const entry = Object.entries(appPaths).find(([, path]) => path === pathname)
  return (entry?.[0] as AppView | undefined) ?? null
}
