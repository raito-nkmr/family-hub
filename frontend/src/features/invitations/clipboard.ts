export async function copyTextToClipboard(text: string, fallbackInput: HTMLInputElement): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fall through to selection-based copying for browsers where the Clipboard API is unavailable or denied.
  }

  fallbackInput.focus()
  fallbackInput.select()
  fallbackInput.setSelectionRange(0, fallbackInput.value.length)

  try {
    return document.execCommand('copy')
  } catch {
    return false
  }
}
