<template>
  <div class="api-automation-layout">
    <CollectionPanel ref="collectionPanelRef" @select="onCollectionSelect" @updated="onCollectionUpdated" />
    <div class="layout-content">
      <RequestList
        v-if="mountedTabs.includes('requests')"
        v-show="activeTab === 'requests'"
        ref="requestListRef"
        :selected-collection-id="selectedCollectionId"
        :selected-collection-name="selectedCollection?.name"
        @executed="handleExecutionUpdated"
        @updated="onRequestUpdated"
      />
      <TestCaseList
        v-if="mountedTabs.includes('test-cases')"
        v-show="activeTab === 'test-cases'"
        ref="testCaseListRef"
        :selected-collection-id="selectedCollectionId"
        :selected-collection-name="selectedCollection?.name"
        :selected-request-id="selectedRequestId"
        :selected-request-name="selectedRequest?.name"
        @executed="handleExecutionUpdated"
      />
      <EnvironmentList
        v-if="mountedTabs.includes('environments')"
        v-show="activeTab === 'environments'"
        ref="environmentListRef"
      />
      <ExecutionRecordList
        v-if="mountedTabs.includes('execution-records')"
        v-show="activeTab === 'execution-records'"
        ref="executionRecordListRef"
        :selected-collection-id="selectedCollectionId"
        :selected-collection-name="selectedCollection?.name"
      />
      <TestReportView
        v-if="mountedTabs.includes('execution-report')"
        v-show="activeTab === 'execution-report'"
        ref="testReportViewRef"
        :project-id="currentProjectId"
        :selected-collection-id="selectedCollectionId"
        :selected-collection-name="selectedCollection?.name"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/store/projectStore'
import type { ApiAutomationSelection, ApiCollection, ApiRequest } from '../types'
import CollectionPanel from '../components/CollectionPanel.vue'

const EnvironmentList = defineAsyncComponent(() => import('./EnvironmentList.vue'))
const ExecutionRecordList = defineAsyncComponent(() => import('./ExecutionRecordList.vue'))
const RequestList = defineAsyncComponent(() => import('./RequestList.vue'))
const TestCaseList = defineAsyncComponent(() => import('./TestCaseList.vue'))
const TestReportView = defineAsyncComponent(() => import('./TestReportView.vue'))

type ApiAutomationTab = 'requests' | 'test-cases' | 'environments' | 'execution-records' | 'execution-report'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

const selectedCollectionId = ref<number | undefined>(undefined)
const selectedCollection = ref<ApiCollection | null>(null)
const selectedRequestId = ref<number | undefined>(undefined)
const selectedRequest = ref<ApiRequest | null>(null)
const currentProjectId = computed(() => projectStore.currentProject?.id)

const collectionPanelRef = ref()
const requestListRef = ref()
const environmentListRef = ref()
const executionRecordListRef = ref()
const testCaseListRef = ref()
const testReportViewRef = ref()

const normalizeTab = (value: unknown): ApiAutomationTab => {
  const tab = String(value || 'requests')
  if (tab === 'test-cases' || tab === 'environments' || tab === 'execution-records' || tab === 'execution-report') {
    return tab
  }
  return 'requests'
}

const activeTab = computed<ApiAutomationTab>(() => normalizeTab(route.query.tab))
const mountedTabs = ref<ApiAutomationTab[]>(['requests'])

const onCollectionSelect = (selection: ApiAutomationSelection) => {
  selectedCollectionId.value = selection.collection?.id
  selectedCollection.value = selection.collection
  selectedRequestId.value = selection.request?.id
  selectedRequest.value = selection.request

  if (selection.type === 'request' && activeTab.value !== 'test-cases') {
    router.replace({
      path: '/api-automation',
      query: {
        ...route.query,
        tab: 'test-cases',
      },
    })
  }
}

const onCollectionUpdated = () => {
  requestListRef.value?.refresh?.()
  testCaseListRef.value?.refresh?.()
  testReportViewRef.value?.refresh?.()
}

const onRequestUpdated = () => {
  collectionPanelRef.value?.refresh?.()
  testCaseListRef.value?.refresh?.()
  environmentListRef.value?.refresh?.()
  testReportViewRef.value?.refresh?.()
}

const handleExecutionUpdated = () => {
  executionRecordListRef.value?.refresh?.()
  testReportViewRef.value?.refresh?.()
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
  if (!mountedTabs.value.includes(newTab)) {
    mountedTabs.value = [...mountedTabs.value, newTab]
  }
})
</script>

<style scoped>
.api-automation-layout {
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
  .api-automation-layout {
    grid-template-columns: 272px minmax(0, 1fr);
    gap: 16px;
  }
}

@media (max-width: 900px) {
  .api-automation-layout {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}
</style>
