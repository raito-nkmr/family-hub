import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { CleaningCategoryManagerDialog } from './CleaningCategoryManagerDialog'
import type { CleaningCategory } from '../api'

const category: CleaningCategory = {
  id: 'category-id',
  group_id: 'group-id',
  name: '2階',
  sort_order: 0,
  created_at: '2026-07-15T00:00:00Z',
  updated_at: '2026-07-15T00:00:00Z',
}
const secondCategory: CleaningCategory = {
  ...category,
  id: 'second-category-id',
  name: '1階',
  sort_order: 1,
}

function renderDialog(overrides: Partial<ComponentProps<typeof CleaningCategoryManagerDialog>> = {}) {
  return render(
    <CleaningCategoryManagerDialog
      categories={[category]}
      submitting={false}
      actionId={null}
      error={null}
      onCreate={vi.fn().mockResolvedValue(true)}
      onRename={vi.fn().mockResolvedValue(true)}
      onDelete={vi.fn().mockResolvedValue(true)}
      onReorder={vi.fn().mockResolvedValue(true)}
      onClose={vi.fn()}
      {...overrides}
    />,
  )
}

describe('CleaningCategoryManagerDialog', () => {
  it('creates a trimmed category', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn().mockResolvedValue(true)
    renderDialog({ onCreate })

    await user.type(screen.getByLabelText('カテゴリー名'), '  1階  ')
    await user.click(screen.getByRole('button', { name: 'カテゴリーを追加' }))

    expect(onCreate).toHaveBeenCalledWith('1階')
  })

  it('renames and deletes a category', async () => {
    const user = userEvent.setup()
    const onRename = vi.fn().mockResolvedValue(true)
    const onDelete = vi.fn().mockResolvedValue(true)
    renderDialog({ onRename, onDelete })

    await user.click(screen.getByRole('button', { name: '2階を編集' }))
    const inputs = screen.getAllByLabelText('カテゴリー名')
    await user.clear(inputs[1])
    await user.type(inputs[1], '1階')
    await user.click(screen.getByRole('button', { name: '保存する' }))
    await user.click(screen.getByRole('button', { name: '2階を削除' }))

    expect(onRename).toHaveBeenCalledWith('category-id', '1階')
    expect(onDelete).toHaveBeenCalledWith(category)
  })

  it('shows an empty state and server error', () => {
    renderDialog({ categories: [], error: '使用中のカテゴリーは削除できません。' })

    expect(screen.getByText('カテゴリーはまだありません。')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('使用中のカテゴリーは削除できません。')
  })

  it('reorders categories with accessible move buttons', async () => {
    const user = userEvent.setup()
    const onReorder = vi.fn().mockResolvedValue(true)
    renderDialog({ categories: [category, secondCategory], onReorder })

    await user.click(screen.getByRole('button', { name: '2階を下へ移動' }))

    expect(onReorder).toHaveBeenCalledWith(['second-category-id', 'category-id'])
  })
})
