import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ArcoVue from '@arco-design/web-vue'
import ArcoVueIcon from '@arco-design/web-vue/es/icon'
import 'wired-elements'
import '@arco-design/web-vue/dist/arco.css'
import './style.css'
import './arco-theme-override.css'
import './assets/wired-elements-custom.css'

import App from './App.vue'
import router, { preloadPrivateRouteComponents } from './router'
import { useThemeStore } from './store/themeStore'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ArcoVue)
app.use(ArcoVueIcon)

useThemeStore(pinia).initializeTheme()

app.mount('#app')

let hasScheduledRoutePreload = false

const scheduleRoutePreload = () => {
  if (hasScheduledRoutePreload || typeof window === 'undefined') {
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
