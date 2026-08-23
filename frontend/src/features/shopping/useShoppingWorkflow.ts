import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isApiErrorWithStatus, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useGroupSelection } from '../../shared/routing/useGroupSelection'
import { usePendingIds } from '../../shared/lib/usePendingIds'
import { useConfirmation } from '../../shared/ui/confirmation'
import { getGroups, getGroup, type FamilyGroup, type GroupDetail } from '../groups/api'
import {
  addUnplannedShoppingPurchase,
  createShoppingCategory,
  createShoppingRequest,
  deleteEmptyShoppingTrip,
  deleteShoppingCategory,
  deleteShoppingRequest,
  discardShoppingTrip,
  getShoppingCategories,
  getShoppingRequests,
  getShoppingStatistics,
  getShoppingTrips,
  purchaseShoppingRequest,
  reorderShoppingCategories,
  reverseShoppingPurchase,
  startShoppingTrip,
  updateShoppingCategory,
  updateShoppingPurchase,
  updateShoppingRequest,
  updateShoppingTrip,
  type ShoppingPurchase,
  type ShoppingRequest,
  type ShoppingTrip,
} from './api'

interface ShoppingWorkflowOptions {
  onUnauthorized: () => void
}

interface ShoppingBaseState {
  groups: FamilyGroup[]
  selectedGroupId: string | null
  selectedGroup: GroupDetail | null
  loadingGroups: boolean
  loadingGroup: boolean
  selectGroup: (groupId: string) => Promise<void>
}

