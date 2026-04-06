<template>
  <div class="ui-automation-layout">
    <ModulePanel ref="modulePanelRef" @select="onModuleSelect" @updated="onModuleUpdated" />
    <div class="layout-content">
      <PageList
        v-show="activeTab === 'pages'"
        ref="pageListRef"
        :selected-module-id="selectedModuleId"
      />
      <PageStepList
        v-show="activeTab === 'page-steps'"
        ref="pageStepListRef"
        :selected-module-id="selectedModuleId"
      />
      <TestCaseList
        v-show="activeTab === 'testcases'"
        ref="testCaseListRef"
        :selected-module-id="selectedModuleId"
      />
      <AiIntelligentModeView
        v-show="activeTab === 'ai-intelligent'"
        ref="aiIntelligentModeRef"
      />
      <ExecutionRecordList
        v-show="activeTab === 'execution-records'"
        ref="executionRecordListRef"
      />
      <BatchRecordList
        v-show="activeTab === 'batch-records'"
        ref="batchRecordListRef"
      />
      <PublicDataList
        v-show="activeTab === 'public-data'"
        ref="publicDataListRef"
      />
      <EnvConfigList
        v-show="activeTab === 'env-config'"
        ref="envConfigListRef"
      />
      <ActuatorList
        v-show="activeTab === 'actuators'"
        ref="actuatorListRef"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ModulePanel from '../components/ModulePanel.vue'
import PageList from './PageList.vue'
import PageStepList from './PageStepList.vue'
import TestCaseList from './TestCaseList.vue'
import AiIntelligentModeView from './AiIntelligentModeView.vue'
import ExecutionRecordList from './ExecutionRecordList.vue'
import BatchRecordList from './BatchRecordList.vue'
import PublicDataList from './PublicDataList.vue'
import EnvConfigList from './EnvConfigList.vue'
import ActuatorList from './ActuatorList.vue'
import type { UiModule } from '../types'

type UiAutomationTab =
  | 'pages'
  | 'page-steps'
  | 'testcases'
  | 'ai-intelligent'
  | 'execution-records'
  | 'batch-records'
  | 'public-data'
  | 'env-config'
  | 'actuators'

const route = useRoute()
const router = useRouter()

const modulePanelRef = ref()
const pageListRef = ref()
const pageStepListRef = ref()
const testCaseListRef = ref()
const aiIntelligentModeRef = ref()
const executionRecordListRef = ref()
const batchRecordListRef = ref()
const publicDataListRef = ref()
const envConfigListRef = ref()
const actuatorListRef = ref()

const selectedModuleId = ref<number | undefined>(undefined)

const normalizeTab = (value: unknown): UiAutomationTab => {
  const tab = String(value || 'pages')

  if (
    tab === 'page-steps' ||
    tab === 'testcases' ||
    tab === 'ai-intelligent' ||
    tab === 'execution-records' ||
    tab === 'batch-records' ||
    tab === 'public-data' ||
    tab === 'env-config' ||
    tab === 'actuators'
  ) {
    return tab
  }

  return 'pages'
}

const activeTab = computed<UiAutomationTab>(() => normalizeTab(route.query.tab))

watch(
  () => route.query.tab,
  tab => {
    const normalizedTab = normalizeTab(tab)

    if (tab !== normalizedTab) {
      void router.replace({
        path: '/ui-automation',
        query: {
          ...route.query,
          tab: normalizedTab,
        },
      })
    }
  },
  { immediate: true }
)

watch(activeTab, newTab => {
  switch (newTab) {
    case 'pages':
      pageListRef.value?.refresh?.()
      break
    case 'page-steps':
      pageStepListRef.value?.refresh?.()
      break
    case 'testcases':
      testCaseListRef.value?.refresh?.()
      break
    case 'ai-intelligent':
      aiIntelligentModeRef.value?.refresh?.()
      break
    case 'execution-records':
      executionRecordListRef.value?.refresh?.()
      break
    case 'batch-records':
      batchRecordListRef.value?.refresh?.()
      break
    case 'public-data':
      publicDataListRef.value?.refresh?.()
      break
    case 'env-config':
      envConfigListRef.value?.refresh?.()
      break
    case 'actuators':
      actuatorListRef.value?.refresh?.()
      break
  }
})

const onModuleSelect = (module: UiModule | null) => {
  selectedModuleId.value = module?.id
}

const onModuleUpdated = () => {
  pageListRef.value?.refresh?.()
  pageStepListRef.value?.refresh?.()
  testCaseListRef.value?.refresh?.()
}
</script>

<style scoped>
.ui-automation-layout {
  display: grid;
  grid-template-columns: 292px minmax(0, 1fr);
  width: 100%;
  height: 100%;
  min-height: 0;
  gap: 20px;
  overflow: hidden;
}

.layout-content {
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: auto;
  display: block;
}

@media (max-width: 1200px) {
  .ui-automation-layout {
    grid-template-columns: 272px minmax(0, 1fr);
    gap: 16px;
  }
}

@media (max-width: 900px) {
  .ui-automation-layout {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}
</style>
