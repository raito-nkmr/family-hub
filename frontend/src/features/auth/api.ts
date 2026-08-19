import { clearCsrfToken, rememberCsrfToken } from '../../shared/api/client'
import type {
  AuthSessionResponse,
  LoginRequest,
  PasswordChangeRequest,
  UserResponse,
  UserSessionListResponse,
  UserSessionResponse,
} from '../../shared/api/generated'
import {
  acceptInvitationApiV1AuthInvitationsAcceptPost,
  changePasswordApiV1AuthPasswordPut,
  getCurrentSessionApiV1AuthMeGet,
  listSessionsApiV1AuthSessionsGet,
  loginApiV1AuthLoginPost,
  logoutAllApiV1AuthLogoutAllPost,
  logoutApiV1AuthLogoutPost,
  revokeSessionApiV1AuthSessionsSessionIdDelete,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type AuthUser = UserResponse & Pick<AuthSessionResponse, 'must_change_password'>
export type AuthUserSession = UserSessionResponse

function rememberSession(response: AuthSessionResponse): AuthUser {
  rememberCsrfToken(response.csrf_token)
  return { ...response.user, must_change_password: response.must_change_password }
}

export async function getCurrentSession(signal?: AbortSignal): Promise<AuthUser> {
  return rememberSession(await sdkData(getCurrentSessionApiV1AuthMeGet({ signal })))
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const credentials: LoginRequest = { username, password }
  return rememberSession(await sdkData(loginApiV1AuthLoginPost({ body: credentials })))
}

export async function logout(): Promise<void> {
  await sdkData(logoutApiV1AuthLogoutPost())
  clearCsrfToken()
}

export function getSessions(signal?: AbortSignal): Promise<UserSessionListResponse> {
  return sdkData(listSessionsApiV1AuthSessionsGet({ signal }))
}

export function revokeSession(sessionId: string): Promise<void> {
  return sdkData(revokeSessionApiV1AuthSessionsSessionIdDelete({ path: { session_id: sessionId } }))
}

export async function logoutAll(): Promise<void> {
  await sdkData(logoutAllApiV1AuthLogoutAllPost())
  clearCsrfToken()
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const body: PasswordChangeRequest = { current_password: currentPassword, new_password: newPassword }
  await sdkData(changePasswordApiV1AuthPasswordPut({ body }))
  clearCsrfToken()
}

export function acceptInvitation(token: string, password: string): Promise<UserResponse> {
  return sdkData(acceptInvitationApiV1AuthInvitationsAcceptPost({ body: { token, password } }))
}
