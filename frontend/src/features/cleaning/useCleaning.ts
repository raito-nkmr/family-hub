import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isApiErrorWithStatus, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useGroupSelection } from '../../shared/routing/useGroupSelection'
import { usePendingIds } from '../../shared/lib/usePendingIds'
import { useConfirmation } from '../../shared/ui/confirmation'
import { getGroups } from '../groups/api'
import {
  completeCleaningTask,
  createCleaningCategory,
  createCleaningTask,
  deleteCleaningCategory,
  getCleaningCategories,
  getCleaningTasks,
  updateCleaningCategory,
  updateCleaningTask,
  type CleaningCategory,
  type CleaningTask,
} from './api'

interface UseCleaningOptions {
  onUnauthorized: () => void
}

function sortTasks(tasks: CleaningTask[]): CleaningTask[] {
  return [...tasks].sort(
    (left, right) =>
      Number(right.is_active) - Number(left.is_active) ||
      new Date(left.next_due_at).getTime() - new Date(right.next_due_at).getTime() ||
      left.name.localeCompare(right.name, 'ja'),
  )
}

function sortCategories(categories: CleaningCategory[]): CleaningCategory[] {
  return [...categories].sort(
    (left, right) => left.name.localeCompare(right.name, 'ja') || left.id.localeCompare(right.id),
  )
}

