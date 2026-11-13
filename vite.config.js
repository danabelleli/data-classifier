import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// During local development, requests to /api are forwarded to the Python
// server started with `python3 api/classify.py`. On Vercel, /api is served by
// the Python function directly, so this proxy is not used there.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
