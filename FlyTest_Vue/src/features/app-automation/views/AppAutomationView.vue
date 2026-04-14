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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { AppAutomationTab } from '../types'
import {
  buildAppAutomationTabChangePatch,
  replaceAppAutomationQuery,
} from './appAutomationNavigation'
import {
  appAutomationTabDefinitions,
  normalizeAppAutomationTab,
} from './appAutomationTabs'

const route = useRoute()
const router = useRouter()

const activeTab = computed<AppAutomationTab>({
  get: () => normalizeAppAutomationTab(route.query.tab),
  set: value => {
    if (value === normalizeAppAutomationTab(route.query.tab)) {
      return
    }
    void replaceAppAutomationQuery(route, router, buildAppAutomationTabChangePatch(value))
  },
})

const tabDefinitions = appAutomationTabDefinitions
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
