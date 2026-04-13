<template>
  <div class="app-automation-layout">
    <a-tabs v-model:active-key="activeTab" type="card-gutter" lazy-load class="app-tabs">
      <a-tab-pane
        v-for="tab in tabDefinitions"
        :key="tab.key"
        :title="tab.title"
      >
        <component :is="tab.component" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { AppAutomationTab } from '../types'

interface AppAutomationTabDefinition {
  key: AppAutomationTab
  title: string
  component: Component
}

const route = useRoute()
const router = useRouter()

const allowedTabs: AppAutomationTab[] = [
  'overview',
  'devices',
  'packages',
  'elements',
  'scene-builder',
  'test-cases',
  'suites',
  'executions',
  'scheduled-tasks',
  'notifications',
  'reports',
  'settings',
]

const tabDefinitions: AppAutomationTabDefinition[] = [
  {
    key: 'overview',
    title: '概览',
    component: defineAsyncComponent(() => import('./AppAutomationDashboardView.vue')),
  },
  {
    key: 'devices',
    title: '设备管理',
    component: defineAsyncComponent(() => import('./AppAutomationDevicesView.vue')),
  },
  {
    key: 'packages',
    title: '应用包',
    component: defineAsyncComponent(() => import('./AppAutomationPackagesView.vue')),
  },
  {
    key: 'elements',
    title: '元素管理',
    component: defineAsyncComponent(() => import('./AppAutomationElementsView.vue')),
  },
  {
    key: 'scene-builder',
    title: '场景编排',
    component: defineAsyncComponent(() => import('./AppAutomationSceneBuilderView.vue')),
  },
  {
    key: 'test-cases',
    title: '测试用例',
    component: defineAsyncComponent(() => import('./AppAutomationTestCasesView.vue')),
  },
  {
    key: 'suites',
    title: '测试套件',
    component: defineAsyncComponent(() => import('./AppAutomationSuitesView.vue')),
  },
  {
    key: 'executions',
    title: '执行记录',
    component: defineAsyncComponent(() => import('./AppAutomationExecutionsView.vue')),
  },
  {
    key: 'scheduled-tasks',
    title: '定时任务',
    component: defineAsyncComponent(() => import('./AppAutomationScheduledTasksView.vue')),
  },
  {
    key: 'notifications',
    title: '通知日志',
    component: defineAsyncComponent(() => import('./AppAutomationNotificationsView.vue')),
  },
  {
    key: 'reports',
    title: '执行报告',
    component: defineAsyncComponent(() => import('./AppAutomationReportsView.vue')),
  },
  {
    key: 'settings',
    title: '环境设置',
    component: defineAsyncComponent(() => import('./AppAutomationSettingsView.vue')),
  },
]

const normalizeTab = (value: unknown): AppAutomationTab => {
  const tab = String(value || 'overview') as AppAutomationTab
  return allowedTabs.includes(tab) ? tab : 'overview'
}

const activeTab = computed<AppAutomationTab>({
  get: () => normalizeTab(route.query.tab),
  set: value => {
    if (value === normalizeTab(route.query.tab)) {
      return
    }
    void router.replace({
      path: '/app-automation',
      query: {
        ...route.query,
        tab: value,
      },
    })
  },
})
</script>

<style scoped>
.app-automation-layout {
  height: 100%;
  padding: 4px 0 0;
}

.app-tabs {
  height: 100%;
}

:deep(.arco-tabs-content) {
  height: calc(100% - 52px);
  overflow: auto;
}
</style>
