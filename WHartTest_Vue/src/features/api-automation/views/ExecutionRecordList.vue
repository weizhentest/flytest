<template>
  <div class="execution-record-list">
    <div class="page-header api-page-header">
      <div class="header-left">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索执行记录"
          allow-clear
          style="width: 260px"
          @search="loadRecords"
          @clear="loadRecords"
        />
      </div>
      <div class="header-right">
        <a-button @click="loadRecords">刷新</a-button>
      </div>
    </div>

    <div class="content-section">
      <a-table :data="filteredRecords" :loading="loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="接口名称" data-index="request_name" :width="220" ellipsis tooltip />
          <a-table-column title="方法" :width="90">
            <template #cell="{ record }">
              <a-tag :color="methodColorMap[record.method] || 'arcoblue'">{{ record.method }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="状态码" :width="90">
            <template #cell="{ record }">{{ record.status_code ?? '-' }}</template>
          </a-table-column>
          <a-table-column title="结果" :width="90">
            <template #cell="{ record }">
              <a-tag :color="record.passed ? 'green' : record.status === 'error' ? 'red' : 'orange'">
                {{ record.passed ? '通过' : record.status }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="响应时间" :width="120">
            <template #cell="{ record }">{{ formatDuration(record.response_time) }}</template>
          </a-table-column>
          <a-table-column title="执行人" data-index="executor_name" :width="120" />
          <a-table-column title="执行时间" :width="180">
            <template #cell="{ record }">{{ formatDate(record.created_at) }}</template>
          </a-table-column>
          <a-table-column title="操作" :width="150" align="center">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="small" @click="viewRecord(record)">详情</a-button>
                <a-popconfirm content="确定删除该执行记录吗？" @ok="deleteRecord(record.id)">
                  <a-button type="text" size="small" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </div>

    <a-drawer v-model:visible="detailVisible" width="760px" title="执行记录详情" :footer="false">
      <div v-if="currentRecord" class="detail-drawer">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="接口名称">{{ currentRecord.request_name }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="currentRecord.passed ? 'green' : currentRecord.status === 'error' ? 'red' : 'orange'">
              {{ currentRecord.status }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="状态码">{{ currentRecord.status_code ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="响应时间">{{ formatDuration(currentRecord.response_time) }}</a-descriptions-item>
          <a-descriptions-item label="执行环境">{{ currentRecord.environment_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ currentRecord.executor_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="最终地址" :span="2">{{ currentRecord.url }}</a-descriptions-item>
          <a-descriptions-item label="错误信息" :span="2">{{ currentRecord.error_message || '-' }}</a-descriptions-item>
        </a-descriptions>

        <a-divider>断言结果</a-divider>
        <a-table :data="currentRecord.assertions_results || []" :pagination="false" row-key="index">
          <template #columns>
            <a-table-column title="#" data-index="index" :width="60" />
            <a-table-column title="类型" data-index="type" :width="120" />
            <a-table-column title="期望值" data-index="expected" ellipsis tooltip />
            <a-table-column title="实际值" data-index="actual" ellipsis tooltip />
            <a-table-column title="结果" :width="90">
              <template #cell="{ record }">
                <a-tag :color="record.passed ? 'green' : 'red'">{{ record.passed ? '通过' : '失败' }}</a-tag>
              </template>
            </a-table-column>
          </template>
        </a-table>

        <a-divider>请求快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentRecord.request_snapshot) }}</pre>

        <a-divider>响应快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentRecord.response_snapshot) }}</pre>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { executionRecordApi } from '../api'
import type { ApiExecutionRecord } from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const searchKeyword = ref('')
const records = ref<ApiExecutionRecord[]>([])
const detailVisible = ref(false)
const currentRecord = ref<ApiExecutionRecord | null>(null)

const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
}

const filteredRecords = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return records.value
  return records.value.filter(item =>
    item.request_name.toLowerCase().includes(keyword) || item.url.toLowerCase().includes(keyword)
  )
})

const formatDate = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(2)} ms`
}

const stringifyBlock = (value: any) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const loadRecords = async () => {
  if (!projectId.value) {
    records.value = []
    return
  }
  loading.value = true
  try {
    const res = await executionRecordApi.list({ project: projectId.value })
    const data = res.data?.data || res.data || []
    records.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('[ExecutionRecordList] 获取执行记录失败:', error)
    Message.error('获取执行记录失败')
  } finally {
    loading.value = false
  }
}

const viewRecord = (record: ApiExecutionRecord) => {
  currentRecord.value = record
  detailVisible.value = true
}

const deleteRecord = async (id: number) => {
  try {
    await executionRecordApi.delete(id)
    Message.success('执行记录删除成功')
    loadRecords()
  } catch (error: any) {
    Message.error(error?.error || '删除执行记录失败')
  }
}

watch(
  () => projectId.value,
  () => {
    loadRecords()
  },
  { immediate: true }
)

defineExpose({
  refresh: loadRecords,
})
</script>

<style scoped>
.execution-record-list {
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
