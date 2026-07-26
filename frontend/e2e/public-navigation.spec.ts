import { expect, test } from '@playwright/test'

test('opens the privacy page directly and changes language on iPhone WebKit', async ({ page }) => {
  await page.goto('/privacy')

  await expect(page.getByRole('heading', { name: 'Privacy', exact: true })).toBeVisible()
  await expect(page).toHaveURL(/\/privacy$/)

  await page.getByRole('button', { name: 'Switch language to JA' }).click()

  await expect(page.getByRole('heading', { name: 'プライバシー', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'プライバシー' })).toHaveAttribute('aria-current', 'page')
})
