<template>
  <div class="test-case-list">
    <div class="page-header api-page-header">
      <div class="header-left">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索测试用例"
          allow-clear
          style="width: 260px"
          @search="loadTestCases"
          @clear="loadTestCases"
        />
      </div>
      <div class="header-right">
        <a-button @click="loadTestCases">刷新</a-button>
      </div>
    </div>

    <div v-if="!selectedCollectionId" class="empty-tip-card">
      <a-empty description="请先在左侧选择一个接口集合" />
    </div>

    <div v-else class="content-section">
      <a-table :data="filteredTestCases" :loading="loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="测试用例" data-index="name" :width="260" ellipsis tooltip />
          <a-table-column title="关联接口" :width="260" ellipsis tooltip>
            <template #cell="{ record }">
              <a-space :size="6">
                <a-tag :color="methodColorMap[record.request_method || ''] || 'arcoblue'">
                  {{ record.request_method || '-' }}
                </a-tag>
                <span>{{ record.request_name || '-' }}</span>
              </a-space>
            </template>
          </a-table-column>
          <a-table-column title="状态" :width="120" align="center">
            <template #cell="{ record }">
              <a-tag :color="statusColorMap[record.status]">{{ statusLabelMap[record.status] }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="标签" :width="90" align="center">
            <template #cell="{ record }">
              <a-tag color="cyan">{{ record.tags?.length || 0 }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="更新时间" :width="180">
            <template #cell="{ record }">{{ formatDate(record.updated_at) }}</template>
          </a-table-column>
          <a-table-column title="操作" :width="160" align="center">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="small" @click="viewTestCase(record)">详情</a-button>
                <a-popconfirm content="确定删除该测试用例吗？" @ok="deleteTestCase(record.id)">
                  <a-button type="text" size="small" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </div>

    <a-drawer v-model:visible="detailVisible" width="760px" title="测试用例详情" :footer="false">
      <div v-if="currentTestCase" class="detail-drawer">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="测试用例">{{ currentTestCase.name }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColorMap[currentTestCase.status]">
              {{ statusLabelMap[currentTestCase.status] }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="接口名称">{{ currentTestCase.request_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="请求方法">
            <a-tag :color="methodColorMap[currentTestCase.request_method || ''] || 'arcoblue'">
              {{ currentTestCase.request_method || '-' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="请求地址" :span="2">{{ currentTestCase.request_url || '-' }}</a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">{{ currentTestCase.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="标签" :span="2">
            <a-space wrap>
              <a-tag v-for="tag in currentTestCase.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
              <span v-if="!currentTestCase.tags?.length">-</span>
            </a-space>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>接口脚本</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentTestCase.script) }}</pre>

        <a-divider>断言规则</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentTestCase.assertions) }}</pre>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { testCaseApi } from '../api'
import type { ApiTestCase } from '../types'

const props = defineProps<{
  selectedCollectionId?: number
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const detailVisible = ref(false)
const searchKeyword = ref('')
const testCases = ref<ApiTestCase[]>([])
const currentTestCase = ref<ApiTestCase | null>(null)

const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
}

const statusColorMap: Record<ApiTestCase['status'], string> = {
  draft: 'gray',
  ready: 'green',
  disabled: 'red',
}

const statusLabelMap: Record<ApiTestCase['status'], string> = {
  draft: '草稿',
  ready: '就绪',
  disabled: '停用',
}

const filteredTestCases = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return testCases.value
  return testCases.value.filter(item => {
    return (
      item.name.toLowerCase().includes(keyword) ||
      (item.request_name || '').toLowerCase().includes(keyword) ||
      (item.request_url || '').toLowerCase().includes(keyword)
    )
  })
})

const formatDate = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const stringifyBlock = (value: any) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const loadTestCases = async () => {
  if (!projectId.value || !props.selectedCollectionId) {
    testCases.value = []
    return
  }
  loading.value = true
  try {
    const res = await testCaseApi.list({
      project: projectId.value,
      collection: props.selectedCollectionId,
    })
    const data = res.data?.data || res.data || []
    testCases.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('[TestCaseList] 获取测试用例失败:', error)
    Message.error('获取测试用例失败')
    testCases.value = []
  } finally {
    loading.value = false
  }
}

const viewTestCase = (record: ApiTestCase) => {
  currentTestCase.value = record
  detailVisible.value = true
}

const deleteTestCase = async (id: number) => {
  try {
    await testCaseApi.delete(id)
    Message.success('测试用例删除成功')
    if (currentTestCase.value?.id === id) {
      detailVisible.value = false
      currentTestCase.value = null
    }
    loadTestCases()
  } catch (error: any) {
    Message.error(error?.error || '删除测试用例失败')
  }
}

watch(
  () => projectId.value,
  () => {
    loadTestCases()
  },
  { immediate: true }
)

watch(
  () => props.selectedCollectionId,
  () => {
    loadTestCases()
  },
  { immediate: true }
)

defineExpose({
  refresh: loadTestCases,
})
</script>

<style scoped>
.test-case-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.api-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.empty-tip-card {
  padding: 32px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.detail-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.json-block {
  margin: 0;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.95);
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
