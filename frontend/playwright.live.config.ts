import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.FAMILY_HUB_E2E_BASE_URL
const username = process.env.FAMILY_HUB_E2E_USERNAME
const password = process.env.FAMILY_HUB_E2E_PASSWORD

if (!baseURL || !username || !password) {
  throw new Error(
    'FAMILY_HUB_E2E_BASE_URL, FAMILY_HUB_E2E_USERNAME, and FAMILY_HUB_E2E_PASSWORD are required for live E2E tests',
  )
}

export default defineConfig({
  testDir: './e2e',
  testMatch: 'live-backend.spec.ts',
  fullyParallel: false,
  forbidOnly: true,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'iphone-webkit-live',
      use: { ...devices['iPhone 15'] },
    },
  ],
})
