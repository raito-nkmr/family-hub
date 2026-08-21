import {
  createGroupApiV1GroupsPost,
  decideGroupMembershipInvitationApiV1GroupsMembershipInvitationsInvitationIdDecisionPost,
  getGroupAdministrationOverviewApiV1GroupsGroupIdAdministrationGet,
  getGroupApiV1GroupsGroupIdGet,
  getGroupMemberRemovalImpactApiV1GroupsGroupIdMembersUserIdRemovalImpactGet,
  inviteGroupMemberApiV1GroupsGroupIdMembershipInvitationsPost,
  listGroupAuditEventsApiV1GroupsGroupIdAuditEventsGet,
  listGroupMemberCandidatesApiV1GroupsGroupIdMemberCandidatesGet,
  listGroupsApiV1GroupsGet,
  listMyGroupMembershipInvitationsApiV1GroupsMembershipInvitationsGet,
  removeGroupMemberApiV1GroupsGroupIdMembersUserIdDelete,
  renameGroupApiV1GroupsGroupIdPatch,
  updateGroupSettingsApiV1GroupsGroupIdSettingsPatch,
  updateGroupMemberRoleApiV1GroupsGroupIdMembersUserIdPatch,
  type GroupDetailResponse,
  type GroupMemberCandidateResponse,
  type GroupMemberResponse,
  type GroupMemberRemovalImpactResponse,
  type GroupAdministrationOverviewResponse,
  type GroupAuditEventResponse,
  type GroupMembershipInvitationResponse,
  type GroupResponse,
  type GroupRole as ApiGroupRole,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type GroupRole = ApiGroupRole
export type FamilyGroup = GroupResponse
export type GroupMember = GroupMemberResponse
export type GroupMemberCandidate = GroupMemberCandidateResponse
export type GroupDetail = GroupDetailResponse
export type GroupAdministrationOverview = GroupAdministrationOverviewResponse
export type GroupAuditEvent = GroupAuditEventResponse
export type GroupMembershipInvitation = GroupMembershipInvitationResponse
export type GroupMemberRemovalImpact = GroupMemberRemovalImpactResponse

export async function getGroups(signal?: AbortSignal): Promise<FamilyGroup[]> {
  return (await sdkData(listGroupsApiV1GroupsGet({ signal }))).items
}

export function getGroup(groupId: string, signal?: AbortSignal): Promise<GroupDetail> {
  return sdkData(getGroupApiV1GroupsGroupIdGet({ path: { group_id: groupId }, signal }))
}

export async function getGroupMemberCandidates(groupId: string, signal?: AbortSignal): Promise<GroupMemberCandidate[]> {
  return (
    await sdkData(
      listGroupMemberCandidatesApiV1GroupsGroupIdMemberCandidatesGet({ path: { group_id: groupId }, signal }),
    )
  ).items
}

export function createGroup(name: string): Promise<GroupDetail> {
  return sdkData(createGroupApiV1GroupsPost({ body: { name } }))
}

export function addGroupMember(groupId: string, userId: string, role: GroupRole): Promise<GroupMembershipInvitation> {
  return sdkData(
    inviteGroupMemberApiV1GroupsGroupIdMembershipInvitationsPost({
      path: { group_id: groupId },
      body: { user_id: userId, role },
    }),
  )
}

export function renameGroup(groupId: string, name: string): Promise<GroupDetail> {
  return sdkData(renameGroupApiV1GroupsGroupIdPatch({ path: { group_id: groupId }, body: { name } }))
}

export function updateGroupTimezone(groupId: string, timezone: string): Promise<GroupDetail> {
  return sdkData(
    updateGroupSettingsApiV1GroupsGroupIdSettingsPatch({
      path: { group_id: groupId },
      body: { timezone },
    }),
  )
}

export function getGroupAdministration(groupId: string, signal?: AbortSignal): Promise<GroupAdministrationOverview> {
  return sdkData(
    getGroupAdministrationOverviewApiV1GroupsGroupIdAdministrationGet({ path: { group_id: groupId }, signal }),
  )
}

export async function getGroupAuditEvents(groupId: string, signal?: AbortSignal): Promise<GroupAuditEvent[]> {
  return (await sdkData(listGroupAuditEventsApiV1GroupsGroupIdAuditEventsGet({ path: { group_id: groupId }, signal })))
    .items
}

export function getGroupMemberRemovalImpact(
  groupId: string,
  userId: string,
  signal?: AbortSignal,
): Promise<GroupMemberRemovalImpact> {
  return sdkData(
    getGroupMemberRemovalImpactApiV1GroupsGroupIdMembersUserIdRemovalImpactGet({
      path: { group_id: groupId, user_id: userId },
      signal,
    }),
  )
}

export async function getMyGroupMembershipInvitations(signal?: AbortSignal): Promise<GroupMembershipInvitation[]> {
  return (await sdkData(listMyGroupMembershipInvitationsApiV1GroupsMembershipInvitationsGet({ signal }))).items
}

export function decideGroupMembershipInvitation(invitationId: string, accept: boolean): Promise<void> {
  return sdkData(
    decideGroupMembershipInvitationApiV1GroupsMembershipInvitationsInvitationIdDecisionPost({
      path: { invitation_id: invitationId },
      body: { accept },
    }),
  )
}

export function updateGroupMemberRole(groupId: string, userId: string, role: GroupRole): Promise<GroupDetail> {
  return sdkData(
    updateGroupMemberRoleApiV1GroupsGroupIdMembersUserIdPatch({
      path: { group_id: groupId, user_id: userId },
      body: { role },
    }),
  )
}

export function removeGroupMember(groupId: string, userId: string): Promise<void> {
  return sdkData(
    removeGroupMemberApiV1GroupsGroupIdMembersUserIdDelete({
      path: { group_id: groupId, user_id: userId },
    }),
  )
}
