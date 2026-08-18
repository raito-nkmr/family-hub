import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Photo } from '../api'
import { PhotoPreview } from './PhotoPreview'

const photo = {
  id: 'photo/id',
  original_filename: 'photo.jpg',
} as Photo

describe('PhotoPreview', () => {
  it('uses the generated thumbnail by default', () => {
    render(<PhotoPreview photo={photo} />)

    expect(screen.getByRole('img')).toHaveAttribute('src', '/api/v1/photos/photo%2Fid/thumbnail')
  })

  it('uses the original when requested', () => {
    render(<PhotoPreview photo={photo} source="original" />)

    expect(screen.getByRole('img')).toHaveAttribute('src', '/api/v1/photos/photo%2Fid/content')
  })

  it('uses a video player for an original video', () => {
    const { container } = render(
      <PhotoPreview photo={{ ...photo, content_type: 'video/quicktime' }} source="original" />,
    )

    expect(screen.getByLabelText('photo.jpg')).toHaveAttribute('poster', '/api/v1/photos/photo%2Fid/thumbnail')
    expect(container.querySelector('source')).toHaveAttribute('src', '/api/v1/photos/photo%2Fid/content')
  })

  it('shows a placeholder without downloading the original if the derivative is unavailable', () => {
    render(<PhotoPreview photo={photo} />)

    fireEvent.error(screen.getByRole('img'))

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('プレビュー未対応')).toBeInTheDocument()
  })
})
