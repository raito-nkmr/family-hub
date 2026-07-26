import { describe, expect, it } from 'vitest'
import { getPhotoContentType } from './contentType'

describe('getPhotoContentType', () => {
  it('keeps the standard JPEG content type', () => {
    expect(getPhotoContentType(new File(['photo'], 'IMG_0001.JPEG', { type: 'image/jpeg' }))).toBe('image/jpeg')
  })

  it('normalizes the non-standard image/jpg content type', () => {
    expect(getPhotoContentType(new File(['photo'], 'IMG_0001.JPG', { type: 'image/jpg' }))).toBe('image/jpeg')
  })

  it.each(['IMG_0001.JPG', 'IMG_0001.JPEG'])('infers JPEG from %s when Safari omits the content type', (filename) => {
    expect(getPhotoContentType(new File(['photo'], filename))).toBe('image/jpeg')
  })
})
