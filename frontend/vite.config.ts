import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: '/foodflow/',
  server: {
    port: 8088,
    host: '0.0.0.0',
    allowedHosts: ['xn--90ahombde2acc.xn--p1ai', 'контентбот.рф', 'tretyakov-igor.tech'],
  },
  build: {
    sourcemap: true,
  },
})
