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
  completeChoreTask,
  createChoreCategory,
  createChoreTask,
  deleteChoreCategory,
  getChoreCategories,
  getChoreTasks,
  reorderChoreCategories,
  updateChoreCategory,
  updateChoreTask,
  type ChoreCategory,
  type ChoreTask,
} from './api'

interface UseChoresOptions {
  onUnauthorized: () => void
}

function sortTasks(tasks: ChoreTask[]): ChoreTask[] {
  return [...tasks].sort(
    (left, right) =>
      Number(right.is_active) - Number(left.is_active) ||
      new Date(left.next_due_at).getTime() - new Date(right.next_due_at).getTime() ||
      left.name.localeCompare(right.name, 'ja'),
  )
}

function sortCategories(categories: ChoreCategory[]): ChoreCategory[] {
  return [...categories].sort(
    (left, right) =>
      left.sort_order - right.sort_order ||
      left.name.localeCompare(right.name, 'ja') ||
      left.id.localeCompare(right.id),
  )
}

export function useChores({ onUnauthorized }: UseChoresOptions) {
  const queryClient = useQueryClient()
  const confirm = useConfirmation()
  const { pendingIds: pendingTaskIds, start: startTask, finish: finishTask } = usePendingIds()
  const [editingTask, setEditingTask] = useState<ChoreTask | null>(null)
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
    queryKey: queryKeys.choreTasks(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getChoreTasks(selectedGroupId!, signal),
    select: sortTasks,
    enabled: selectedGroupId !== null,
  })
  const categoriesQuery = useQuery({
    queryKey: queryKeys.choreCategories(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getChoreCategories(selectedGroupId!, signal),
    select: sortCategories,
    enabled: selectedGroupId !== null,
  })

  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(tasksQuery.error, onUnauthorized)
  useUnauthorizedError(categoriesQuery.error, onUnauthorized)

  const saveMutation = useMutation({
    mutationFn: async ({ groupId, task, name, intervalDays, categoryId }: SaveTaskInput) =>
      task
        ? updateChoreTask(task.id, { name, interval_days: intervalDays, category_id: categoryId })
        : createChoreTask(groupId, name, intervalDays, categoryId),
    onSuccess: (saved, { groupId }) => {
      queryClient.setQueryData<ChoreTask[]>(queryKeys.choreTasks(groupId), (current = []) =>
        sortTasks([...current.filter((task) => task.id !== saved.id), saved]),
      )
    },
  })
  const createCategoryMutation = useMutation({
    mutationFn: ({ groupId, name }: { groupId: string; name: string }) => createChoreCategory(groupId, name),
    onSuccess: (created, { groupId }) => {
      queryClient.setQueryData<ChoreCategory[]>(queryKeys.choreCategories(groupId), (current = []) =>
        sortCategories([...current, created]),
      )
    },
  })
  const updateCategoryMutation = useMutation({
    mutationFn: ({ categoryId, name }: { categoryId: string; name: string }) => updateChoreCategory(categoryId, name),
    onSuccess: (updated) => {
      queryClient.setQueryData<ChoreCategory[]>(queryKeys.choreCategories(updated.group_id), (current = []) =>
        sortCategories(current.map((category) => (category.id === updated.id ? updated : category))),
      )
    },
  })
  const deleteCategoryMutation = useMutation({
    mutationFn: ({ categoryId }: { groupId: string; categoryId: string }) => deleteChoreCategory(categoryId),
    onSuccess: (_deleted, { groupId, categoryId }) => {
      queryClient.setQueryData<ChoreCategory[]>(queryKeys.choreCategories(groupId), (current = []) =>
        current.filter((category) => category.id !== categoryId),
      )
    },
  })
  const reorderCategoryMutation = useMutation({
    mutationFn: ({ groupId, categoryIds }: { groupId: string; categoryIds: string[] }) =>
      reorderChoreCategories(groupId, categoryIds),
    onSuccess: (ordered, { groupId }) => {
      queryClient.setQueryData<ChoreCategory[]>(queryKeys.choreCategories(groupId), sortCategories(ordered))
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
      else setDialogError(i18n.t(editingTask ? 'errors.choreUpdate' : 'errors.choreCreate'))
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
      else if (isApiErrorWithStatus(error, 409)) setCategoryDialogError(i18n.t('errors.choreCategoryDuplicate'))
      else setCategoryDialogError(i18n.t('errors.choreCategoryCreate'))
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
      else if (isApiErrorWithStatus(error, 409)) setCategoryDialogError(i18n.t('errors.choreCategoryDuplicate'))
      else setCategoryDialogError(i18n.t('errors.choreCategoryUpdate'))
      return false
    } finally {
      setCategoryActionId(null)
    }
  }

  const removeCategory = async (category: ChoreCategory) => {
    if (!selectedGroupId || !(await confirm(i18n.t('errors.choreCategoryDeleteConfirm', { name: category.name })))) {
      return false
    }
    setCategoryDialogError(null)
    setCategoryActionId(category.id)
    try {
      await deleteCategoryMutation.mutateAsync({ groupId: selectedGroupId, categoryId: category.id })
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else if (isApiErrorWithStatus(error, 409)) setCategoryDialogError(i18n.t('errors.choreCategoryInUse'))
      else setCategoryDialogError(i18n.t('errors.choreCategoryDelete'))
      return false
    } finally {
      setCategoryActionId(null)
    }
  }

  const reorderCategories = async (categoryIds: string[]) => {
    if (!selectedGroupId) return false
    setCategoryDialogError(null)
    setCategoryActionId('reorder')
    try {
      await reorderCategoryMutation.mutateAsync({ groupId: selectedGroupId, categoryIds })
      return true
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setCategoryDialogError(i18n.t('errors.choreCategoryReorder'))
      return false
    } finally {
      setCategoryActionId(null)
    }
  }

  const updateTask = async (task: ChoreTask, operation: () => Promise<ChoreTask>, fallback: string) => {
    if (!startTask(task.id)) return
    setPageMutationError(null)
    try {
      const updated = await operation()
      queryClient.setQueryData<ChoreTask[]>(queryKeys.choreTasks(task.group_id), (current = []) =>
        sortTasks(current.map((item) => (item.id === updated.id ? updated : item))),
      )
      await queryClient.invalidateQueries({ queryKey: queryKeys.choreReports(task.group_id) })
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setPageMutationError(fallback)
    } finally {
      finishTask(task.id)
    }
  }

  const complete = (task: ChoreTask) =>
    updateTask(task, () => completeChoreTask(task.id), i18n.t('errors.choreComplete'))

  const setTaskActive = async (task: ChoreTask, isActive: boolean) => {
    if (!isActive && !(await confirm(i18n.t('errors.chorePauseConfirm', { name: task.name })))) return
    await updateTask(
      task,
      () => updateChoreTask(task.id, { is_active: isActive }),
      i18n.t(isActive ? 'errors.choreResume' : 'errors.chorePause'),
    )
  }

  const refresh = async () => {
    setPageMutationError(null)
    if (selectedGroupId) await Promise.all([tasksQuery.refetch(), categoriesQuery.refetch()])
    else await groupsQuery.refetch()
  }

  const openTaskDialog = (task: ChoreTask | null = null) => {
    setEditingTask(task)
    setDialogError(null)
    setShowTaskDialog(true)
  }
  const openCategoryDialog = () => {
    setCategoryDialogError(null)
    setShowCategoryDialog(true)
  }
  const queryError = groupsQuery.error
    ? i18n.t('errors.choreData')
    : tasksQuery.error
      ? i18n.t('errors.choreLoad')
      : categoriesQuery.error
        ? i18n.t('errors.choreCategoriesLoad')
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
      deleteCategoryMutation.isPending ||
      reorderCategoryMutation.isPending,
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
    reorderCategories,
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
  task: ChoreTask | null
  name: string
  intervalDays: number
  categoryId: string
}
