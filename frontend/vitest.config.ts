import { defineConfig } from 'vitest/config'
import svgr from 'vite-plugin-svgr'
import { appVersion } from './app-version.js'

export default defineConfig({
  plugins: [svgr()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: './src/test/setup.ts',
    restoreMocks: true,
  },
})
