import { useState } from 'react'

export type PhotoGridColumns = 2 | 3 | 4

const PHOTO_GRID_COLUMNS_STORAGE_KEY = 'family-hub-photo-grid-columns'

function readPhotoGridColumns(): PhotoGridColumns {
  try {
    const stored = Number(localStorage.getItem(PHOTO_GRID_COLUMNS_STORAGE_KEY))
    return stored === 2 || stored === 4 ? stored : 3
  } catch {
    return 3
  }
}

export function usePhotoGridColumns() {
  const [gridColumns, setGridColumns] = useState<PhotoGridColumns>(readPhotoGridColumns)

  const changeGridColumns = (columns: PhotoGridColumns) => {
    setGridColumns(columns)
    try {
      localStorage.setItem(PHOTO_GRID_COLUMNS_STORAGE_KEY, String(columns))
    } catch {
      // Keep the selection for this page when browser storage is unavailable.
    }
  }

  return { gridColumns, changeGridColumns }
}
