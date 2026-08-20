import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CheckIcon, FavoriteIcon, ShareIcon, VideoLibraryIcon } from '../../../shared/ui/icons'
import { PhotoBadge } from './PhotoBadge'

describe('PhotoBadge', () => {
  it('shares the same badge base while keeping the variant and position semantic', () => {
    const { container } = render(
      <>
        <PhotoBadge variant="favorite" position="top-left" label="お気に入り" icon={<FavoriteIcon />} />
        <PhotoBadge variant="video" position="top-right" label="動画" icon={<VideoLibraryIcon />}>
          動画
        </PhotoBadge>
        <PhotoBadge variant="shared" position="bottom-right" label="共有" icon={<ShareIcon />}>
          共有
        </PhotoBadge>
      </>,
    )

    const badges = container.querySelectorAll('.photo-badge')

    expect(badges).toHaveLength(3)
    expect(badges[0]).toHaveClass('photo-badge--favorite', 'photo-badge--top-left')
    expect(badges[1]).toHaveClass('photo-badge--video', 'photo-badge--top-right')
    expect(badges[2]).toHaveClass('photo-badge--shared', 'photo-badge--bottom-right')
    expect(container.querySelectorAll('.photo-badge__icon')).toHaveLength(3)
    expect(screen.getByTitle('お気に入り')).toBeInTheDocument()
  })

  it('supports an active selection state with the same badge treatment', () => {
    const { container } = render(
      <PhotoBadge variant="selection" position="bottom-left" label="写真を選択" active icon={<CheckIcon />} />,
    )

    expect(container.querySelector('.photo-badge')).toHaveClass(
      'photo-badge--selection',
      'photo-badge--bottom-left',
      'photo-badge--active',
    )
    expect(container.querySelector('.photo-badge__icon svg')).toBeInTheDocument()
  })
})
