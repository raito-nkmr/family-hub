import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isApiErrorWithStatus, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useSearchSelection } from '../../shared/routing/useSearchSelection'
import { useConfirmation } from '../../shared/ui/confirmation'
import {
  addGroupMember,
  createGroup,
  getGroup,
  getGroupMemberRemovalImpact,
  getGroupMemberCandidates,
  getGroups,
  removeGroupMember,
  renameGroup,
  updateGroupTimezone,
  updateGroupMemberRole,
  type FamilyGroup,
  type GroupDetail,
  type GroupMember,
  type GroupRole,
} from './api'

interface UseGroupsOptions {
  currentUserId: string
  onUnauthorized: () => void
}

export function useGroups({ currentUserId, onUnauthorized }: UseGroupsOptions) {
  const queryClient = useQueryClient()
  const confirm = useConfirmation()
  const [selectedGroupId, setSelectedGroupId] = useSearchSelection('group')
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showAddMemberDialog, setShowAddMemberDialog] = useState(false)
  const [memberActionId, setMemberActionId] = useState<string | null>(null)
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const memberActionInFlightRef = useRef(false)

  const groupsQuery = useQuery({ queryKey: queryKeys.groups, queryFn: ({ signal }) => getGroups(signal) })
  const detailQuery = useQuery({
    queryKey: queryKeys.group(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getGroup(selectedGroupId!, signal),
    enabled: selectedGroupId !== null,
  })
  const candidatesQuery = useQuery({
    queryKey: queryKeys.groupCandidates(selectedGroupId ?? ''),
    queryFn: ({ signal }) => getGroupMemberCandidates(selectedGroupId!, signal),
    enabled: showAddMemberDialog && selectedGroupId !== null,
  })
  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(detailQuery.error, onUnauthorized)
  useUnauthorizedError(candidatesQuery.error, onUnauthorized)

  const createMutation = useMutation({
    mutationFn: createGroup,
    onSuccess: (created) => {
      queryClient.setQueryData<FamilyGroup[]>(queryKeys.groups, (current = []) => [created, ...current])
      queryClient.setQueryData(queryKeys.group(created.id), created)
      setSelectedGroupId(created.id)
      setShowCreateDialog(false)
    },
  })
  const addMemberMutation = useMutation({
    mutationFn: ({ groupId, userId, role }: { groupId: string; userId: string; role: GroupRole }) =>
      addGroupMember(groupId, userId, role),
    onSuccess: (_invitation, { groupId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.groups })
      void queryClient.invalidateQueries({ queryKey: queryKeys.group(groupId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.groupCandidates(groupId) })
    },
  })
  const renameMutation = useMutation({
    mutationFn: ({ groupId, name }: { groupId: string; name: string }) => renameGroup(groupId, name),
    onSuccess: (updated) => updateGroupCaches(queryClient, updated),
  })
  const timezoneMutation = useMutation({
    mutationFn: ({ groupId, timezone }: { groupId: string; timezone: string }) =>
      updateGroupTimezone(groupId, timezone),
    onSuccess: (updated) => {
      updateGroupCaches(queryClient, updated)
      void queryClient.invalidateQueries({ queryKey: queryKeys.choreReports(updated.id) })
    },
  })

  const create = async (name: string) => {
    setDialogError(null)
    try {
      await createMutation.mutateAsync(name)
    } catch (error) {
      if (isApiErrorWithStatus(error, 409)) setDialogError(i18n.t('errors.groupAlreadyExists'))
      else handleGroupError(error, i18n.t('errors.groupCreate'), onUnauthorized, setDialogError)
    }
  }

  const addMember = async (userId: string, role: GroupRole) => {
    if (!selectedGroupId) return
    setDialogError(null)
    try {
      await addMemberMutation.mutateAsync({ groupId: selectedGroupId, userId, role })
      setShowAddMemberDialog(false)
    } catch (error) {
      if (isApiErrorWithStatus(error, 409)) setDialogError(i18n.t('errors.groupAlreadyMember'))
      else if (isApiErrorWithStatus(error, 404)) setDialogError(i18n.t('errors.groupUserNotFound'))
      else handleGroupError(error, i18n.t('errors.groupAdd'), onUnauthorized, setDialogError)
    }
  }

  const changeRole = async (member: GroupMember, role: GroupRole) => {
    if (!selectedGroupId || member.role === role || memberActionInFlightRef.current) return
    memberActionInFlightRef.current = true
    const groupId = selectedGroupId
    setMemberActionId(member.user_id)
    setPageMutationError(null)
    try {
      await updateGroupMemberRole(groupId, member.user_id, role)
      const updated = await getGroup(groupId)
      updateGroupCaches(queryClient, updated)
    } catch (error) {
      if (isApiErrorWithStatus(error, 409)) setPageMutationError(i18n.t('errors.groupAdminRequired'))
      else handleGroupError(error, i18n.t('errors.groupRole'), onUnauthorized, setPageMutationError)
    } finally {
      memberActionInFlightRef.current = false
      setMemberActionId(null)
    }
  }

  const removeMember = async (member: GroupMember) => {
    const selectedGroup = detailQuery.data
    if (!selectedGroup || memberActionInFlightRef.current) return
    let impact
    try {
      impact = await getGroupMemberRemovalImpact(selectedGroup.id, member.user_id)
    } catch (error) {
      handleGroupError(error, i18n.t('errors.groupDetail'), onUnauthorized, setPageMutationError)
      return
    }
    const impactSummary = [
      impact.shared_photo_count && i18n.t('groups.removalImpact.sharedPhotos', { count: impact.shared_photo_count }),
      impact.created_album_count && i18n.t('groups.removalImpact.albums', { count: impact.created_album_count }),
      impact.created_chore_task_count &&
        i18n.t('groups.removalImpact.choreTasks', { count: impact.created_chore_task_count }),
      impact.created_shopping_item_count &&
        i18n.t('groups.removalImpact.shoppingItems', { count: impact.created_shopping_item_count }),
    ]
      .filter(Boolean)
      .join(', ')
    if (
      !(await confirm(
        `${i18n.t('errors.groupRemoveConfirm', { username: member.username, group: selectedGroup.name })}${
          impactSummary ? `\n${i18n.t('groups.removalImpact.summary', { items: impactSummary })}` : ''
        }`,
      ))
    )
      return
    memberActionInFlightRef.current = true
    const groupId = selectedGroup.id
    setMemberActionId(member.user_id)
    setPageMutationError(null)
    try {
      await removeGroupMember(groupId, member.user_id)
      if (member.user_id === currentUserId) {
        setSelectedGroupId(null)
        queryClient.removeQueries({ queryKey: queryKeys.group(groupId) })
        await groupsQuery.refetch()
      } else {
        updateGroupCaches(queryClient, await getGroup(groupId))
      }
    } catch (error) {
      if (isApiErrorWithStatus(error, 409)) setPageMutationError(i18n.t('errors.groupLastAdmin'))
      else handleGroupError(error, i18n.t('errors.groupRemove'), onUnauthorized, setPageMutationError)
    } finally {
      memberActionInFlightRef.current = false
      setMemberActionId(null)
    }
  }

  const openGroup = async (group: FamilyGroup) => {
    setSelectedGroupId(group.id)
    setPageMutationError(null)
    try {
      await queryClient.fetchQuery({
        queryKey: queryKeys.group(group.id),
        queryFn: ({ signal }) => getGroup(group.id, signal),
      })
    } catch (error) {
      handleGroupError(error, i18n.t('errors.groupDetail'), onUnauthorized, setPageMutationError)
    }
  }

  const rename = async (name: string) => {
    if (!selectedGroupId) return false
    setPageMutationError(null)
    try {
      await renameMutation.mutateAsync({ groupId: selectedGroupId, name })
      return true
    } catch (error) {
      if (isApiErrorWithStatus(error, 409)) setPageMutationError(i18n.t('errors.groupAlreadyExists'))
      else handleGroupError(error, i18n.t('errors.groupRename'), onUnauthorized, setPageMutationError)
      return false
    }
  }

  const updateTimezone = async (timezone: string) => {
    if (!selectedGroupId) return false
    setPageMutationError(null)
    try {
      await timezoneMutation.mutateAsync({ groupId: selectedGroupId, timezone })
      return true
    } catch (error) {
      handleGroupError(error, i18n.t('errors.groupTimezone'), onUnauthorized, setPageMutationError)
      return false
    }
  }

  const refresh = async () => {
    setPageMutationError(null)
    await groupsQuery.refetch()
  }

  const openDialog = (dialog: 'create' | 'member') => {
    setDialogError(null)
    if (dialog === 'create') setShowCreateDialog(true)
    if (dialog === 'member' && selectedGroupId) setShowAddMemberDialog(true)
  }
  const queryError = groupsQuery.error
    ? i18n.t('errors.groupLoad')
    : detailQuery.error
      ? i18n.t('errors.groupDetail')
      : candidatesQuery.error
        ? i18n.t('errors.groupCandidates')
        : null

  return {
    groups: groupsQuery.data ?? [],
    selectedGroup: detailQuery.data ?? null,
    loading: groupsQuery.isPending || (selectedGroupId !== null && detailQuery.isPending),
    submitting:
      createMutation.isPending || addMemberMutation.isPending || renameMutation.isPending || timezoneMutation.isPending,
    showCreateDialog,
    showAddMemberDialog,
    memberCandidates: candidatesQuery.data ?? [],
    loadingMemberCandidates: candidatesQuery.isPending && showAddMemberDialog,
    memberActionId,
    pageError: pageMutationError ?? queryError,
    dialogError,
    create,
    rename,
    updateTimezone,
    addMember,
    changeRole,
    removeMember,
    openGroup,
    refresh,
    backToList: () => setSelectedGroupId(null),
    openDialog,
    closeCreateDialog: () => setShowCreateDialog(false),
    closeAddMemberDialog: () => setShowAddMemberDialog(false),
  }
}

function updateGroupCaches(queryClient: ReturnType<typeof useQueryClient>, updated: GroupDetail) {
  queryClient.setQueryData(queryKeys.group(updated.id), updated)
  queryClient.setQueryData<FamilyGroup[]>(queryKeys.groups, (current = []) =>
    current.map((group) => (group.id === updated.id ? updated : group)),
  )
}

function handleGroupError(
  error: unknown,
  fallback: string,
  onUnauthorized: () => void,
  setError: (message: string) => void,
) {
  if (isUnauthorizedError(error)) onUnauthorized()
  else setError(fallback)
}