function useShoppingBase({ onUnauthorized }: ShoppingWorkflowOptions): ShoppingBaseState {
  const groupsQuery = useQuery({ queryKey: queryKeys.groups, queryFn: ({ signal }) => getGroups(signal) })
  const groups = groupsQuery.data ?? []
  const { selectedGroupId, selectGroup: selectGroupInUrl } = useGroupSelection(groups)
  const groupQuery = useQuery({
    queryKey: queryKeys.group(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getGroup(selectedGroupId!, signal),
    enabled: selectedGroupId !== null,
  })
  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(groupQuery.error, onUnauthorized)

  return {
    groups,
    selectedGroupId,
    selectedGroup: groupQuery.data ?? null,
    loadingGroups: groupsQuery.isPending,
    loadingGroup: selectedGroupId !== null && groupQuery.isPending,
    selectGroup: selectGroupInUrl,
  }
}

export function useShoppingStore(options: ShoppingWorkflowOptions) {
  const queryClient = useQueryClient()
  const base = useShoppingBase(options)
  const confirm = useConfirmation()
  const { pendingIds, start, finish } = usePendingIds()
  const [lastPurchase, setLastPurchase] = useState<ShoppingPurchase | null>(null)
  const [mutationError, setMutationError] = useState<string | null>(null)
  const requestsQuery = useQuery({
    queryKey: queryKeys.shoppingRequests(base.selectedGroupId ?? ''),
    queryFn: ({ signal }) => getShoppingRequests(base.selectedGroupId!, signal),
    enabled: base.selectedGroupId !== null,
  })
  const tripsQuery = useQuery({
    queryKey: queryKeys.shoppingTrips(base.selectedGroupId ?? ''),
    queryFn: ({ signal }) => getShoppingTrips(base.selectedGroupId!, undefined, signal, 50),
    enabled: base.selectedGroupId !== null,
  })
  useUnauthorizedError(requestsQuery.error, options.onUnauthorized)
  useUnauthorizedError(tripsQuery.error, options.onUnauthorized)

  const purchaseMutation = useMutation({
    mutationFn: ({ item, tripId }: { item: ShoppingRequest; tripId?: string }) =>
      purchaseShoppingRequest(item.id, tripId),
  })
  const startMutation = useMutation({
    mutationFn: (groupId: string) => startShoppingTrip(groupId),
  })
  const endMutation = useMutation({
    mutationFn: (tripId: string) =>
      updateShoppingTrip(tripId, { total_amount_yen: null, finalize: true, delete_if_empty: true }),
  })
  const discardMutation = useMutation({ mutationFn: discardShoppingTrip })
  const reverseMutation = useMutation({
    mutationFn: (purchaseId: string) => reverseShoppingPurchase(purchaseId),
  })
  const activeTrip =
    tripsQuery.data?.items.find((trip) => trip.finalized_at === null && trip.discarded_at === null) ?? null

  const purchase = async (item: ShoppingRequest) => {
    if (!start(item.id)) return
    setMutationError(null)
    try {
      const purchaseRecord = await purchaseMutation.mutateAsync({ item, tripId: activeTrip?.id })
      setLastPurchase(purchaseRecord)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingRequests(item.group_id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingTrips(item.group_id) }),
      ])
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setMutationError(i18n.t('errors.shoppingPurchase'))
    } finally {
      finish(item.id)
    }
  }

  const undo = async () => {
    if (!lastPurchase || reverseMutation.isPending) return
    setMutationError(null)
    try {
      await reverseMutation.mutateAsync(lastPurchase.id)
      setLastPurchase(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingTrips(base.selectedGroupId ?? '') }),
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingRequests(base.selectedGroupId ?? '') }),
      ])
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setMutationError(i18n.t('errors.shoppingRestore'))
    }
  }

  const beginTrip = async () => {
    if (!base.selectedGroupId) return
    setMutationError(null)
    try {
      await startMutation.mutateAsync(base.selectedGroupId)
      await queryClient.invalidateQueries({ queryKey: queryKeys.shoppingTrips(base.selectedGroupId) })
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setMutationError(i18n.t('errors.shoppingTripStart'))
    }
  }

  const endTrip = async () => {
    if (!activeTrip || endMutation.isPending) return false
    if (activeTrip.purchase_count === 0 && !(await confirm(i18n.t('shopping.finishEmptyTripConfirm')))) {
      return false
    }
    setMutationError(null)
    try {
      await endMutation.mutateAsync(activeTrip.id)
      setLastPurchase(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingTrips(activeTrip.group_id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingRequests(activeTrip.group_id) }),
      ])
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setMutationError(i18n.t('errors.shoppingTripEnd'))
      return false
    }
  }

  const discardTrip = async () => {
    if (!activeTrip || discardMutation.isPending) return false
    if (!(await confirm(i18n.t('shopping.discardTripConfirm')))) return false
    setMutationError(null)
    try {
      await discardMutation.mutateAsync(activeTrip.id)
      setLastPurchase(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingTrips(activeTrip.group_id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.shoppingRequests(activeTrip.group_id) }),
      ])
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setMutationError(i18n.t('errors.shoppingTripDiscard'))
      return false
    }
  }

  return {
    ...base,
    items: requestsQuery.data ?? [],
    activeTrip,
    lastPurchase,
    pendingItemIds: pendingIds,
    loading: base.loadingGroups || base.loadingGroup || requestsQuery.isPending || tripsQuery.isPending,
    pageError: mutationError ?? (requestsQuery.error || tripsQuery.error ? i18n.t('errors.shoppingLoad') : null),
    submitting:
      purchaseMutation.isPending ||
      startMutation.isPending ||
      endMutation.isPending ||
      discardMutation.isPending ||
      reverseMutation.isPending,
    purchase,
    undo,
    beginTrip,
    endTrip,
    discardTrip,
    refresh: async () => {
      setMutationError(null)
      await Promise.all([requestsQuery.refetch(), tripsQuery.refetch()])
    },
  }
}

