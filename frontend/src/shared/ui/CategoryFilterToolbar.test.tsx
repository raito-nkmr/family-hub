import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { CategoryFilterToolbar } from './CategoryFilterToolbar'

const categories = [
  { id: 'food', name: '食品' },
  { id: 'daily', name: '日用品' },
]

function renderToolbar(overrides: Partial<ComponentProps<typeof CategoryFilterToolbar>> = {}) {
  return render(
    <CategoryFilterToolbar
      categories={categories}
      selectedCategory="all"
      allLabel="すべて"
      ariaLabel="買い物カテゴリー"
      manageLabel="カテゴリー"
      manageDisabled={false}
      onSelectCategory={vi.fn()}
      onManage={vi.fn()}
      {...overrides}
    />,
  )
}

describe('CategoryFilterToolbar', () => {
  it('renders the selected state and optional uncategorized filter', () => {
    renderToolbar({ selectedCategory: 'none', noCategory: { value: 'none', label: 'カテゴリーなし' } })

    expect(screen.getByRole('button', { name: 'すべて' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'カテゴリーなし' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('forwards category and management actions', async () => {
    const user = userEvent.setup()
    const onSelectCategory = vi.fn()
    const onManage = vi.fn()
    renderToolbar({ onSelectCategory, onManage })

    await user.click(screen.getByRole('button', { name: '食品' }))
    await user.click(screen.getByRole('button', { name: 'カテゴリー' }))

    expect(onSelectCategory).toHaveBeenCalledWith('food')
    expect(onManage).toHaveBeenCalledOnce()
  })
})
