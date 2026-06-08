import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'


export default defineConfig(async () => {
  return {
    plugins: [      tailwindcss(),
      TanStackRouterVite(),
      react(),
    ].filter(Boolean) as Plugin[],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      // Allow Cayu preview domains and local/IP-based access
      allowedHosts: ['.sandbox.cayu.app', '.cayu.app', '.nip.io', 'localhost'],
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/media': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
      hmr: true,
    },
  }
})
