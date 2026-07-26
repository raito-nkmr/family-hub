import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import type { AuthUser } from '../features/auth/api'
import { appPaths } from './routes'

interface RequireAdminProps {
  role: AuthUser['system_role']
  children: ReactNode
}

export function RequireAdmin({ role, children }: RequireAdminProps) {
  return role === 'admin' ? children : <Navigate to={appPaths.home} replace />
}
