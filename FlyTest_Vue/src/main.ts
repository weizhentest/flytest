import axios from 'axios'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@arco-design/web-vue/dist/arco.css'
import './style.css'
import './arco-theme-override.css'

import App from './App.vue'
import router, { preloadPrivateRouteComponents } from './router'
import { useAuthStore } from './store/authStore'
import { useThemeStore } from './store/themeStore'

const app = createApp(App)
const pinia = createPinia()

axios.defaults.withCredentials = true

app.use(pinia)
app.use(router)

const bootstrapApp = async () => {
  useThemeStore(pinia).initializeTheme()
  app.mount('#app')
  try {
    await useAuthStore(pinia).bootstrapSession()
  } catch (error) {
    console.error('Failed to bootstrap session:', error)
  }
}

void bootstrapApp()

let hasScheduledRoutePreload = false

const scheduleRoutePreload = () => {
  if (hasScheduledRoutePreload || typeof window === 'undefined') {
    return
  }

  const connection = (navigator as Navigator & {
    connection?: {
      saveData?: boolean
      effectiveType?: string
    }
  }).connection

  if (connection?.saveData || connection?.effectiveType === '2g') {
    return
  }

  hasScheduledRoutePreload = true
  const idleWindow = window as Window & {
    requestIdleCallback?: (callback: IdleRequestCallback) => number
  }

  const runPreload = () => {
    void preloadPrivateRouteComponents()
  }

  if (idleWindow.requestIdleCallback) {
    idleWindow.requestIdleCallback(() => runPreload())
    return
  }

  setTimeout(runPreload, 160)
}

void router.isReady().then(() => {
  if (router.currentRoute.value.meta.requiresAuth) {
    scheduleRoutePreload()
  }
})

router.afterEach(to => {
  if (to.meta.requiresAuth) {
    scheduleRoutePreload()
  }
})
