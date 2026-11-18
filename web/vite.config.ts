import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const publicPort = Number(process.env.PUBLIC_PORT ?? 8090)

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    hmr: { clientPort: publicPort },
    watch: { usePolling: true, interval: 300 },
  },
})
