import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import type { ShoppingCategory, ShoppingRequest } from './api'
import { ShoppingListPage } from './ShoppingListPage'

const useShoppingList = vi.fn()

vi.mock('./useShoppingWorkflow', () => ({
  useShoppingList: () => useShoppingList(),
}))

const categories: ShoppingCategory[] = [
  {
    id: 'food-category-id',
    group_id: 'group-id',
    name: '食品',
    sort_order: 0,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
  },
  {
    id: 'household-category-id',
    group_id: 'group-id',
    name: '日用品',
    sort_order: 1,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
  },
]

const items: ShoppingRequest[] = [
  {
    id: 'milk-id',
    group_id: 'group-id',
    name: '牛乳',
    assignee_user_id: 'member-id',
    assignee_username: '家族A',
    category_id: 'food-category-id',
    category_name: '食品',
    created_by_user_id: 'user-id',
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
  },
  {
    id: 'soap-id',
    group_id: 'group-id',
    name: '洗剤',
    assignee_user_id: null,
    assignee_username: null,
    category_id: 'household-category-id',
    category_name: '日用品',
    created_by_user_id: 'user-id',
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
  },
  {
    id: 'banana-id',
    group_id: 'group-id',
    name: 'バナナ',
    assignee_user_id: null,
    assignee_username: null,
    category_id: null,
    category_name: null,
    created_by_user_id: 'user-id',
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
  },
]

function renderPage() {
  return render(<ShoppingListPage onUnauthorized={vi.fn()} />, { wrapper: createAppWrapper('/shopping/list') })
}

describe('ShoppingListPage', () => {
  const selectGroup = vi.fn()
  const saveRequest = vi.fn()

  beforeEach(() => {
    selectGroup.mockReset()
    saveRequest.mockReset()
    saveRequest.mockResolvedValue(true)
    useShoppingList.mockReturnValue({
      groups: [
        { id: 'group-id', name: '同居家族' },
        { id: 'other-group-id', name: '別の家族' },
      ],
      selectedGroupId: 'group-id',
      items,
      categories,
      members: [
        {
          is_active: true,
          joined_at: '2026-08-01T00:00:00Z',
          role: 'member',
          user_id: 'member-id',
          username: '家族A',
        },
      ],
      loading: false,
      submitting: false,
      pageError: null,
      dialogError: null,
      categoryDialogError: null,
      categoryActionId: null,
      clearDialogError: vi.fn(),
      clearCategoryDialogError: vi.fn(),
      selectGroup,
      saveRequest,
      removeRequest: vi.fn(),
      addCategory: vi.fn(),
      renameCategory: vi.fn(),
      removeCategory: vi.fn(),
      reorderCategories: vi.fn(),
      refresh: vi.fn(),
    })
  })

  it('keeps category management out of the list until opened', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'カテゴリー' }))

    expect(screen.getByRole('dialog', { name: 'カテゴリー' })).toBeInTheDocument()
  })

  it('opens the add dialog and saves the item fields', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: 'リストに追加' }))
    await user.type(screen.getByLabelText('買うもの'), '  卵  ')
    await user.selectOptions(screen.getByLabelText('担当者'), 'member-id')
    await user.selectOptions(screen.getByLabelText('カテゴリー'), 'food-category-id')
    await user.click(screen.getByRole('button', { name: '保存する' }))

    expect(saveRequest).toHaveBeenCalledWith(undefined, {
      name: '卵',
      assignee_user_id: 'member-id',
      category_id: 'food-category-id',
    })
  })

  it('opens an existing item in the edit dialog', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: '牛乳を編集' }))

    expect(screen.getByRole('dialog', { name: '買うものを編集' })).toBeInTheDocument()
    expect(screen.getByLabelText('買うもの')).toHaveValue('牛乳')
    expect(screen.getByLabelText('担当者')).toHaveValue('member-id')
    expect(screen.getByLabelText('カテゴリー')).toHaveValue('food-category-id')
  })

  it('does not apply unfinished form input when the dialog is canceled', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: 'リストに追加' }))
    await user.type(screen.getByLabelText('買うもの'), '途中入力')
    await user.click(screen.getByRole('button', { name: 'キャンセル' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(saveRequest).not.toHaveBeenCalled()
    expect(screen.queryByRole('heading', { name: '途中入力' })).not.toBeInTheDocument()
  })

  it('filters the flat list by category and uncategorized items', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /^食品$/ }))
    expect(screen.getByRole('heading', { name: '牛乳' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '洗剤' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'バナナ' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^カテゴリーなし$/ }))
    expect(screen.getByRole('heading', { name: 'バナナ' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '牛乳' })).not.toBeInTheDocument()
  })

  it('resets the category filter when switching groups', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /^食品$/ }))
    await user.selectOptions(screen.getByLabelText('家族グループ'), 'other-group-id')

    expect(selectGroup).toHaveBeenCalledWith('other-group-id')
    expect(screen.getByRole('button', { name: /^すべて$/ })).toHaveAttribute('aria-pressed', 'true')
  })
})
