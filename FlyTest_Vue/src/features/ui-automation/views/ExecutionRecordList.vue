<template>
  <div class="execution-record-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.status"
          placeholder="执行状态"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="(label, key) in STATUS_LABELS" :key="key" :value="Number(key)">{{ label }}</a-option>
        </a-select>
        <a-select
          v-model="filters.trigger_type"
          placeholder="触发类型"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option value="manual">手动执行</a-option>
          <a-option value="scheduled">定时执行</a-option>
          <a-option value="api">API 触发</a-option>
        </a-select>
        <a-button type="outline" @click="onSearch">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="recordData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1100 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as ExecutionStatus]">
          {{ STATUS_LABELS[record.status as ExecutionStatus] ?? '未知' }}
        </a-tag>
      </template>
      <template #trigger_type="{ record }">
        <a-tag :color="triggerColors[record.trigger_type]">{{ triggerLabels[record.trigger_type] }}</a-tag>
      </template>
      <template #duration="{ record }">
        <span v-if="record.duration != null">{{ record.duration.toFixed(2) }}s</span>
        <span v-else>-</span>
      </template>
      <template #start_time="{ record }">
        <span v-if="record.start_time">{{ formatTime(record.start_time) }}</span>
        <span v-else>-</span>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewDetail(record)">
            <template #icon><icon-eye /></template>
            详情
          </a-button>
          <a-popconfirm content="确定删除此执行记录？关联的截图、视频、Trace文件将一并删除。" @ok="handleDelete(record.id)">
            <a-button type="text" size="mini" status="danger">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
    <a-drawer
      v-model:visible="drawerVisible"
      title="执行记录详情"
      width="700px"
      unmount-on-close
    >
      <template v-if="currentRecord">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="用例名称">{{ currentRecord.test_case_name ?? `ID: ${currentRecord.test_case}` }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ currentRecord.executor_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="statusColors[currentRecord.status as ExecutionStatus]">
              {{ STATUS_LABELS[currentRecord.status as ExecutionStatus] ?? '未知' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="触发类型">
            <a-tag :color="triggerColors[currentRecord.trigger_type]">{{ triggerLabels[currentRecord.trigger_type] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ currentRecord.start_time ? formatTime(currentRecord.start_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ currentRecord.end_time ? formatTime(currentRecord.end_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行时长">{{ currentRecord.duration != null ? `${currentRecord.duration.toFixed(2)}s` : '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行追踪">
            <a-button v-if="currentRecord.trace_path" type="primary" size="small" @click="viewTrace(currentRecord.id)">
              <template #icon><icon-eye /></template>
              查看 Trace
            </a-button>
            <span v-else>-</span>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 错误信息 -->
        <template v-if="currentRecord.error_message">
          <a-divider>错误信息</a-divider>
          <a-alert type="error" :title="currentRecord.error_message" />
        </template>

        <!-- 执行日志 -->
        <template v-if="currentRecord.log">
          <a-divider>执行日志</a-divider>
          <pre class="log-content">{{ currentRecord.log }}</pre>
        </template>

        <!-- 步骤执行结果 -->
        <template v-if="currentRecord.step_results?.length">
          <a-divider>步骤执行结果</a-divider>
          <a-collapse :default-active-key="[]">
            <a-collapse-item v-for="(step, idx) in currentRecord.step_results" :key="idx">
              <template #header>
                <div class="step-header">
                  <span>步骤 {{ idx + 1 }}<template v-if="getStepDescription(step)">: {{ getStepDescription(step) }}</template></span>
                  <a-tag :color="getStepStatusColor(step)" size="small" style="margin-left: 8px">
                    {{ getStepStatusText(step) }}
                  </a-tag>
                  <span v-if="getStepDuration(step)" class="step-duration">{{ getStepDuration(step) }}s</span>
                </div>
              </template>
              <div class="step-detail">
                <div v-if="getStepMessage(step)" class="step-message">
                  <a-alert :type="getStepStatus(step) === 'failed' ? 'error' : 'info'" :title="getStepMessage(step)" />
                </div>
                <div v-if="getStepScreenshot(step)" class="step-screenshot">
                  <a-image :src="formatScreenshotUrl(getStepScreenshot(step))" width="100%" fit="contain" />
                </div>
                <div class="step-raw">
                  <a-collapse>
                    <a-collapse-item header="原始数据">
                      <pre class="step-result">{{ JSON.stringify(step, null, 2) }}</pre>
                    </a-collapse-item>
                  </a-collapse>
                </div>
              </div>
            </a-collapse-item>
          </a-collapse>
        </template>

        <!-- 截图 -->
        <template v-if="currentRecord.screenshots?.length">
          <a-divider>执行截图</a-divider>
          <a-image-preview-group>
            <a-space wrap>
              <a-image
                v-for="(img, idx) in currentRecord.screenshots"
                :key="idx"
                :src="img"
                width="120"
                height="80"
                fit="cover"
              />
            </a-space>
          </a-image-preview-group>
        </template>

        <!-- 录制视频 -->
        <template v-if="currentRecord.video_path">
          <a-divider>执行录像</a-divider>
          <video :src="currentRecord.video_path" controls style="max-width: 100%; max-height: 300px;" />
        </template>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { IconRefresh, IconEye, IconDelete } from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import { executionRecordApi } from '../api'
import type { UiExecutionRecord, ExecutionStatus } from '../types'
import { STATUS_LABELS, extractPaginationData, extractResponseData } from '../types'
import { useProjectStore } from '@/store/projectStore'

const router = useRouter()
const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const recordData = ref<UiExecutionRecord[]>([])
const drawerVisible = ref(false)
const currentRecord = ref<UiExecutionRecord | null>(null)

const filters = reactive({
  status: undefined as number | undefined,
  trigger_type: undefined as string | undefined,
})
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const statusColors: Record<ExecutionStatus | 4, string> = {
  0: 'gray',
  1: 'arcoblue',
  2: 'green',
  3: 'red',
  4: 'orange',
}

const triggerLabels: Record<string, string> = {
  manual: '手动执行',
  scheduled: '定时执行',
  api: 'API 触发',
}

const triggerColors: Record<string, string> = {
  manual: 'arcoblue',
  scheduled: 'purple',
  api: 'cyan',
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '用例名称', dataIndex: 'test_case_name', ellipsis: true, tooltip: true, width: 180, align: 'center' as const },
  { title: '执行人', dataIndex: 'executor_name', width: 100, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 90, align: 'center' as const },
  { title: '触发类型', slotName: 'trigger_type', width: 100, align: 'center' as const },
  { title: '时长', slotName: 'duration', width: 90, align: 'center' as const },
  { title: '开始时间', slotName: 'start_time', width: 160, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 130, fixed: 'right' as const, align: 'center' as const },
]

const formatTime = (time: string) => {
  const d = new Date(time)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** 步骤结果辅助函数 */
type StepResult = Record<string, unknown>

const getStepStatus = (step: unknown) => ((step as StepResult)?.status as string) ?? 'unknown'
const getStepDescription = (step: unknown) => ((step as StepResult)?.description as string) ?? ''
const getStepStatusText = (step: unknown) => {
  const status = getStepStatus(step)
  const map: Record<string, string> = { passed: '通过', failed: '失败', skipped: '跳过' }
  return map[status] ?? status
}
const getStepStatusColor = (step: unknown) => {
  const status = getStepStatus(step)
  const map: Record<string, string> = { passed: 'green', failed: 'red', skipped: 'gray' }
  return map[status] ?? 'gray'
}
const getStepMessage = (step: unknown) => ((step as StepResult)?.message as string) ?? ''
const getStepDuration = (step: unknown) => {
  const d = (step as StepResult)?.duration as number | undefined
  return d != null ? d.toFixed(2) : ''
}
const getStepScreenshot = (step: unknown) => ((step as StepResult)?.screenshot as string) ?? ''

/** 格式化截图 URL */
const formatScreenshotUrl = (path: string) => {
  if (!path) return ''
  // 如果是 Base64 数据 URL，直接返回
  if (path.startsWith('data:')) return path
  // 如果是完整 URL 或已处理的 media 路径，直接返回
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/media/')) return path
  // 本地相对路径（兼容旧数据）：提取文件名，尝试访问 media 目录
  const filename = path.split('/').pop() || path
  return `/media/ui_screenshots/${filename}`
}

const fetchRecords = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await executionRecordApi.list({
      project: projectId.value,
      status: filters.status,
      trigger_type: filters.trigger_type,
    })
    const { items, count } = extractPaginationData(res)
    recordData.value = items
    pagination.total = count
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchRecords()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchRecords()
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  fetchRecords()
}

const viewDetail = async (record: UiExecutionRecord) => {
  currentRecord.value = record  // 先显示列表数据
  drawerVisible.value = true
  // 获取详情数据
  try {
    const res = await executionRecordApi.get(record.id)
    const detail = extractResponseData<UiExecutionRecord>(res)
    if (detail) {
      currentRecord.value = detail
    }
  } catch {
    // 静默失败，使用列表数据
  }
}

/** 跳转到 Trace 详情页 */
const viewTrace = (recordId: number) => {
  router.push({ name: 'TraceDetail', params: { id: recordId } })
}

/** 删除执行记录 */
const handleDelete = async (id: number) => {
  try {
    await executionRecordApi.delete(id)
    Message.success('删除成功')
    fetchRecords()
  } catch {
    Message.error('删除失败')
  }
}

const refresh = () => fetchRecords()

defineExpose({ refresh })

// 监听项目变化，重新加载数据
watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchRecords()
  }
}, { immediate: true })
</script>

<style scoped>
.execution-record-list {
  padding: 16px;
  background: var(--color-bg-2);
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.search-box {
  display: flex;
  align-items: center;
}

.log-content {
  background: var(--color-fill-2);
  padding: 12px;
  border-radius: 4px;
  overflow: auto;
  max-height: 200px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.step-result {
  background: var(--color-fill-2);
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  overflow: auto;
  max-height: 200px;
}
.step-header {
  display: flex;
  align-items: center;
}
.step-duration {
  margin-left: auto;
  font-size: 12px;
  color: var(--color-text-3);
}
.step-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.step-message {
  margin-bottom: 8px;
}
.step-screenshot {
  max-width: 100%;
  border-radius: 4px;
  overflow: hidden;
}
.step-raw {
  margin-top: 8px;
}
</style>
