import { useTranslation } from 'react-i18next'
import type { PhotoGridColumns } from './usePhotoGridColumns'

interface PhotoGridDensityProps {
  columns: PhotoGridColumns
  onChange: (columns: PhotoGridColumns) => void
}

export function PhotoGridDensity({ columns, onChange }: PhotoGridDensityProps) {
  const { t } = useTranslation()

  return (
    <div className="photo-grid-density" aria-label={t('photos.gridColumns')}>
      <span>{t('photos.gridColumns')}</span>
      <div>
        {([2, 3, 4] as const).map((count) => (
          <button
            key={count}
            type="button"
            aria-label={t('photos.setGridColumns', { count })}
            aria-pressed={columns === count}
            onClick={() => onChange(count)}
          >
            {count}
          </button>
        ))}
      </div>
    </div>
  )
}
