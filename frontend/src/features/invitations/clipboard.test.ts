import { afterEach, describe, expect, it, vi } from 'vitest'
import { copyTextToClipboard } from './clipboard'

const clipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
const execCommandDescriptor = Object.getOwnPropertyDescriptor(document, 'execCommand')
const fallbackInputs: HTMLInputElement[] = []

function setClipboard(value: Pick<Clipboard, 'writeText'> | undefined) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value })
}

function setExecCommand(value: (commandId: string) => boolean) {
  Object.defineProperty(document, 'execCommand', { configurable: true, value })
}

function createFallbackInput(value: string) {
  const input = document.createElement('input')
  input.value = value
  document.body.append(input)
  fallbackInputs.push(input)
  return input
}

afterEach(() => {
  if (clipboardDescriptor) Object.defineProperty(navigator, 'clipboard', clipboardDescriptor)
  else Reflect.deleteProperty(navigator, 'clipboard')

  if (execCommandDescriptor) Object.defineProperty(document, 'execCommand', execCommandDescriptor)
  else Reflect.deleteProperty(document, 'execCommand')

  fallbackInputs.splice(0).forEach((input) => input.remove())
})

describe('copyTextToClipboard', () => {
  it('uses the Clipboard API when it is available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    const execCommand = vi.fn(() => true)
    setClipboard({ writeText })
    setExecCommand(execCommand)

    const copied = await copyTextToClipboard('invitation-url', createFallbackInput('invitation-url'))

    expect(copied).toBe(true)
    expect(writeText).toHaveBeenCalledWith('invitation-url')
    expect(execCommand).not.toHaveBeenCalled()
  })

  it('selects the visible input and falls back when the Clipboard API is unavailable', async () => {
    const execCommand = vi.fn(() => true)
    setClipboard(undefined)
    setExecCommand(execCommand)
    const input = createFallbackInput('invitation-url')

    const copied = await copyTextToClipboard('invitation-url', input)

    expect(copied).toBe(true)
    expect(document.activeElement).toBe(input)
    expect(input.selectionStart).toBe(0)
    expect(input.selectionEnd).toBe(input.value.length)
    expect(execCommand).toHaveBeenCalledWith('copy')
  })

  it('falls back when the Clipboard API rejects the copy', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('Not allowed'))
    const execCommand = vi.fn(() => true)
    setClipboard({ writeText })
    setExecCommand(execCommand)

    const copied = await copyTextToClipboard('invitation-url', createFallbackInput('invitation-url'))

    expect(copied).toBe(true)
    expect(execCommand).toHaveBeenCalledWith('copy')
  })

  it('reports failure when neither copy method succeeds', async () => {
    setClipboard(undefined)
    setExecCommand(() => false)

    const copied = await copyTextToClipboard('invitation-url', createFallbackInput('invitation-url'))

    expect(copied).toBe(false)
  })
})
