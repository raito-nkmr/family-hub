import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import type { ChoreTask } from '../chores/api'
import type { FamilyGroup } from '../groups/api'
import type { ShoppingItem } from '../shopping/api'
import { HomePage } from './HomePage'

const group: FamilyGroup = {
  id: 'group-id',
  name: '同居家族',
  created_by_user_id: 'user-id',
  created_at: '2026-07-14T00:00:00Z',
  updated_at: '2026-07-14T00:00:00Z',
  current_user_role: 'admin',
  member_count: 2,
  timezone: 'Asia/Tokyo',
}

const task: ChoreTask = {
  id: 'task-id',
  group_id: group.id,
  name: 'お風呂',
  category_id: 'chore-id',
  interval_days: 1,
  is_active: true,
  created_by_user_id: 'user-id',
  created_at: '2026-07-14T00:00:00Z',
  updated_at: '2026-07-14T00:00:00Z',
  next_due_at: '2099-07-16T00:00:00Z',
  current_user_role: 'admin',
  last_completion: null,
}

const item: ShoppingItem = {
  id: 'item-id',
  group_id: group.id,
  name: '牛乳',
  created_by_user_id: 'user-id',
  created_at: '2026-07-15T00:00:00Z',
  updated_at: '2026-07-15T00:00:00Z',
  purchased_by_user_id: null,
  purchased_by_username: null,
  purchased_at: null,
}

describe('HomePage', () => {
  it('summarizes chore and shopping and opens their apps', () => {
    render(
      <MemoryRouter>
        <HomePage
          recentPhotos={[]}
          unseenPhotoCount={2}
          groups={[group]}
          choreTasks={[{ group, task }]}
          shoppingItems={[{ group, item }]}
          loading={false}
          error={null}
          onRefresh={vi.fn()}
          onSelectPhoto={vi.fn()}
          showPwaInstallPrompt={true}
          onShowPwaInstallGuide={vi.fn()}
          onDismissPwaInstallPrompt={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('未読の更新 2件')).toBeInTheDocument()
    expect(screen.getByText('お風呂')).toBeInTheDocument()
    expect(screen.getByText('牛乳')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '家事を開く' })).toHaveAttribute('href', '/chores')
    expect(screen.getByRole('link', { name: '買い物リストを開く' })).toHaveAttribute('href', '/shopping')
  })

  it('opens and dismisses the Home Screen guide suggestion', async () => {
    const user = userEvent.setup()
    const onShowPwaInstallGuide = vi.fn()
    const onDismissPwaInstallPrompt = vi.fn()
    render(
      <MemoryRouter>
        <HomePage
          recentPhotos={[]}
          unseenPhotoCount={0}
          groups={[]}
          choreTasks={[]}
          shoppingItems={[]}
          loading={false}
          error={null}
          onRefresh={vi.fn()}
          onSelectPhoto={vi.fn()}
          showPwaInstallPrompt={true}
          onShowPwaInstallGuide={onShowPwaInstallGuide}
          onDismissPwaInstallPrompt={onDismissPwaInstallPrompt}
        />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: '追加方法を見る' }))
    await user.click(screen.getByRole('button', { name: 'アプリ化の案内を閉じる' }))

    expect(onShowPwaInstallGuide).toHaveBeenCalledOnce()
    expect(onDismissPwaInstallPrompt).toHaveBeenCalledOnce()
  })
})
