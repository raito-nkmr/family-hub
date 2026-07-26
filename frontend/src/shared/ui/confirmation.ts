import { createContext, useContext } from 'react'

export interface ConfirmationOptions {
  cancelLabel?: string
  confirmLabel?: string
}

export type Confirm = (message: string, options?: ConfirmationOptions) => Promise<boolean>

export const ConfirmationContext = createContext<Confirm>(async () => false)

export function useConfirmation(): Confirm {
  return useContext(ConfirmationContext)
}
