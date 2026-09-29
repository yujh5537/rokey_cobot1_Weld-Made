import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      '/sim-weld': {
        target: 'http://127.0.0.1:8766',
        rewrite: (path) => path.replace(/^\/sim-weld/, ''),
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },

      '/commands': {
        target: 'http://127.0.0.1:8000',
      },

      '/health': {
        target: 'http://127.0.0.1:8000',
      },
    },
  },
})