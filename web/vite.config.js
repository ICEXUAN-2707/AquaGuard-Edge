import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': `http://127.0.0.1:${process.env.AQUAGUARD_PORT || '8000'}`,
      '/api': `http://127.0.0.1:${process.env.AQUAGUARD_C_PORT || process.env.AQUAGUARD_PORT || '8000'}`,
    },
  },
  build: { rollupOptions: { input: { baseline: 'index.html', business: 'c.html' } } },
})
