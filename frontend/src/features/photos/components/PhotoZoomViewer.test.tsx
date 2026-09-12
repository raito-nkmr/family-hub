import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PhotoZoomViewer } from './PhotoZoomViewer'

const photo = {
  id: 'photo-1',
  original_filename: 'photo.jpg',
  content_type: 'image/jpeg',
}

function pointerEvent(
  type: 'pointerDown' | 'pointerMove' | 'pointerUp',
  pointerId: number,
  clientX: number,
  clientY: number,
) {
  return { type, pointerId, pointerType: 'touch', clientX, clientY }
}

describe('PhotoZoomViewer', () => {
  it('zooms with a pinch, pans while zoomed, and does not navigate', () => {
    const onPreviousPhoto = vi.fn()
    const onNextPhoto = vi.fn()
    const { container } = render(
      <PhotoZoomViewer photo={photo} onPreviousPhoto={onPreviousPhoto} onNextPhoto={onNextPhoto} />,
    )
    const viewer = container.querySelector('.photo-zoom-viewer')!

    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 1, 100, 100))
    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 2, 200, 100))
    fireEvent.pointerMove(viewer, pointerEvent('pointerMove', 2, 300, 100))

    expect(viewer).toHaveAttribute('data-zoom-scale', '2')

    fireEvent.pointerUp(viewer, pointerEvent('pointerUp', 2, 300, 100))
    fireEvent.pointerMove(viewer, pointerEvent('pointerMove', 1, 130, 100))
    fireEvent.pointerUp(viewer, pointerEvent('pointerUp', 1, 130, 100))

    expect(viewer).toHaveAttribute('data-zoom-scale', '2')
    expect(onPreviousPhoto).not.toHaveBeenCalled()
    expect(onNextPhoto).not.toHaveBeenCalled()
  })

  it('limits pinch zoom to three times and resets at minimum scale', () => {
    const { container } = render(<PhotoZoomViewer photo={photo} />)
    const viewer = container.querySelector('.photo-zoom-viewer')!

    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 1, 100, 100))
    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 2, 200, 100))
    fireEvent.pointerMove(viewer, pointerEvent('pointerMove', 2, 600, 100))
    expect(viewer).toHaveAttribute('data-zoom-scale', '3')

    fireEvent.pointerMove(viewer, pointerEvent('pointerMove', 2, 100, 100))
    expect(viewer).toHaveAttribute('data-zoom-scale', '1')
  })

  it('resets scale when the photo changes', () => {
    const { container, rerender } = render(<PhotoZoomViewer key={photo.id} photo={photo} />)
    const viewer = container.querySelector('.photo-zoom-viewer')!

    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 1, 100, 100))
    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 2, 200, 100))
    fireEvent.pointerMove(viewer, pointerEvent('pointerMove', 2, 300, 100))
    expect(viewer).toHaveAttribute('data-zoom-scale', '2')

    rerender(<PhotoZoomViewer key="photo-2" photo={{ ...photo, id: 'photo-2' }} />)

    expect(container.querySelector('.photo-zoom-viewer')).toHaveAttribute('data-zoom-scale', '1')
  })

  it('navigates only for a horizontal swipe at equal scale', () => {
    const onPreviousPhoto = vi.fn()
    const onNextPhoto = vi.fn()
    const { container } = render(
      <PhotoZoomViewer photo={photo} onPreviousPhoto={onPreviousPhoto} onNextPhoto={onNextPhoto} />,
    )
    const viewer = container.querySelector('.photo-zoom-viewer')!

    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 1, 100, 100))
    fireEvent.pointerUp(viewer, pointerEvent('pointerUp', 1, 180, 105))
    fireEvent.pointerDown(viewer, pointerEvent('pointerDown', 2, 180, 100))
    fireEvent.pointerUp(viewer, pointerEvent('pointerUp', 2, 100, 105))

    expect(onPreviousPhoto).toHaveBeenCalledOnce()
    expect(onNextPhoto).toHaveBeenCalledOnce()
  })
})
