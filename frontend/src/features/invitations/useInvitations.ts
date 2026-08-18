import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isApiErrorWithStatus, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useConfirmation } from '../../shared/ui/confirmation'
import {
  createInvitation,
  getInvitations,
  removeInvitationHistory,
  revokeInvitation,
  type CreatedInvitation,
  type Invitation,
  type InvitationExpiryHours,
} from './api'

interface UseInvitationsOptions {
  onUnauthorized: () => void
}

export function useInvitations({ onUnauthorized }: UseInvitationsOptions) {
  const queryClient = useQueryClient()
  const confirm = useConfirmation()
  const [createdInvitation, setCreatedInvitation] = useState<CreatedInvitation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const invitationsQuery = useQuery({
    queryKey: queryKeys.invitations,
    queryFn: ({ signal }) => getInvitations(signal),
  })
  const createMutation = useMutation({
    mutationFn: ({ username, expiresInHours }: { username: string; expiresInHours: InvitationExpiryHours }) =>
      createInvitation(username, expiresInHours),
    onSuccess: (created) => {
      const invitation: Invitation = {
        id: created.id,
        username: created.username,
        created_by_username: created.created_by_username,
        created_at: created.created_at,
        expires_at: created.expires_at,
        status: created.status,
      }
      setCreatedInvitation(created)
      queryClient.setQueryData<Invitation[]>(queryKeys.invitations, (current = []) => [
        invitation,
        ...current.filter((item) => item.id !== created.id),
      ])
    },
  })
  const revokeMutation = useMutation({
    mutationFn: revokeInvitation,
    onSuccess: (_, invitationId) => {
      queryClient.setQueryData<Invitation[]>(queryKeys.invitations, (current = []) =>
        current.map((item) => (item.id === invitationId ? { ...item, status: 'revoked' } : item)),
      )
      if (createdInvitation?.id === invitationId) setCreatedInvitation(null)
    },
  })
  const removeMutation = useMutation({
    mutationFn: removeInvitationHistory,
    onSuccess: (_, invitationId) => {
      queryClient.setQueryData<Invitation[]>(queryKeys.invitations, (current = []) =>
        current.filter((item) => item.id !== invitationId),
      )
      if (createdInvitation?.id === invitationId) setCreatedInvitation(null)
    },
  })
  const unauthorizedError = [
    invitationsQuery.error,
    createMutation.error,
    revokeMutation.error,
    removeMutation.error,
  ].find(isUnauthorizedError)
  useUnauthorizedError(unauthorizedError, onUnauthorized)

  const create = async (username: string, expiresInHours: InvitationExpiryHours = 24) => {
    setError(null)
    setCreatedInvitation(null)
    try {
      await createMutation.mutateAsync({ username, expiresInHours })
    } catch (requestError) {
      if (!isUnauthorizedError(requestError)) {
        setError(
          isApiErrorWithStatus(requestError, 409)
            ? i18n.t('errors.invitationReserved')
            : i18n.t('errors.invitationCreate'),
        )
      }
    }
  }

  const revoke = async (invitation: Invitation) => {
    if (!(await confirm(i18n.t('errors.invitationRevokeConfirm', { username: invitation.username })))) return
    setError(null)
    try {
      await revokeMutation.mutateAsync(invitation.id)
    } catch (requestError) {
      if (!isUnauthorizedError(requestError)) setError(i18n.t('errors.invitationRevoke'))
    }
  }

  const remove = async (invitation: Invitation) => {
    const isPending = invitation.status === 'pending'
    const confirmationKey = isPending ? 'errors.invitationCancelConfirm' : 'errors.invitationRemoveConfirm'
    if (
      !(await confirm(i18n.t(confirmationKey, { username: invitation.username }), {
        cancelLabel: i18n.t('invitations.confirmationBack'),
        confirmLabel: i18n.t(isPending ? 'invitations.confirmCancelInvitation' : 'invitations.confirmRemoveHistory'),
      }))
    )
      return
    setError(null)
    try {
      await removeMutation.mutateAsync(invitation.id)
    } catch (requestError) {
      if (!isUnauthorizedError(requestError)) setError(i18n.t('errors.invitationRemove'))
    }
  }

  return {
    invitations: invitationsQuery.data ?? [],
    createdInvitation,
    loading: invitationsQuery.isPending || invitationsQuery.isFetching,
    submitting: createMutation.isPending,
    revokingId: revokeMutation.isPending ? revokeMutation.variables : null,
    removingId: removeMutation.isPending ? removeMutation.variables : null,
    error:
      error ??
      (invitationsQuery.error && !isUnauthorizedError(invitationsQuery.error) ? i18n.t('errors.invitationLoad') : null),
    create,
    revoke,
    remove,
    refresh: async () => {
      setError(null)
      await invitationsQuery.refetch()
    },
    clearCreatedInvitation: () => setCreatedInvitation(null),
  }
}
