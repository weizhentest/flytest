<template>
  <div class="ui-automation-layout">
    <ModulePanel ref="modulePanelRef" @select="onModuleSelect" @updated="onModuleUpdated" />
    <div class="layout-content">
      <a-tabs v-model:active-key="activeTab" type="card-gutter">
        <a-tab-pane key="pages" title="页面管理">
          <PageList ref="pageListRef" :selected-module-id="selectedModuleId" />
        </a-tab-pane>
        <a-tab-pane key="page-steps" title="页面步骤">
          <PageStepList ref="pageStepListRef" :selected-module-id="selectedModuleId" />
        </a-tab-pane>
        <a-tab-pane key="testcases" title="测试用例">
          <TestCaseList ref="testCaseListRef" :selected-module-id="selectedModuleId" />
        </a-tab-pane>
        <a-tab-pane key="execution-records" title="执行记录">
          <ExecutionRecordList ref="executionRecordListRef" />
        </a-tab-pane>
        <a-tab-pane key="batch-records" title="批量执行">
          <BatchRecordList ref="batchRecordListRef" />
        </a-tab-pane>
        <a-tab-pane key="public-data" title="公共数据">
          <PublicDataList ref="publicDataListRef" />
        </a-tab-pane>
        <a-tab-pane key="env-config" title="环境配置">
          <EnvConfigList ref="envConfigListRef" />
        </a-tab-pane>
        <a-tab-pane key="actuators" title="执行器">
          <ActuatorList ref="actuatorListRef" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import ModulePanel from '../components/ModulePanel.vue'
import PageList from './PageList.vue'
import PageStepList from './PageStepList.vue'
import TestCaseList from './TestCaseList.vue'
import ExecutionRecordList from './ExecutionRecordList.vue'
import BatchRecordList from './BatchRecordList.vue'
import PublicDataList from './PublicDataList.vue'
import EnvConfigList from './EnvConfigList.vue'
import ActuatorList from './ActuatorList.vue'
import type { UiModule } from '../types'

const activeTab = ref('pages')
const modulePanelRef = ref()
const selectedModuleId = ref<number | undefined>(undefined)

const pageListRef = ref()
const pageStepListRef = ref()
const testCaseListRef = ref()
const executionRecordListRef = ref()
const batchRecordListRef = ref()
const publicDataListRef = ref()
const envConfigListRef = ref()
const actuatorListRef = ref()
void [modulePanelRef, pageListRef, pageStepListRef, testCaseListRef, executionRecordListRef, batchRecordListRef, publicDataListRef, envConfigListRef, actuatorListRef]

// 页签切换时刷新对应数据
watch(activeTab, (newTab) => {
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
  display: flex;
  width: 100%;
  height: 100%;
  gap: 10px;
  overflow: hidden;
  background-color: var(--color-bg-1);
}

@media (max-width: 768px) {
  .ui-automation-layout {
    flex-direction: column;
  }
}

.layout-content {
  flex: 1;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  padding: 20px;
}

:deep(.arco-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.arco-tabs-content) {
  flex: 1;
  overflow: auto;
}

:deep(.arco-tabs-pane) {
  height: 100%;
}
</style>
