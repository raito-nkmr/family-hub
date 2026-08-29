import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useGroupSelection } from '../../shared/routing/useGroupSelection'
import { usePendingIds } from '../../shared/lib/usePendingIds'
import { getGroups } from '../groups/api'
import {
  createShoppingItem,
  getShoppingItems,
  purchaseShoppingItem,
  restoreShoppingItem,
  type ShoppingItem,
} from './api'

interface UseShoppingOptions {
  onUnauthorized: () => void
}

function sortItems(items: ShoppingItem[]): ShoppingItem[] {
  return [...items].sort((left, right) => {
    if (left.purchased_at === null && right.purchased_at !== null) return -1
    if (left.purchased_at !== null && right.purchased_at === null) return 1
    if (left.purchased_at === null && right.purchased_at === null) {
      return new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
    }
    return new Date(right.purchased_at ?? 0).getTime() - new Date(left.purchased_at ?? 0).getTime()
  })
}

export function useShopping({ onUnauthorized }: UseShoppingOptions) {
  const queryClient = useQueryClient()
  const { pendingIds: pendingItemIds, start: startItem, finish: finishItem } = usePendingIds()
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const groupsQuery = useQuery({
    queryKey: queryKeys.groups,
    queryFn: ({ signal }) => getGroups(signal),
  })
  const groups = groupsQuery.data ?? []
  const { selectedGroupId, selectGroup: selectGroupInUrl } = useGroupSelection(groups)
  const itemsQuery = useQuery({
    queryKey: queryKeys.shoppingItems(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getShoppingItems(selectedGroupId!, signal),
    select: sortItems,
    enabled: selectedGroupId !== null,
  })

  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(itemsQuery.error, onUnauthorized)

  const createMutation = useMutation({
    mutationFn: ({ groupId, itemName }: { groupId: string; itemName: string }) => createShoppingItem(groupId, itemName),
    onSuccess: (created, { groupId }) => {
      queryClient.setQueryData<ShoppingItem[]>(queryKeys.shoppingItems(groupId), (current = []) =>
        sortItems([...current, created]),
      )
    },
  })

  const selectGroup = async (groupId: string) => {
    setPageMutationError(null)
    setFormError(null)
    await selectGroupInUrl(groupId)
  }

  const addItem = async (itemName: string): Promise<boolean> => {
    if (!selectedGroupId) return false
    setFormError(null)
    try {
      await createMutation.mutateAsync({ groupId: selectedGroupId, itemName })
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setFormError(i18n.t('errors.shoppingCreate'))
      return false
    }
  }

  const changePurchaseState = async (item: ShoppingItem, purchased: boolean) => {
    if (!startItem(item.id)) return
    setPageMutationError(null)
    try {
      const updated = purchased ? await purchaseShoppingItem(item.id) : await restoreShoppingItem(item.id)
      queryClient.setQueryData<ShoppingItem[]>(queryKeys.shoppingItems(item.group_id), (current = []) =>
        sortItems(current.map((currentItem) => (currentItem.id === updated.id ? updated : currentItem))),
      )
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setPageMutationError(i18n.t(purchased ? 'errors.shoppingPurchase' : 'errors.shoppingRestore'))
    } finally {
      finishItem(item.id)
    }
  }

  const refresh = async () => {
    setPageMutationError(null)
    if (selectedGroupId) await itemsQuery.refetch()
    else await groupsQuery.refetch()
  }

  const queryError = groupsQuery.error
    ? i18n.t('errors.shoppingData')
    : itemsQuery.error
      ? i18n.t('errors.shoppingLoad')
      : null

  return {
    groups,
    selectedGroupId,
    items: itemsQuery.data ?? [],
    loading: groupsQuery.isPending || (selectedGroupId !== null && itemsQuery.isPending),
    submitting: createMutation.isPending,
    pendingItemIds,
    pageError: pageMutationError ?? queryError,
    formError,
    selectGroup,
    addItem,
    changePurchaseState,
    refresh,
  }
}
