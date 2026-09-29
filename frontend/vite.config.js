import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { env } from 'node:process'

const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'
const wsTarget = apiTarget.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      '/ws': {
        target: wsTarget,
        ws: true,
      },

      '/commands': {
        target: apiTarget,
      },

      '/health': {
        target: apiTarget,
      },
    },
  },
})