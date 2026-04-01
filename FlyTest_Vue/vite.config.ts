import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'url'

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
      '^/api(?:/|$)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/media(?:/|$)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/ws(?:/|$)': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
