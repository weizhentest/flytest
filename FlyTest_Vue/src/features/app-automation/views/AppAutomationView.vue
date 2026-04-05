<template>
  <div class="app-automation-layout">
    <a-tabs v-model:active-key="activeTab" type="card-gutter" lazy-load class="app-tabs">
      <a-tab-pane key="overview" title="概览">
        <AppAutomationDashboardView />
      </a-tab-pane>
      <a-tab-pane key="devices" title="设备管理">
        <AppAutomationDevicesView />
      </a-tab-pane>
      <a-tab-pane key="packages" title="应用包">
        <AppAutomationPackagesView />
      </a-tab-pane>
      <a-tab-pane key="elements" title="元素管理">
        <AppAutomationElementsView />
      </a-tab-pane>
      <a-tab-pane key="scene-builder" title="场景编排">
        <AppAutomationSceneBuilderView />
      </a-tab-pane>
      <a-tab-pane key="test-cases" title="测试用例">
        <AppAutomationTestCasesView />
      </a-tab-pane>
      <a-tab-pane key="suites" title="测试套件">
        <AppAutomationSuitesView />
      </a-tab-pane>
      <a-tab-pane key="executions" title="执行记录">
        <AppAutomationExecutionsView />
      </a-tab-pane>
      <a-tab-pane key="scheduled-tasks" title="定时任务">
        <AppAutomationScheduledTasksView />
      </a-tab-pane>
      <a-tab-pane key="notifications" title="通知日志">
        <AppAutomationNotificationsView />
      </a-tab-pane>
      <a-tab-pane key="reports" title="执行报告">
        <AppAutomationReportsView />
      </a-tab-pane>
      <a-tab-pane key="settings" title="环境设置">
        <AppAutomationSettingsView />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { AppAutomationTab } from '../types'
import AppAutomationDashboardView from './AppAutomationDashboardView.vue'
import AppAutomationDevicesView from './AppAutomationDevicesView.vue'
import AppAutomationPackagesView from './AppAutomationPackagesView.vue'
import AppAutomationElementsView from './AppAutomationElementsView.vue'
import AppAutomationSceneBuilderView from './AppAutomationSceneBuilderView.vue'
import AppAutomationTestCasesView from './AppAutomationTestCasesView.vue'
import AppAutomationSuitesView from './AppAutomationSuitesView.vue'
import AppAutomationExecutionsView from './AppAutomationExecutionsView.vue'
import AppAutomationScheduledTasksView from './AppAutomationScheduledTasksView.vue'
import AppAutomationNotificationsView from './AppAutomationNotificationsView.vue'
import AppAutomationReportsView from './AppAutomationReportsView.vue'
import AppAutomationSettingsView from './AppAutomationSettingsView.vue'

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
