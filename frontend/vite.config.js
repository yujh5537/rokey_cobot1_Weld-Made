import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
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