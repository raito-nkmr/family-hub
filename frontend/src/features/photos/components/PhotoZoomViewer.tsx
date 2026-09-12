import { useCallback, useRef, useState, type PointerEvent } from 'react'
import { PhotoPreview } from './PhotoPreview'

interface ZoomPhoto {
  id: string
  original_filename: string
  content_type?: string
}

interface Point {
  x: number
  y: number
}

interface Size {
  width: number
  height: number
}

type Gesture =
  | { kind: 'swipe'; startPoint: Point }
  | { kind: 'pan'; startPoint: Point; startOffset: Point }
  | { kind: 'pinch'; startScale: number; startOffset: Point; startDistance: number; startMidpoint: Point }

const MIN_SCALE = 1
const MAX_SCALE = 3
const SWIPE_THRESHOLD_PX = 50

function distance(first: Point, second: Point): number {
  return Math.hypot(second.x - first.x, second.y - first.y)
}

function midpoint(first: Point, second: Point): Point {
  return {
    x: (first.x + second.x) / 2,
    y: (first.y + second.y) / 2,
  }
}

export function PhotoZoomViewer({
  photo,
  onPreviousPhoto,
  onNextPhoto,
}: {
  photo: ZoomPhoto
  onPreviousPhoto?: () => void
  onNextPhoto?: () => void
}) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const pointersRef = useRef(new Map<number, Point>())
  const gestureRef = useRef<Gesture | null>(null)
  const naturalSizeRef = useRef<Size | null>(null)
  const scaleRef = useRef(MIN_SCALE)
  const offsetRef = useRef<Point>({ x: 0, y: 0 })
  const [scale, setScale] = useState(MIN_SCALE)
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 })

  const getMaximumScale = useCallback(() => {
    const viewport = viewportRef.current
    const image = naturalSizeRef.current
    if (!viewport || !image || image.width <= 0 || image.height <= 0) return MAX_SCALE
    const fitScale = Math.min(viewport.clientWidth / image.width, viewport.clientHeight / image.height)
    return Math.max(MIN_SCALE, Math.min(MAX_SCALE, 1 / fitScale))
  }, [])

  const clampOffset = useCallback((nextOffset: Point, nextScale: number): Point => {
    const viewport = viewportRef.current
    const image = naturalSizeRef.current
    if (!viewport || !image || image.width <= 0 || image.height <= 0) return { x: 0, y: 0 }
    const fitScale = Math.min(viewport.clientWidth / image.width, viewport.clientHeight / image.height)
    const maxX = Math.max(0, (image.width * fitScale * nextScale - viewport.clientWidth) / 2)
    const maxY = Math.max(0, (image.height * fitScale * nextScale - viewport.clientHeight) / 2)
    return {
      x: Math.max(-maxX, Math.min(maxX, nextOffset.x)),
      y: Math.max(-maxY, Math.min(maxY, nextOffset.y)),
    }
  }, [])

  const updateTransform = useCallback(
    (nextScale: number, nextOffset: Point) => {
      const boundedScale = Math.max(MIN_SCALE, Math.min(getMaximumScale(), nextScale))
      const boundedOffset = boundedScale === MIN_SCALE ? { x: 0, y: 0 } : clampOffset(nextOffset, boundedScale)
      scaleRef.current = boundedScale
      offsetRef.current = boundedOffset
      setScale(boundedScale)
      setOffset(boundedOffset)
    },
    [clampOffset, getMaximumScale],
  )

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== 'touch') return
    const point = { x: event.clientX, y: event.clientY }
    pointersRef.current.set(event.pointerId, point)
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // Synthetic events and browsers that lose a contact may not have a capturable pointer.
    }

    const pointers = [...pointersRef.current.values()]
    if (pointers.length >= 2) {
      gestureRef.current = {
        kind: 'pinch',
        startScale: scaleRef.current,
        startOffset: offsetRef.current,
        startDistance: distance(pointers[0], pointers[1]),
        startMidpoint: midpoint(pointers[0], pointers[1]),
      }
    } else if (scaleRef.current > MIN_SCALE) {
      gestureRef.current = { kind: 'pan', startPoint: point, startOffset: offsetRef.current }
    } else {
      gestureRef.current = { kind: 'swipe', startPoint: point }
    }
  }

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== 'touch') return
    const point = { x: event.clientX, y: event.clientY }
    pointersRef.current.set(event.pointerId, point)
    const pointers = [...pointersRef.current.values()]
    const gesture = gestureRef.current
    if (!gesture) return

    if (gesture.kind === 'pinch' && pointers.length >= 2) {
      const currentMidpoint = midpoint(pointers[0], pointers[1])
      const currentDistance = distance(pointers[0], pointers[1])
      const ratio = gesture.startDistance > 0 ? currentDistance / gesture.startDistance : 1
      updateTransform(gesture.startScale * ratio, {
        x: gesture.startOffset.x + currentMidpoint.x - gesture.startMidpoint.x,
        y: gesture.startOffset.y + currentMidpoint.y - gesture.startMidpoint.y,
      })
      event.preventDefault()
      return
    }

    if (gesture.kind === 'pan' && pointers.length === 1) {
      updateTransform(scaleRef.current, {
        x: gesture.startOffset.x + point.x - gesture.startPoint.x,
        y: gesture.startOffset.y + point.y - gesture.startPoint.y,
      })
      event.preventDefault()
    }
  }

  const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== 'touch') return
    const point = { x: event.clientX, y: event.clientY }
    const gesture = gestureRef.current
    pointersRef.current.delete(event.pointerId)
    try {
      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      }
    } catch {
      // The pointer may already have been released by the browser.
    }

    if (gesture?.kind === 'pinch' && pointersRef.current.size === 1) {
      const remainingPoint = [...pointersRef.current.values()][0]
      gestureRef.current =
        scaleRef.current > MIN_SCALE
          ? { kind: 'pan', startPoint: remainingPoint, startOffset: offsetRef.current }
          : { kind: 'swipe', startPoint: remainingPoint }
      return
    }

    if (pointersRef.current.size > 0 || !gesture || gesture.kind !== 'swipe') return
    const deltaX = point.x - gesture.startPoint.x
    const deltaY = point.y - gesture.startPoint.y
    if (Math.abs(deltaX) < SWIPE_THRESHOLD_PX || Math.abs(deltaX) <= Math.abs(deltaY)) return
    if (deltaX > 0) onPreviousPhoto?.()
    else onNextPhoto?.()
  }

  const handlePointerCancel = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== 'touch') return
    pointersRef.current.delete(event.pointerId)
    gestureRef.current = null
    try {
      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      }
    } catch {
      // The pointer may already have been released by the browser.
    }
  }

  return (
    <div
      ref={viewportRef}
      className={`photo-zoom-viewer${scale > MIN_SCALE ? ' photo-zoom-viewer--zoomed' : ''}`}
      data-zoom-scale={scale}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
    >
      <PhotoPreview
        photo={photo}
        className="modal__image photo-zoom-viewer__image"
        source="preview"
        onDisplayDimensions={(width, height) => {
          naturalSizeRef.current = { width, height }
          updateTransform(scaleRef.current, offsetRef.current)
        }}
        style={{
          transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${scale})`,
        }}
      />
    </div>
  )
}
