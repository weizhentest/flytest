<template>
  <div class="api-automation-layout">
    <CollectionPanel ref="collectionPanelRef" @select="onCollectionSelect" @updated="onCollectionUpdated" />
    <div class="layout-content">
      <a-tabs v-model:active-key="activeTab" type="card-gutter">
        <a-tab-pane key="requests" title="接口管理">
          <RequestList
            ref="requestListRef"
            :selected-collection-id="selectedCollectionId"
            @executed="executionRecordListRef?.refresh?.()"
            @updated="onRequestUpdated"
          />
        </a-tab-pane>
        <a-tab-pane key="environments" title="环境配置">
          <EnvironmentList ref="environmentListRef" />
        </a-tab-pane>
        <a-tab-pane key="execution-records" title="执行历史">
          <ExecutionRecordList ref="executionRecordListRef" />
        </a-tab-pane>
        <a-tab-pane key="test-cases" title="测试用例">
          <TestCaseList ref="testCaseListRef" :selected-collection-id="selectedCollectionId" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ApiCollection } from '../types'
import CollectionPanel from '../components/CollectionPanel.vue'
import EnvironmentList from './EnvironmentList.vue'
import ExecutionRecordList from './ExecutionRecordList.vue'
import RequestList from './RequestList.vue'
import TestCaseList from './TestCaseList.vue'

const activeTab = ref('requests')
const selectedCollectionId = ref<number | undefined>(undefined)

const collectionPanelRef = ref()
const requestListRef = ref()
const environmentListRef = ref()
const executionRecordListRef = ref()
const testCaseListRef = ref()

const onCollectionSelect = (collection: ApiCollection | null) => {
  selectedCollectionId.value = collection?.id
}

const onCollectionUpdated = () => {
  requestListRef.value?.refresh?.()
  testCaseListRef.value?.refresh?.()
}

const onRequestUpdated = () => {
  collectionPanelRef.value?.refresh?.()
  testCaseListRef.value?.refresh?.()
}

watch(activeTab, newTab => {
  switch (newTab) {
    case 'requests':
      requestListRef.value?.refresh?.()
      break
    case 'environments':
      environmentListRef.value?.refresh?.()
      break
    case 'execution-records':
      executionRecordListRef.value?.refresh?.()
      break
    case 'test-cases':
      testCaseListRef.value?.refresh?.()
      break
  }
})
</script>

<style scoped>
.api-automation-layout {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 10px;
  overflow: hidden;
  background-color: var(--color-bg-1);
}

@media (max-width: 768px) {
  .api-automation-layout {
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
