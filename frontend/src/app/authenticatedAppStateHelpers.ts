import { photoViews, type AppView } from './routes'

export function isAppPhotoView(view: AppView): boolean {
  return view === 'home' || photoViews.includes(view)
}
