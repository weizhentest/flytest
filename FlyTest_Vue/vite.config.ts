import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'url'

const apiProxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'
const appAutomationProxyTarget = process.env.VITE_APP_AUTOMATION_PROXY_TARGET || 'http://localhost:8010'
const wsProxyTarget = process.env.VITE_WS_PROXY_TARGET || apiProxyTarget.replace(/^http/i, 'ws')

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Monaco workers are intentionally large. We still split the app and vendor
    // graph aggressively so this threshold mainly avoids noise from editor assets.
    chunkSizeWarningLimit: 8000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }

          if (id.includes('monaco-editor') || id.includes('@guolao/vue-monaco-editor')) {
            return 'monaco'
          }

          if (id.includes('@arco-design/web-vue')) {
            return 'arco'
          }

          if (
            id.includes('/vue/') ||
            id.includes('vue-router') ||
            id.includes('pinia') ||
            id.includes('@vueuse/core')
          ) {
            return 'vue-core'
          }

          if (id.includes('axios')) {
            return 'network'
          }

          if (id.includes('marked') || id.includes('dompurify')) {
            return 'content'
          }

          if (id.includes('wired-elements') || id.includes('vuedraggable')) {
            return 'ui-extras'
          }
        },
      },
    },
  },
  server: {
    proxy: {
      '^/api/app-automation(?:/|$)': {
        target: appAutomationProxyTarget,
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api\/app-automation/, ''),
      },
      '^/api(?:/|$)': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '^/media(?:/|$)': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '^/ws(?:/|$)': {
        target: wsProxyTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
