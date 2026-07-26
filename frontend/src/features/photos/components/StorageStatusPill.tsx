import { useTranslation } from 'react-i18next'
import type { StorageStatus } from '../api'

export function StorageStatusPill({ storage }: { storage: StorageStatus | null }) {
  const { t } = useTranslation()
  const available = storage?.available === true
  return (
    <div className={`status-pill ${available ? 'status-pill--available' : ''}`} role="status">
      <span className="status-pill__dot" />
      <span>{storage ? t(`storage.${storage.status}`) : t('storage.checking')}</span>
    </div>
  )
}
