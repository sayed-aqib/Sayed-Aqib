import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Fixed, dedicated port so this project no longer collides with other
    // local projects that default to 5173/8000 (e.g. Legal_Risk_Contract_
    // Analysis, which now pins 5173/8001). strictPort fails loudly instead
    // of silently landing on a different port.
    port: 5180,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8010',
    },
  },
})