export function useCleaning({ onUnauthorized }: UseCleaningOptions) {
  const queryClient = useQueryClient()
  const confirm = useConfirmation()
  const { pendingIds: pendingTaskIds, start: startTask, finish: finishTask } = usePendingIds()
  const [editingTask, setEditingTask] = useState<CleaningTask | null>(null)
  const [showTaskDialog, setShowTaskDialog] = useState(false)
  const [showCategoryDialog, setShowCategoryDialog] = useState(false)
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const [categoryDialogError, setCategoryDialogError] = useState<string | null>(null)
  const [categoryActionId, setCategoryActionId] = useState<string | null>(null)

  const groupsQuery = useQuery({
    queryKey: queryKeys.groups,
    queryFn: ({ signal }) => getGroups(signal),
  })
  const groups = groupsQuery.data ?? []
  const { selectedGroupId, selectGroup: selectGroupInUrl } = useGroupSelection(groups)
  const tasksQuery = useQuery({
    queryKey: queryKeys.cleaningTasks(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getCleaningTasks(selectedGroupId!, signal),
    select: sortTasks,
    enabled: selectedGroupId !== null,
  })
  const categoriesQuery = useQuery({
    queryKey: queryKeys.cleaningCategories(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getCleaningCategories(selectedGroupId!, signal),
    select: sortCategories,
    enabled: selectedGroupId !== null,
  })

  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(tasksQuery.error, onUnauthorized)
  useUnauthorizedError(categoriesQuery.error, onUnauthorized)

  const saveMutation = useMutation({
    mutationFn: async ({ groupId, task, name, intervalDays, categoryId }: SaveTaskInput) =>
      task
        ? updateCleaningTask(task.id, { name, interval_days: intervalDays, category_id: categoryId })
        : createCleaningTask(groupId, name, intervalDays, categoryId),
    onSuccess: (saved, { groupId }) => {
      queryClient.setQueryData<CleaningTask[]>(queryKeys.cleaningTasks(groupId), (current = []) =>
        sortTasks([...current.filter((task) => task.id !== saved.id), saved]),
      )
    },
  })
  const createCategoryMutation = useMutation({
    mutationFn: ({ groupId, name }: { groupId: string; name: string }) => createCleaningCategory(groupId, name),
    onSuccess: (created, { groupId }) => {
      queryClient.setQueryData<CleaningCategory[]>(queryKeys.cleaningCategories(groupId), (current = []) =>
        sortCategories([...current, created]),
      )
    },
  })
  const updateCategoryMutation = useMutation({
    mutationFn: ({ categoryId, name }: { categoryId: string; name: string }) =>
      updateCleaningCategory(categoryId, name),
    onSuccess: (updated) => {
      queryClient.setQueryData<CleaningCategory[]>(queryKeys.cleaningCategories(updated.group_id), (current = []) =>
        sortCategories(current.map((category) => (category.id === updated.id ? updated : category))),
      )
    },
  })
  const deleteCategoryMutation = useMutation({
    mutationFn: ({ categoryId }: { groupId: string; categoryId: string }) => deleteCleaningCategory(categoryId),
    onSuccess: (_deleted, { groupId, categoryId }) => {
      queryClient.setQueryData<CleaningCategory[]>(queryKeys.cleaningCategories(groupId), (current = []) =>
        current.filter((category) => category.id !== categoryId),
      )
    },
  })

  const selectGroup = async (groupId: string) => {
    setPageMutationError(null)
    await selectGroupInUrl(groupId)
  }

  const saveTask = async (name: string, intervalDays: number, categoryId: string) => {
    const groupId = editingTask?.group_id ?? selectedGroupId
    if (!groupId) return
    setDialogError(null)
    try {
      await saveMutation.mutateAsync({ groupId, task: editingTask, name, intervalDays, categoryId })
      setShowTaskDialog(false)
      setEditingTask(null)
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setDialogError(i18n.t(editingTask ? 'errors.cleaningUpdate' : 'errors.cleaningCreate'))
    }
  }

  const createCategory = async (name: string) => {
    if (!selectedGroupId) return false
    setCategoryDialogError(null)
    setCategoryActionId('create')
    try {
      await createCategoryMutation.mutateAsync({ groupId: selectedGroupId, name })
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else if (isApiErrorWithStatus(error, 409)) setCategoryDialogError(i18n.t('errors.cleaningCategoryDuplicate'))
      else setCategoryDialogError(i18n.t('errors.cleaningCategoryCreate'))
      return false
    } finally {
      setCategoryActionId(null)
    }
  }

  const renameCategory = async (categoryId: string, name: string) => {
    setCategoryDialogError(null)
    setCategoryActionId(categoryId)
    try {
      await updateCategoryMutation.mutateAsync({ categoryId, name })
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else if (isApiErrorWithStatus(error, 409)) setCategoryDialogError(i18n.t('errors.cleaningCategoryDuplicate'))
      else setCategoryDialogError(i18n.t('errors.cleaningCategoryUpdate'))
      return false
    } finally {
      setCategoryActionId(null)
    }
  }

  const removeCategory = async (category: CleaningCategory) => {
    if (!selectedGroupId || !(await confirm(i18n.t('errors.cleaningCategoryDeleteConfirm', { name: category.name })))) {
      return false
    }
    setCategoryDialogError(null)
    setCategoryActionId(category.id)
    try {
      await deleteCategoryMutation.mutateAsync({ groupId: selectedGroupId, categoryId: category.id })
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else if (isApiErrorWithStatus(error, 409)) setCategoryDialogError(i18n.t('errors.cleaningCategoryInUse'))
      else setCategoryDialogError(i18n.t('errors.cleaningCategoryDelete'))
      return false
    } finally {
      setCategoryActionId(null)
    }
  }

  const updateTask = async (task: CleaningTask, operation: () => Promise<CleaningTask>, fallback: string) => {
    if (!startTask(task.id)) return
    setPageMutationError(null)
    try {
      const updated = await operation()
      queryClient.setQueryData<CleaningTask[]>(queryKeys.cleaningTasks(task.group_id), (current = []) =>
        sortTasks(current.map((item) => (item.id === updated.id ? updated : item))),
      )
      await queryClient.invalidateQueries({ queryKey: queryKeys.cleaningReports(task.group_id) })
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setPageMutationError(fallback)
    } finally {
      finishTask(task.id)
    }
  }

  const complete = (task: CleaningTask) =>
    updateTask(task, () => completeCleaningTask(task.id), i18n.t('errors.cleaningComplete'))

  const setTaskActive = async (task: CleaningTask, isActive: boolean) => {
    if (!isActive && !(await confirm(i18n.t('errors.cleaningPauseConfirm', { name: task.name })))) return
    await updateTask(
      task,
      () => updateCleaningTask(task.id, { is_active: isActive }),
      i18n.t(isActive ? 'errors.cleaningResume' : 'errors.cleaningPause'),
    )
  }

  const refresh = async () => {
    setPageMutationError(null)
    if (selectedGroupId) await Promise.all([tasksQuery.refetch(), categoriesQuery.refetch()])
    else await groupsQuery.refetch()
  }

  const openTaskDialog = (task: CleaningTask | null = null) => {
    setEditingTask(task)
    setDialogError(null)
    setShowTaskDialog(true)
  }
  const openCategoryDialog = () => {
    setCategoryDialogError(null)
    setShowCategoryDialog(true)
  }
  const queryError = groupsQuery.error
    ? i18n.t('errors.cleaningData')
    : tasksQuery.error
      ? i18n.t('errors.cleaningLoad')
      : categoriesQuery.error
        ? i18n.t('errors.cleaningCategoriesLoad')
        : null

  return {
    groups,
    selectedGroupId,
    selectedGroup: groups.find((group) => group.id === selectedGroupId) ?? null,
    categories: categoriesQuery.data ?? [],
    tasks: tasksQuery.data ?? [],
    loading: groupsQuery.isPending || (selectedGroupId !== null && (tasksQuery.isPending || categoriesQuery.isPending)),
    submitting:
      saveMutation.isPending ||
      createCategoryMutation.isPending ||
      updateCategoryMutation.isPending ||
      deleteCategoryMutation.isPending,
    pendingTaskIds,
    editingTask,
    showTaskDialog,
    showCategoryDialog,
    pageError: pageMutationError ?? queryError,
    dialogError,
    categoryDialogError,
    categoryActionId,
    selectGroup,
    saveTask,
    complete,
    setTaskActive,
    refresh,
    openTaskDialog,
    createCategory,
    renameCategory,
    removeCategory,
    openCategoryDialog,
    closeTaskDialog: () => {
      setShowTaskDialog(false)
      setEditingTask(null)
    },
    closeCategoryDialog: () => {
      setShowCategoryDialog(false)
      setCategoryDialogError(null)
    },
  }
}

interface SaveTaskInput {
  groupId: string
  task: CleaningTask | null
  name: string
  intervalDays: number
  categoryId: string
}