export function useShoppingList(options: ShoppingWorkflowOptions) {
  const queryClient = useQueryClient()
  const base = useShoppingBase(options)
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const [categoryDialogError, setCategoryDialogError] = useState<string | null>(null)
  const [categoryActionId, setCategoryActionId] = useState<string | null>(null)
  const requestsQuery = useQuery({
    queryKey: queryKeys.shoppingRequests(base.selectedGroupId ?? ''),
    queryFn: ({ signal }) => getShoppingRequests(base.selectedGroupId!, signal),
    enabled: base.selectedGroupId !== null,
  })
  const categoriesQuery = useQuery({
    queryKey: queryKeys.shoppingCategories(base.selectedGroupId ?? ''),
    queryFn: ({ signal }) => getShoppingCategories(base.selectedGroupId!, signal),
    enabled: base.selectedGroupId !== null,
  })
  useUnauthorizedError(requestsQuery.error, options.onUnauthorized)
  useUnauthorizedError(categoriesQuery.error, options.onUnauthorized)

  const saveRequestMutation = useMutation({
    mutationFn: ({ item, body }: { item?: ShoppingRequest; body: Parameters<typeof createShoppingRequest>[1] }) =>
      item ? updateShoppingRequest(item.id, body) : createShoppingRequest(base.selectedGroupId!, body),
  })
  const deleteRequestMutation = useMutation({ mutationFn: deleteShoppingRequest })
  const createCategoryMutation = useMutation({
    mutationFn: ({ groupId, name }: { groupId: string; name: string }) => createShoppingCategory(groupId, name),
  })
  const updateCategoryMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => updateShoppingCategory(id, name),
  })
  const deleteCategoryMutation = useMutation({ mutationFn: deleteShoppingCategory })
  const reorderCategoryMutation = useMutation({
    mutationFn: ({ groupId, ids }: { groupId: string; ids: string[] }) => reorderShoppingCategories(groupId, ids),
  })

  const invalidate = async (groupId = base.selectedGroupId) => {
    if (!groupId) return
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.shoppingRequests(groupId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.shoppingCategories(groupId) }),
    ])
  }
  const run = async (operation: () => Promise<unknown>, errorKey: string) => {
    setPageMutationError(null)
    try {
      await operation()
      await invalidate()
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setPageMutationError(i18n.t(errorKey))
      return false
    }
  }

  const runDialogOperation = async (operation: () => Promise<unknown>, errorKey: string) => {
    setDialogError(null)
    try {
      await operation()
      await invalidate()
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setDialogError(i18n.t(errorKey))
      return false
    }
  }

  const runCategoryOperation = async (
    operation: () => Promise<unknown>,
    errorKey: string,
    conflictErrorKey: string,
    actionId: string,
  ) => {
    setCategoryDialogError(null)
    setCategoryActionId(actionId)
    try {
      await operation()
      await invalidate()
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else if (isApiErrorWithStatus(error, 409)) setCategoryDialogError(i18n.t(conflictErrorKey))
      else setCategoryDialogError(i18n.t(errorKey))
      return false
    } finally {
      setCategoryActionId(null)
    }
  }

  const selectGroup = async (groupId: string) => {
    setPageMutationError(null)
    setDialogError(null)
    setCategoryDialogError(null)
    await base.selectGroup(groupId)
  }

  return {
    ...base,
    selectGroup,
    items: requestsQuery.data ?? [],
    categories: categoriesQuery.data ?? [],
    members: base.selectedGroup?.members.filter((member) => member.is_active) ?? [],
    loading: base.loadingGroups || base.loadingGroup || requestsQuery.isPending || categoriesQuery.isPending,
    submitting:
      saveRequestMutation.isPending ||
      deleteRequestMutation.isPending ||
      createCategoryMutation.isPending ||
      updateCategoryMutation.isPending ||
      deleteCategoryMutation.isPending ||
      reorderCategoryMutation.isPending,
    pageError:
      pageMutationError ?? (requestsQuery.error || categoriesQuery.error ? i18n.t('errors.shoppingLoad') : null),
    dialogError,
    categoryDialogError,
    categoryActionId,
    clearDialogError: () => setDialogError(null),
    clearCategoryDialogError: () => setCategoryDialogError(null),
    saveRequest: (item: ShoppingRequest | undefined, body: Parameters<typeof createShoppingRequest>[1]) =>
      runDialogOperation(
        () => saveRequestMutation.mutateAsync({ item, body }),
        item ? 'errors.shoppingUpdate' : 'errors.shoppingCreate',
      ),
    removeRequest: (itemId: string) => run(() => deleteRequestMutation.mutateAsync(itemId), 'errors.shoppingDelete'),
    addCategory: (name: string) =>
      base.selectedGroupId
        ? runCategoryOperation(
            () => createCategoryMutation.mutateAsync({ groupId: base.selectedGroupId!, name }),
            'errors.shoppingCategoryCreate',
            'errors.shoppingCategoryDuplicate',
            'create',
          )
        : Promise.resolve(false),
    renameCategory: (id: string, name: string) =>
      runCategoryOperation(
        () => updateCategoryMutation.mutateAsync({ id, name }),
        'errors.shoppingCategoryUpdate',
        'errors.shoppingCategoryDuplicate',
        id,
      ),
    removeCategory: (id: string) =>
      runCategoryOperation(
        () => deleteCategoryMutation.mutateAsync(id),
        'errors.shoppingCategoryDelete',
        'errors.shoppingCategoryInUse',
        id,
      ),
    reorderCategories: (ids: string[]) =>
      base.selectedGroupId
        ? runCategoryOperation(
            () => reorderCategoryMutation.mutateAsync({ groupId: base.selectedGroupId!, ids }),
            'errors.shoppingCategoryReorder',
            'errors.shoppingCategoryReorder',
            'reorder',
          )
        : Promise.resolve(false),
    refresh: async () => {
      setPageMutationError(null)
      setDialogError(null)
      setCategoryDialogError(null)
      await Promise.all([requestsQuery.refetch(), categoriesQuery.refetch()])
    },
  }
}

