import type { InvitationCreatedResponse, InvitationListResponse, InvitationResponse } from '../../shared/api/generated'
import {
  createInvitationApiV1AdminInvitationsPost,
  listInvitationsApiV1AdminInvitationsGet,
  removeInvitationHistoryApiV1AdminInvitationsHistoryInvitationIdDelete,
  revokeInvitationApiV1AdminInvitationsInvitationIdDelete,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'
import { acceptInvitation } from '../auth/api'

export type Invitation = InvitationResponse
export type CreatedInvitation = InvitationCreatedResponse

export async function getInvitations(signal?: AbortSignal): Promise<Invitation[]> {
  const response: InvitationListResponse = await sdkData(listInvitationsApiV1AdminInvitationsGet({ signal }))
  return response.items
}

export function createInvitation(username: string, expiresInHours = 24): Promise<CreatedInvitation> {
  return sdkData(createInvitationApiV1AdminInvitationsPost({ body: { username, expires_in_hours: expiresInHours } }))
}

export function revokeInvitation(invitationId: string): Promise<void> {
  return sdkData(revokeInvitationApiV1AdminInvitationsInvitationIdDelete({ path: { invitation_id: invitationId } }))
}

export function removeInvitationHistory(invitationId: string): Promise<void> {
  return sdkData(
    removeInvitationHistoryApiV1AdminInvitationsHistoryInvitationIdDelete({
      path: { invitation_id: invitationId },
    }),
  )
}

export { acceptInvitation }
