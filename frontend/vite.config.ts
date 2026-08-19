import { Agent } from 'node:http'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import svgr from 'vite-plugin-svgr'
import { appVersion } from './app-version.js'

const apiAgent = new Agent({ keepAlive: true })

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  server: {
    host: '0.0.0.0',
    port: 15173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18000',
        changeOrigin: true,
        agent: apiAgent,
        headers: {
          connection: 'keep-alive',
        },
      },
    },
  },
})