function todayInput(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function yearStartInput(): string {
  return `${new Date().getFullYear()}-01-01`
}

export function useShoppingHistory(options: ShoppingWorkflowOptions) {
  const queryClient = useQueryClient()
  const base = useShoppingBase(options)
  const confirm = useConfirmation()
  const [fromDate, setFromDate] = useState(yearStartInput)
  const [toDate, setToDate] = useState(todayInput)
  const [mutationError, setMutationError] = useState<string | null>(null)
  const tripsQuery = useInfiniteQuery({
    queryKey: queryKeys.shoppingTripHistory(base.selectedGroupId ?? ''),
    queryFn: ({ pageParam, signal }) => getShoppingTrips(base.selectedGroupId!, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: base.selectedGroupId !== null,
  })
  const statsQuery = useQuery({
    queryKey: queryKeys.shoppingStatistics(base.selectedGroupId ?? '', fromDate, toDate),
    queryFn: ({ signal }) => getShoppingStatistics(base.selectedGroupId!, fromDate, toDate, signal),
    enabled: base.selectedGroupId !== null,
  })
  const categoriesQuery = useQuery({
    queryKey: queryKeys.shoppingCategories(base.selectedGroupId ?? ''),
    queryFn: ({ signal }) => getShoppingCategories(base.selectedGroupId!, signal),
    enabled: base.selectedGroupId !== null,
  })
  useUnauthorizedError(tripsQuery.error, options.onUnauthorized)
  useUnauthorizedError(statsQuery.error, options.onUnauthorized)
  useUnauthorizedError(categoriesQuery.error, options.onUnauthorized)

  const updateTripMutation = useMutation({
    mutationFn: ({ tripId, amount }: { tripId: string; amount: number | null }) =>
      updateShoppingTrip(tripId, { total_amount_yen: amount, finalize: true }),
  })
  const addPurchaseMutation = useMutation({
    mutationFn: ({ tripId, name, categoryId }: { tripId: string; name: string; categoryId: string | null }) =>
      addUnplannedShoppingPurchase(tripId, { name, category_id: categoryId }),
  })
  const updatePurchaseMutation = useMutation({
    mutationFn: ({
      id,
      categoryId,
      purchaserId,
    }: {
      id: string
      categoryId: string | null
      purchaserId: string | null
    }) => updateShoppingPurchase(id, { category_id: categoryId, purchased_by_user_id: purchaserId }),
  })
  const reversePurchaseMutation = useMutation({ mutationFn: reverseShoppingPurchase })
  const discardTripMutation = useMutation({ mutationFn: discardShoppingTrip })
  const deleteEmptyTripMutation = useMutation({ mutationFn: deleteEmptyShoppingTrip })

  const invalidate = async () => {
    if (!base.selectedGroupId) return
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.shoppingTrips(base.selectedGroupId) }),
      queryClient.invalidateQueries({ queryKey: ['groups', base.selectedGroupId, 'shopping-statistics'] }),
    ])
  }
  const run = async (operation: () => Promise<unknown>, errorKey: string) => {
    setMutationError(null)
    try {
      await operation()
      await invalidate()
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) options.onUnauthorized()
      else setMutationError(i18n.t(errorKey))
      return false
    }
  }

  return {
    ...base,
    trips: tripsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    hasMore: tripsQuery.hasNextPage,
    loading:
      base.loadingGroups ||
      base.loadingGroup ||
      tripsQuery.isPending ||
      categoriesQuery.isPending ||
      statsQuery.isPending,
    loadingMore: tripsQuery.isFetchingNextPage,
    statistics: statsQuery.data ?? null,
    categories: categoriesQuery.data ?? [],
    members: base.selectedGroup?.members.filter((member) => member.is_active) ?? [],
    pageError:
      mutationError ??
      (tripsQuery.error || categoriesQuery.error || statsQuery.error ? i18n.t('errors.shoppingHistoryLoad') : null),
    submitting:
      updateTripMutation.isPending ||
      addPurchaseMutation.isPending ||
      updatePurchaseMutation.isPending ||
      reversePurchaseMutation.isPending ||
      discardTripMutation.isPending ||
      deleteEmptyTripMutation.isPending,
    fromDate,
    toDate,
    setFromDate,
    setToDate,
    saveTripAmount: (tripId: string, amount: number | null) =>
      run(() => updateTripMutation.mutateAsync({ tripId, amount }), 'errors.shoppingTripUpdate'),
    addUnplanned: (tripId: string, name: string, categoryId: string | null) =>
      run(() => addPurchaseMutation.mutateAsync({ tripId, name, categoryId }), 'errors.shoppingUnplannedCreate'),
    updatePurchase: (id: string, categoryId: string | null, purchaserId: string | null) =>
      run(() => updatePurchaseMutation.mutateAsync({ id, categoryId, purchaserId }), 'errors.shoppingPurchaseUpdate'),
    reversePurchase: (id: string) => run(() => reversePurchaseMutation.mutateAsync(id), 'errors.shoppingReverse'),
    discardTrip: async (trip: ShoppingTrip) => {
      if (!(await confirm(i18n.t('shopping.discardTripConfirm')))) return false
      return run(() => discardTripMutation.mutateAsync(trip.id), 'errors.shoppingTripDiscard')
    },
    deleteEmptyTrip: async (trip: ShoppingTrip) => {
      if (!(await confirm(i18n.t('shopping.deleteEmptyTripConfirm')))) return false
      return run(() => deleteEmptyTripMutation.mutateAsync(trip.id), 'errors.shoppingTripDelete')
    },
    loadMore: () => (tripsQuery.hasNextPage ? tripsQuery.fetchNextPage() : Promise.resolve()),
    refresh: async () => {
      setMutationError(null)
      await Promise.all([tripsQuery.refetch(), statsQuery.refetch(), categoriesQuery.refetch()])
    },
  }
}
