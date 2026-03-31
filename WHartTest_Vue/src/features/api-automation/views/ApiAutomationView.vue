<template>
  <div class="api-automation-layout">
    <CollectionPanel ref="collectionPanelRef" @select="onCollectionSelect" @updated="onCollectionUpdated" />
    <div class="layout-content">
      <div class="module-nav">
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          class="module-nav-button"
          :class="{ active: activeTab === item.key }"
          @click="switchTab(item.key)"
        >
          <span class="module-nav-title">{{ item.label }}</span>
          <span class="module-nav-subtitle">{{ item.description }}</span>
        </button>
      </div>
      <RequestList
        v-show="activeTab === 'requests'"
        ref="requestListRef"
        :selected-collection-id="selectedCollectionId"
        :selected-collection-name="selectedCollection?.name"
        @executed="handleExecutionUpdated"
        @updated="onRequestUpdated"
      />
      <TestCaseList
        v-show="activeTab === 'test-cases'"
        ref="testCaseListRef"
        :selected-collection-id="selectedCollectionId"
        :selected-collection-name="selectedCollection?.name"
        @executed="handleExecutionUpdated"
      />
      <EnvironmentList
        v-show="activeTab === 'environments'"
        ref="environmentListRef"
      />
      <ExecutionRecordList
        v-show="activeTab === 'execution-records'"
        ref="executionRecordListRef"
      />
      <TestReportView
        v-show="activeTab === 'execution-report'"
        ref="testReportViewRef"
        :project-id="selectedCollection?.project || undefined"
        :selected-collection-id="selectedCollectionId"
        :selected-collection-name="selectedCollection?.name"
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
import TestReportView from './TestReportView.vue'

type ApiAutomationTab = 'requests' | 'test-cases' | 'environments' | 'execution-records' | 'execution-report'

const route = useRoute()
const router = useRouter()

const selectedCollectionId = ref<number | undefined>(undefined)
const selectedCollection = ref<ApiCollection | null>(null)

const collectionPanelRef = ref()
const requestListRef = ref()
const environmentListRef = ref()
const executionRecordListRef = ref()
const testCaseListRef = ref()
const testReportViewRef = ref()

const navItems: Array<{ key: ApiAutomationTab; label: string; description: string }> = [
  { key: 'requests', label: '接口管理', description: '维护接口定义、导入文档、执行单接口。' },
  { key: 'test-cases', label: '测试用例', description: '查看和执行接口自动化测试用例。' },
  { key: 'environments', label: '环境配置', description: '维护基础地址、变量和鉴权配置。' },
  { key: 'execution-records', label: '执行历史', description: '查看每次执行的明细记录和断言结果。' },
  { key: 'execution-report', label: '测试报告', description: '汇总通过率、失败接口和执行趋势。' },
]

const normalizeTab = (value: unknown): ApiAutomationTab => {
  const tab = String(value || 'requests')
  if (tab === 'test-cases' || tab === 'environments' || tab === 'execution-records' || tab === 'execution-report') {
    return tab
  }
  return 'requests'
}

const activeTab = computed<ApiAutomationTab>(() => normalizeTab(route.query.tab))

const switchTab = (tab: ApiAutomationTab) => {
  router.replace({
    path: '/api-automation',
    query: {
      ...route.query,
      tab,
    },
  })
}

const onCollectionSelect = (collection: ApiCollection | null) => {
  selectedCollectionId.value = collection?.id
  selectedCollection.value = collection
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
    case 'execution-report':
      testReportViewRef.value?.refresh?.()
      break
  }
})
</script>

<style scoped>
.api-automation-layout {
  display: grid;
  grid-template-columns: 292px minmax(0, 1fr);
  width: 100%;
  height: 100%;
  gap: 20px;
  overflow: hidden;
}

@media (max-width: 900px) {
  .api-automation-layout {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

.layout-content {
  min-width: 0;
  height: 100%;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.module-nav {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.module-nav-button {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 86px;
  padding: 16px 18px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.module-nav-button:hover {
  transform: translateY(-1px);
  border-color: rgba(15, 118, 110, 0.22);
  box-shadow: 0 16px 30px rgba(15, 23, 42, 0.05);
}

.module-nav-button.active {
  border-color: rgba(15, 118, 110, 0.3);
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.12), rgba(255, 255, 255, 0.94));
  box-shadow: 0 18px 34px rgba(15, 118, 110, 0.08);
}

.module-nav-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.module-nav-subtitle {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

@media (max-width: 1200px) {
  .api-automation-layout {
    grid-template-columns: 272px minmax(0, 1fr);
    gap: 16px;
  }

  .module-nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  .module-nav {
    grid-template-columns: 1fr;
  }
}
</style>
