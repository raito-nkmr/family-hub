import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useGroupSelection } from '../../shared/routing/useGroupSelection'
import { useConfirmation } from '../../shared/ui/confirmation'
import { getGroups } from '../groups/api'
import {
  completeCleaningTask,
  createCleaningTask,
  getCleaningTasks,
  updateCleaningTask,
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

export function useCleaning({ onUnauthorized }: UseCleaningOptions) {
  const queryClient = useQueryClient()
  const confirm = useConfirmation()
  const [pendingTaskIds, setPendingTaskIds] = useState<ReadonlySet<string>>(() => new Set())
  const [editingTask, setEditingTask] = useState<CleaningTask | null>(null)
  const [showTaskDialog, setShowTaskDialog] = useState(false)
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const pendingTaskIdsRef = useRef(new Set<string>())

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

  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(tasksQuery.error, onUnauthorized)

  const saveMutation = useMutation({
    mutationFn: async ({ groupId, task, name, intervalDays }: SaveTaskInput) =>
      task
        ? updateCleaningTask(task.id, { name, interval_days: intervalDays })
        : createCleaningTask(groupId, name, intervalDays),
    onSuccess: (saved, { groupId }) => {
      queryClient.setQueryData<CleaningTask[]>(queryKeys.cleaningTasks(groupId), (current = []) =>
        sortTasks([...current.filter((task) => task.id !== saved.id), saved]),
      )
    },
  })

  const selectGroup = async (groupId: string) => {
    setPageMutationError(null)
    await selectGroupInUrl(groupId)
  }

  const saveTask = async (name: string, intervalDays: number) => {
    const groupId = editingTask?.group_id ?? selectedGroupId
    if (!groupId) return
    setDialogError(null)
    try {
      await saveMutation.mutateAsync({ groupId, task: editingTask, name, intervalDays })
      setShowTaskDialog(false)
      setEditingTask(null)
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setDialogError(i18n.t(editingTask ? 'errors.cleaningUpdate' : 'errors.cleaningCreate'))
    }
  }

  const updateTask = async (task: CleaningTask, operation: () => Promise<CleaningTask>, fallback: string) => {
    if (pendingTaskIdsRef.current.has(task.id)) return
    pendingTaskIdsRef.current.add(task.id)
    setPendingTaskIds((current) => new Set(current).add(task.id))
    setPageMutationError(null)
    try {
      const updated = await operation()
      queryClient.setQueryData<CleaningTask[]>(queryKeys.cleaningTasks(task.group_id), (current = []) =>
        sortTasks(current.map((item) => (item.id === updated.id ? updated : item))),
      )
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setPageMutationError(fallback)
    } finally {
      pendingTaskIdsRef.current.delete(task.id)
      setPendingTaskIds((current) => {
        const next = new Set(current)
        next.delete(task.id)
        return next
      })
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
    if (selectedGroupId) await tasksQuery.refetch()
    else await groupsQuery.refetch()
  }

  const openTaskDialog = (task: CleaningTask | null = null) => {
    setEditingTask(task)
    setDialogError(null)
    setShowTaskDialog(true)
  }
  const queryError = groupsQuery.error
    ? i18n.t('errors.cleaningData')
    : tasksQuery.error
      ? i18n.t('errors.cleaningLoad')
      : null

  return {
    groups,
    selectedGroupId,
    selectedGroup: groups.find((group) => group.id === selectedGroupId) ?? null,
    tasks: tasksQuery.data ?? [],
    loading: groupsQuery.isPending || (selectedGroupId !== null && tasksQuery.isPending),
    submitting: saveMutation.isPending,
    pendingTaskIds,
    editingTask,
    showTaskDialog,
    pageError: pageMutationError ?? queryError,
    dialogError,
    selectGroup,
    saveTask,
    complete,
    setTaskActive,
    refresh,
    openTaskDialog,
    closeTaskDialog: () => {
      setShowTaskDialog(false)
      setEditingTask(null)
    },
  }
}

interface SaveTaskInput {
  groupId: string
  task: CleaningTask | null
  name: string
  intervalDays: number
}
