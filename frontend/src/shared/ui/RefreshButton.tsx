import { useTranslation } from 'react-i18next'
import { RefreshIcon } from './icons'

interface RefreshButtonProps {
  disabled?: boolean
  onClick: () => unknown
}

export function RefreshButton({ disabled = false, onClick }: RefreshButtonProps) {
  const { t } = useTranslation()

  return (
    <button className="refresh-button" type="button" onClick={() => void onClick()} disabled={disabled}>
      <RefreshIcon />
      <span>{t('common.refresh')}</span>
    </button>
  )
}
