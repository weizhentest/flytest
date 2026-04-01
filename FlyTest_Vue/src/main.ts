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
import router from './router'
import { useThemeStore } from './store/themeStore'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ArcoVue)
app.use(ArcoVueIcon)

useThemeStore(pinia).initializeTheme()

app.mount('#app')
