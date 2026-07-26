import type {
  AdministrativeAuditEventResponse,
  AdministrativeGroupHealthResponse,
  AdministrativeUserResponse,
  MaintenanceRunResponse,
  SystemRole,
  SystemStatusResponse,
} from '../../shared/api/generated'
import {
  assignGroupAdministratorApiV1AdminGroupsGroupIdAdministratorPatch,
  getSystemStatusApiV1AdminMaintenanceStatusGet,
  listAuditEventsApiV1AdminAuditEventsGet,
  listGroupHealthApiV1AdminGroupsGet,
  listMaintenanceHistoryApiV1AdminMaintenanceHistoryGet,
  listUsersApiV1AdminUsersGet,
  updateUserRoleApiV1AdminUsersUserIdRolePatch,
  updateUserStatusApiV1AdminUsersUserIdStatusPatch,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type SystemStatus = SystemStatusResponse

export function getSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
  return sdkData(getSystemStatusApiV1AdminMaintenanceStatusGet({ signal }))
}

export interface AdministrationSnapshot {
  users: AdministrativeUserResponse[]
  groups: AdministrativeGroupHealthResponse[]
  auditEvents: AdministrativeAuditEventResponse[]
  maintenanceHistory: MaintenanceRunResponse[]
}

export async function getAdministrationSnapshot(signal?: AbortSignal): Promise<AdministrationSnapshot> {
  const [users, groups, auditEvents, maintenanceHistory] = await Promise.all([
    sdkData(listUsersApiV1AdminUsersGet({ signal })),
    sdkData(listGroupHealthApiV1AdminGroupsGet({ signal })),
    sdkData(listAuditEventsApiV1AdminAuditEventsGet({ query: { limit: 100 }, signal })),
    sdkData(listMaintenanceHistoryApiV1AdminMaintenanceHistoryGet({ query: { limit: 100 }, signal })),
  ])
  return {
    users: users.items,
    groups: groups.items,
    auditEvents: auditEvents.items,
    maintenanceHistory: maintenanceHistory.items,
  }
}

export function updateAdministrativeUserStatus(userId: string, isActive: boolean, currentPassword: string) {
  return sdkData(
    updateUserStatusApiV1AdminUsersUserIdStatusPatch({
      path: { user_id: userId },
      body: { is_active: isActive, current_password: currentPassword },
    }),
  )
}

export function updateAdministrativeUserRole(userId: string, systemRole: SystemRole, currentPassword: string) {
  return sdkData(
    updateUserRoleApiV1AdminUsersUserIdRolePatch({
      path: { user_id: userId },
      body: { system_role: systemRole, current_password: currentPassword },
    }),
  )
}

export function assignAdministrativeGroupAdministrator(groupId: string, userId: string, currentPassword: string) {
  return sdkData(
    assignGroupAdministratorApiV1AdminGroupsGroupIdAdministratorPatch({
      path: { group_id: groupId },
      body: { user_id: userId, current_password: currentPassword },
    }),
  )
}
