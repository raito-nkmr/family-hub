import { useTranslation } from 'react-i18next'
import { NavLink, useLocation } from 'react-router'
import { appPaths, cleaningViews, getAppView, managementViews, photoViews, type AppView } from '../../app/routes'
import {
  AlbumIcon,
  CleaningIcon,
  DeleteIcon,
  EditIcon,
  FamilyGroupIcon,
  GroupIcon,
  PersonAddIcon,
  PhotoActivityIcon,
  PhotoIcon,
  PhotoLibraryIcon,
  ShoppingCartIcon,
  SaveIcon,
} from './icons'

interface NavigationProps {
  showInvitations: boolean
  photoUnseenCount: number
}

export function AppNavigation({ showInvitations, photoUnseenCount }: NavigationProps) {
  const { t } = useTranslation()
  const activeView = getAppView(useLocation().pathname)
  const itemClass = (view: AppView, extra = '') =>
    `${activeView === view ? 'app-navigation__item app-navigation__item--active' : 'app-navigation__item'} ${extra}`.trim()
  const sectionClass = (views: AppView[], extra = '') =>
    `${activeView && views.includes(activeView) ? 'app-navigation__item app-navigation__item--active' : 'app-navigation__item'} ${extra}`.trim()

  return (
    <nav className="app-navigation" aria-label={t('navigation.label')}>
      <span className="app-navigation__label" lang="en">
        {t('navigation.apps')}
      </span>
      <NavLink className={itemClass('home')} to={appPaths.home}>
        <FamilyGroupIcon />
        {t('navigation.home')}
      </NavLink>
      <NavLink className={sectionClass(photoViews, 'app-navigation__mobile-only')} to={appPaths.photos}>
        <span className="app-navigation__icon">
          <PhotoIcon />
          {photoUnseenCount > 0 && <span className="app-navigation__badge-dot" />}
        </span>
        {t('navigation.photos')}
      </NavLink>
      <span className="app-navigation__section app-navigation__desktop-only">
        <PhotoIcon />
        {t('navigation.photos')}
      </span>
      <NavLink
        className={itemClass('photo-activity', 'app-navigation__desktop-only app-navigation__item--nested')}
        to={appPaths['photo-activity']}
      >
        <PhotoActivityIcon />
        {t('navigation.photoActivity')}
        {photoUnseenCount > 0 && <span className="app-navigation__badge">{photoUnseenCount}</span>}
      </NavLink>
      <NavLink
        className={itemClass('photos', 'app-navigation__desktop-only app-navigation__item--nested')}
        to={appPaths.photos}
      >
        <PhotoLibraryIcon />
        {t('navigation.photoLibrary')}
      </NavLink>
      <NavLink
        className={itemClass('albums', 'app-navigation__desktop-only app-navigation__item--nested')}
        to={appPaths.albums}
      >
        <AlbumIcon />
        {t('navigation.albums')}
      </NavLink>
      <NavLink
        className={itemClass('photo-trash', 'app-navigation__desktop-only app-navigation__item--nested')}
        to={appPaths['photo-trash']}
      >
        <DeleteIcon />
        {t('navigation.photoTrash')}
      </NavLink>
      <NavLink className={sectionClass(cleaningViews)} to={appPaths.cleaning}>
        <CleaningIcon />
        {t('navigation.cleaning')}
      </NavLink>
      <NavLink className={itemClass('shopping')} to={appPaths.shopping}>
        <ShoppingCartIcon />
        {t('navigation.shopping')}
      </NavLink>
      <span className="app-navigation__label app-navigation__label--management" lang="en">
        {t('navigation.management')}
      </span>
      <NavLink className={sectionClass(managementViews, 'app-navigation__mobile-only')} to={appPaths.groups}>
        <GroupIcon />
        {t('navigation.more')}
      </NavLink>
      <NavLink className={itemClass('groups', 'app-navigation__desktop-only')} to={appPaths.groups}>
        <GroupIcon />
        {t('navigation.groups')}
      </NavLink>
      {showInvitations && (
        <NavLink className={itemClass('invitations', 'app-navigation__desktop-only')} to={appPaths.invitations}>
          <PersonAddIcon />
          {t('navigation.invitations')}
        </NavLink>
      )}
      <NavLink className={itemClass('account', 'app-navigation__desktop-only')} to={appPaths.account}>
        <EditIcon />
        {t('navigation.account')}
      </NavLink>
      {showInvitations && (
        <NavLink className={itemClass('system', 'app-navigation__desktop-only')} to={appPaths.system}>
          <SaveIcon />
          {t('navigation.system')}
        </NavLink>
      )}
    </nav>
  )
}

export function SectionNavigation({ showInvitations, photoUnseenCount }: NavigationProps) {
  const { t } = useTranslation()
  const activeView = getAppView(useLocation().pathname)
  const tabs =
    activeView && photoViews.includes(activeView)
      ? [
          {
            view: 'photo-activity' as const,
            label: t('navigation.photoActivity'),
            count: photoUnseenCount,
            icon: <PhotoActivityIcon />,
          },
          { view: 'photos' as const, label: t('navigation.photoLibrary'), count: 0, icon: <PhotoLibraryIcon /> },
          { view: 'albums' as const, label: t('navigation.albums'), count: 0, icon: <AlbumIcon /> },
          { view: 'photo-trash' as const, label: t('navigation.photoTrash'), count: 0, icon: <DeleteIcon /> },
        ]
      : activeView && managementViews.includes(activeView)
        ? [
            { view: 'groups' as const, label: t('navigation.groups'), count: 0, icon: <GroupIcon /> },
            ...(showInvitations
              ? [
                  {
                    view: 'invitations' as const,
                    label: t('navigation.invitations'),
                    count: 0,
                    icon: <PersonAddIcon />,
                  },
                ]
              : []),
            { view: 'account' as const, label: t('navigation.account'), count: 0, icon: <EditIcon /> },
            ...(showInvitations
              ? [{ view: 'system' as const, label: t('navigation.system'), count: 0, icon: <SaveIcon /> }]
              : []),
          ]
        : []
  if (tabs.length === 0) return null
  return (
    <nav className="section-navigation" aria-label={t('navigation.sectionLabel')}>
      {tabs.map((tab) => (
        <NavLink
          className={
            activeView === tab.view
              ? 'section-navigation__item section-navigation__item--active'
              : 'section-navigation__item'
          }
          to={appPaths[tab.view]}
          key={tab.view}
        >
          {tab.icon}
          {tab.label}
          {tab.count > 0 && <span>{tab.count}</span>}
        </NavLink>
      ))}
    </nav>
  )
}
