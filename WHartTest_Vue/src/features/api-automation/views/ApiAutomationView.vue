<template>
  <div class="api-automation-layout">
    <CollectionPanel ref="collectionPanelRef" @select="onCollectionSelect" @updated="onCollectionUpdated" />
    <div class="layout-content">
      <RequestList
        v-show="activeTab === 'requests'"
        ref="requestListRef"
        :selected-collection-id="selectedCollectionId"
        @executed="executionRecordListRef?.refresh?.()"
        @updated="onRequestUpdated"
      />
      <TestCaseList
        v-show="activeTab === 'test-cases'"
        ref="testCaseListRef"
        :selected-collection-id="selectedCollectionId"
        @executed="executionRecordListRef?.refresh?.()"
      />
      <EnvironmentList
        v-show="activeTab === 'environments'"
        ref="environmentListRef"
      />
      <ExecutionRecordList
        v-show="activeTab === 'execution-records'"
        ref="executionRecordListRef"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiCollection } from '../types'
import CollectionPanel from '../components/CollectionPanel.vue'
import EnvironmentList from './EnvironmentList.vue'
import ExecutionRecordList from './ExecutionRecordList.vue'
import RequestList from './RequestList.vue'
import TestCaseList from './TestCaseList.vue'

type ApiAutomationTab = 'requests' | 'test-cases' | 'environments' | 'execution-records'

const route = useRoute()
const router = useRouter()

const selectedCollectionId = ref<number | undefined>(undefined)

const collectionPanelRef = ref()
const requestListRef = ref()
const environmentListRef = ref()
const executionRecordListRef = ref()
const testCaseListRef = ref()

const normalizeTab = (value: unknown): ApiAutomationTab => {
  const tab = String(value || 'requests')
  if (tab === 'test-cases' || tab === 'environments' || tab === 'execution-records') {
    return tab
  }
  return 'requests'
}

const activeTab = computed<ApiAutomationTab>(() => normalizeTab(route.query.tab))

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
  environmentListRef.value?.refresh?.()
}

watch(
  () => route.query.tab,
  tab => {
    const normalizedTab = normalizeTab(tab)
    if (tab !== normalizedTab) {
      router.replace({
        path: '/api-automation',
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
    case 'requests':
      requestListRef.value?.refresh?.()
      break
    case 'test-cases':
      testCaseListRef.value?.refresh?.()
      break
    case 'environments':
      environmentListRef.value?.refresh?.()
      break
    case 'execution-records':
      executionRecordListRef.value?.refresh?.()
      break
  }
})
</script>

<style scoped>
.api-automation-layout {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 18px;
  overflow: hidden;
  padding: 8px;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.08), transparent 30%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(248, 250, 252, 0.82));
  border-radius: 28px;
}

@media (max-width: 768px) {
  .api-automation-layout {
    flex-direction: column;
  }
}

.layout-content {
  flex: 1;
  height: 100%;
  overflow: auto;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(248, 250, 252, 0.94));
  border-radius: 26px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
  padding: 28px;
}

@media (max-width: 1200px) {
  .api-automation-layout {
    gap: 14px;
    padding: 4px;
  }

  .layout-content {
    padding: 22px;
  }
}
</style>
