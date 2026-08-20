import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
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

  it('reports decoded image dimensions', () => {
    const onDisplayDimensions = vi.fn()
    render(<PhotoPreview photo={photo} source="original" onDisplayDimensions={onDisplayDimensions} />)
    const image = screen.getByRole('img')
    Object.defineProperties(image, {
      naturalWidth: { value: 3024 },
      naturalHeight: { value: 4032 },
    })

    fireEvent.load(image)

    expect(onDisplayDimensions).toHaveBeenCalledWith(3024, 4032)
  })

  it('uses a video player for an original video', () => {
    const { container } = render(
      <PhotoPreview photo={{ ...photo, content_type: 'video/quicktime' }} source="original" />,
    )

    expect(screen.getByLabelText('photo.jpg')).toHaveAttribute('poster', '/api/v1/photos/photo%2Fid/thumbnail')
    expect(container.querySelector('source')).toHaveAttribute('src', '/api/v1/photos/photo%2Fid/content')
  })

  it('reports decoded video dimensions', () => {
    const onDisplayDimensions = vi.fn()
    render(
      <PhotoPreview
        photo={{ ...photo, content_type: 'video/quicktime' }}
        source="original"
        onDisplayDimensions={onDisplayDimensions}
      />,
    )
    const video = screen.getByLabelText('photo.jpg')
    Object.defineProperties(video, {
      videoWidth: { value: 1080 },
      videoHeight: { value: 1920 },
    })

    fireEvent.loadedMetadata(video)

    expect(onDisplayDimensions).toHaveBeenCalledWith(1080, 1920)
  })

  it('shows the placeholder when an original video cannot be played', () => {
    render(<PhotoPreview photo={{ ...photo, content_type: 'video/quicktime' }} source="original" />)

    fireEvent.error(screen.getByLabelText('photo.jpg'))

    expect(screen.queryByLabelText('photo.jpg')).not.toBeInTheDocument()
    expect(screen.getByText('プレビュー未対応')).toBeInTheDocument()
  })

  it('shows a placeholder without downloading the original if the derivative is unavailable', () => {
    render(<PhotoPreview photo={photo} />)

    fireEvent.error(screen.getByRole('img'))

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('プレビュー未対応')).toBeInTheDocument()
  })
})
