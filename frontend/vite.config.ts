import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
  server: {
    proxy: { '/api': loadEnv(mode, '.', 'TALDAU_').TALDAU_API_PROXY || 'http://127.0.0.1:8000' },
  },
}))
