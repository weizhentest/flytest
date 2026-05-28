import axios from 'axios'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import '@arco-design/web-vue/dist/arco.css'
import './style.css'
import './arco-theme-override.css'

import App from './App.vue'
import router, { preloadPrivateRouteComponents } from './router'
import { useAuthStore } from './store/authStore'
import { useThemeStore } from './store/themeStore'
import { trackUserOperation } from '@/services/userService'

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

const pathLabels: Record<string, string> = {
  '/dashboard': '首页',
  '/personal-center': '个人中心',
  '/projects': '项目管理',
  '/requirements': '需求管理',
  '/testcases': '测试管理 / 测试用例',
  '/testsuites': '测试管理 / 测试套件',
  '/test-bugs': '测试管理 / BUG管理',
  '/test-executions': '测试管理 / 测试报告',
  '/llm-configs': '系统管理 / AI大模型配置',
  '/langgraph-chat': 'AI 对话',
  '/knowledge-management': '知识库管理',
  '/data-factory': '数据工厂 / 工具面板',
  '/api-keys': '系统管理 / API KEY 管理',
  '/remote-mcp-configs': '系统管理 / MCP 配置',
  '/requirements/report': '需求管理 / 评审报告',
  '/ai-diagram': 'AI 图表',
  '/skills': '系统管理 / Skills 管理',
  '/testcase-templates': '模板管理',
  '/users': '系统管理 / 用户管理',
  '/organizations': '系统管理 / 组织管理',
  '/permissions': '系统管理 / 权限管理',
  '/project-deletion-logs': '系统管理 / 项目删除记录',
}

const apiAutomationLabels: Record<string, string> = {
  requests: 'AI接口自动化 / 请求管理',
  'test-cases': 'AI接口自动化 / 测试用例',
  environments: 'AI接口自动化 / 环境配置',
  'execution-records': 'AI接口自动化 / 执行记录',
  'execution-report': 'AI接口自动化 / 测试报告',
}

const appAutomationLabels: Record<string, string> = {
  overview: 'APP自动化 / 概览',
  devices: 'APP自动化 / 设备管理',
  packages: 'APP自动化 / 应用包',
  elements: 'APP自动化 / 元素管理',
  'scene-builder': 'APP自动化 / 场景编排',
  'test-cases': 'APP自动化 / 测试用例',
  suites: 'APP自动化 / 测试套件',
  executions: 'APP自动化 / 执行记录',
  'scheduled-tasks': 'APP自动化 / 定时任务',
  notifications: 'APP自动化 / 通知日志',
  reports: 'APP自动化 / 执行报告',
  settings: 'APP自动化 / 环境设置',
}

const uiAutomationLabels: Record<string, string> = {
  pages: 'UI自动化 / 页面管理',
  'page-steps': 'UI自动化 / 页面步骤',
  testcases: 'UI自动化 / 测试用例',
  'ai-intelligent': 'UI自动化 / AI智能模式',
  'execution-records': 'UI自动化 / 执行记录',
  'batch-records': 'UI自动化 / 批量执行',
  'public-data': 'UI自动化 / 公共数据',
  'env-config': 'UI自动化 / 环境配置',
  actuators: 'UI自动化 / 执行器',
}

const dataFactoryLabels: Record<string, string> = {
  all: '数据工厂 / 工具面板',
  string: '数据工厂 / 字符工具',
  encoding: '数据工厂 / 编码工具',
  random: '数据工厂 / 随机工具',
  encryption: '数据工厂 / 加密工具',
  test_data: '数据工厂 / 测试数据',
  json: '数据工厂 / JSON工具',
  crontab: '数据工厂 / Crontab工具',
}

const getRouteOperationLabel = (to: RouteLocationNormalizedLoaded) => {
  if (to.path.startsWith('/users/') && to.path.endsWith('/operation-logs')) {
    return '系统管理 / 用户操作记录'
  }

  if (to.path.startsWith('/ui-automation/trace')) {
    return 'UI自动化 / 执行记录详情'
  }

  if (to.path.startsWith('/api-automation')) {
    const tab = String(to.query.tab || 'requests')
    return apiAutomationLabels[tab] || 'AI接口自动化'
  }

  if (to.path.startsWith('/app-automation')) {
    const tab = String(to.query.tab || 'overview')
    return appAutomationLabels[tab] || 'APP自动化'
  }

  if (to.path.startsWith('/ui-automation')) {
    const tab = String(to.query.tab || 'pages')
    return uiAutomationLabels[tab] || 'UI自动化'
  }

  if (to.path.startsWith('/data-factory')) {
    const category = String(to.query.category || 'all')
    return dataFactoryLabels[category] || '数据工厂'
  }

  if (to.path.startsWith('/requirements/')) {
    return to.path.endsWith('/report') ? '需求管理 / 专项报告' : '需求管理 / 文档详情'
  }

  return pathLabels[to.path] || String(to.name || to.path)
}

let lastTrackedRoute = ''

const trackRouteVisit = (to: RouteLocationNormalizedLoaded) => {
  if (!to.meta.requiresAuth) {
    return
  }

  const authStore = useAuthStore(pinia)
  if (!authStore.isAuthenticated) {
    return
  }

  const marker = `${authStore.currentUser?.id || 'anonymous'}:${to.fullPath}`
  if (marker === lastTrackedRoute) {
    return
  }
  lastTrackedRoute = marker

  void trackUserOperation({
    action: 'menu',
    label: getRouteOperationLabel(to),
    path: to.fullPath,
    method: 'GET',
    route_name: String(to.name || ''),
  }).catch(() => undefined)
}

void router.isReady().then(() => {
  if (router.currentRoute.value.meta.requiresAuth) {
    scheduleRoutePreload()
  }
  trackRouteVisit(router.currentRoute.value)
})

router.afterEach(to => {
  if (to.meta.requiresAuth) {
    scheduleRoutePreload()
  }
  trackRouteVisit(to)
})
