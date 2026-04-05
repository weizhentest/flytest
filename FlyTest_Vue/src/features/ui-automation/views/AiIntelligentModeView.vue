<template>
  <div class="ai-mode-view">
    <a-alert class="mode-tip" type="info" show-icon>
      AI 智能模式会优先使用已激活的 LLM 做任务规划；如果当前环境未安装 `browser-use / Playwright`，会自动切换到 AI 规划执行后端。
    </a-alert>

    <div v-if="!projectId" class="empty-state">
      <a-empty description="请先选择项目后再使用 AI 智能模式" />
    </div>

    <template v-else>
      <a-tabs v-model:active-key="activeView" lazy-load>
        <a-tab-pane key="cases" title="AI 用例">
          <div class="page-header">
            <div class="search-box">
              <a-input-search
                v-model="caseFilters.search"
                placeholder="搜索用例名称或任务描述"
                allow-clear
                style="width: 280px"
                @search="reloadCases"
                @clear="reloadCases"
              />
              <a-select
                v-model="caseFilters.default_execution_mode"
                placeholder="执行模式"
                allow-clear
                style="width: 140px"
                @change="reloadCases"
              >
                <a-option value="text">文本模式</a-option>
                <a-option value="vision">视觉模式</a-option>
              </a-select>
              <a-button type="outline" @click="reloadCases">
                <template #icon><icon-refresh /></template>
                刷新
              </a-button>
            </div>

            <div class="action-buttons">
              <a-button type="outline" @click="openAdhocModal">
                <template #icon><icon-play-arrow /></template>
                临时执行
              </a-button>
              <a-button type="primary" @click="openCaseModal()">
                <template #icon><icon-plus /></template>
                新建 AI 用例
              </a-button>
            </div>
          </div>

          <a-table
            :columns="caseColumns"
            :data="cases"
            :loading="caseLoading"
            :pagination="casePagination"
            :scroll="{ x: 1080 }"
            row-key="id"
            @page-change="onCasePageChange"
            @page-size-change="onCasePageSizeChange"
          >
            <template #default_execution_mode="{ record }">
              <a-tag :color="modeColors[record.default_execution_mode]">
                {{ AI_MODE_LABELS[record.default_execution_mode] }}
              </a-tag>
            </template>
            <template #updated_at="{ record }">
              {{ formatTime(record.updated_at) }}
            </template>
            <template #operations="{ record }">
              <a-space :size="4">
                <a-button type="text" size="mini" @click="runCase(record)">
                  <template #icon><icon-play-arrow /></template>
                  运行
                </a-button>
                <a-button type="text" size="mini" @click="openCaseModal(record)">
                  <template #icon><icon-edit /></template>
                  编辑
                </a-button>
                <a-popconfirm content="确定删除该 AI 用例？" @ok="deleteCase(record.id)">
                  <a-button type="text" size="mini" status="danger">
                    <template #icon><icon-delete /></template>
                    删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="records" title="AI 执行记录">
          <div class="page-header">
            <div class="search-box">
              <a-input-search
                v-model="recordFilters.search"
                placeholder="搜索执行记录"
                allow-clear
                style="width: 240px"
                @search="reloadRecords"
                @clear="reloadRecords"
              />
              <a-select
                v-model="recordFilters.status"
                placeholder="执行状态"
                allow-clear
                style="width: 140px"
                @change="reloadRecords"
              >
                <a-option v-for="(label, key) in AI_STATUS_LABELS" :key="key" :value="key">
                  {{ label }}
                </a-option>
              </a-select>
              <a-select
                v-model="recordFilters.execution_mode"
                placeholder="执行模式"
                allow-clear
                style="width: 140px"
                @change="reloadRecords"
              >
                <a-option v-for="(label, key) in AI_MODE_LABELS" :key="key" :value="key">
                  {{ label }}
                </a-option>
              </a-select>
              <a-button type="outline" @click="reloadRecords">
                <template #icon><icon-refresh /></template>
                刷新
              </a-button>
            </div>
          </div>

          <a-table
            :columns="recordColumns"
            :data="records"
            :loading="recordLoading"
            :pagination="recordPagination"
            :scroll="{ x: 1180 }"
            row-key="id"
            @page-change="onRecordPageChange"
            @page-size-change="onRecordPageSizeChange"
          >
            <template #execution_mode="{ record }">
              <a-tag :color="modeColors[record.execution_mode]">
                {{ AI_MODE_LABELS[record.execution_mode] }}
              </a-tag>
            </template>
            <template #execution_backend="{ record }">
              <a-tag :color="backendColors[record.execution_backend]">
                {{ AI_BACKEND_LABELS[record.execution_backend] }}
              </a-tag>
            </template>
            <template #status="{ record }">
              <a-tag :color="statusColors[record.status]">
                {{ AI_STATUS_LABELS[record.status] }}
              </a-tag>
            </template>
            <template #progress="{ record }">
              {{ formatProgress(record) }}
            </template>
            <template #start_time="{ record }">
              {{ formatTime(record.start_time) }}
            </template>
            <template #operations="{ record }">
              <a-space :size="4">
                <a-button type="text" size="mini" @click="viewRecord(record.id)">
                  <template #icon><icon-eye /></template>
                  详情
                </a-button>
                <a-button
                  v-if="record.status === 'running' || record.status === 'pending'"
                  type="text"
                  size="mini"
                  status="warning"
                  @click="stopRecord(record.id)"
                >
                  <template #icon><icon-stop /></template>
                  停止
                </a-button>
                <a-popconfirm content="确定删除该执行记录？" @ok="deleteRecord(record.id)">
                  <a-button type="text" size="mini" status="danger">
                    <template #icon><icon-delete /></template>
                    删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </template>

    <a-modal
      v-model:visible="caseModalVisible"
      :title="editingCaseId ? '编辑 AI 用例' : '新建 AI 用例'"
      :confirm-loading="caseSubmitting"
      width="720px"
      @ok="submitCase"
    >
      <a-form layout="vertical">
        <a-form-item label="用例名称" required>
          <a-input v-model="caseForm.name" placeholder="例如：后台登录后检查首页核心卡片" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="默认执行模式" required>
              <a-select v-model="caseForm.default_execution_mode">
                <a-option value="text">文本模式</a-option>
                <a-option value="vision">视觉模式</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="所属项目">
              <a-input :model-value="projectStore.currentProject?.name || ''" disabled />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea
            v-model="caseForm.description"
            placeholder="补充业务背景、前置条件或断言重点"
            :auto-size="{ minRows: 2, maxRows: 4 }"
          />
        </a-form-item>
        <a-form-item label="任务描述" required>
          <a-textarea
            v-model="caseForm.task_description"
            placeholder="请用自然语言描述想让 AI 完成的 UI 自动化任务"
            :auto-size="{ minRows: 5, maxRows: 9 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="adhocModalVisible"
      title="临时执行 AI 任务"
      :confirm-loading="adhocSubmitting"
      width="720px"
      @ok="submitAdhoc"
    >
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="任务名称">
              <a-input v-model="adhocForm.case_name" placeholder="不填则自动生成" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="执行模式" required>
              <a-select v-model="adhocForm.execution_mode">
                <a-option value="text">文本模式</a-option>
                <a-option value="vision">视觉模式</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="任务描述" required>
          <a-textarea
            v-model="adhocForm.task_description"
            placeholder="直接输入要执行的 AI 自动化任务"
            :auto-size="{ minRows: 6, maxRows: 10 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      v-model:visible="recordDrawerVisible"
      title="AI 执行详情"
      width="760px"
      unmount-on-close
    >
      <a-spin :loading="recordDetailLoading" style="width: 100%">
        <template v-if="currentRecord">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="任务名称">{{ currentRecord.case_name }}</a-descriptions-item>
            <a-descriptions-item label="执行人">{{ currentRecord.executed_by_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="执行模式">
              <a-tag :color="modeColors[currentRecord.execution_mode]">
                {{ AI_MODE_LABELS[currentRecord.execution_mode] }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="执行后端">
              <a-tag :color="backendColors[currentRecord.execution_backend]">
                {{ AI_BACKEND_LABELS[currentRecord.execution_backend] }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="执行状态">
              <a-tag :color="statusColors[currentRecord.status]">
                {{ AI_STATUS_LABELS[currentRecord.status] }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="模型配置">{{ currentRecord.model_config_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="开始时间">{{ formatTime(currentRecord.start_time) }}</a-descriptions-item>
            <a-descriptions-item label="结束时间">{{ currentRecord.end_time ? formatTime(currentRecord.end_time) : '-' }}</a-descriptions-item>
            <a-descriptions-item label="执行时长">
              {{ currentRecord.duration != null ? `${currentRecord.duration.toFixed(2)}s` : '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="任务进度">{{ formatProgress(currentRecord) }}</a-descriptions-item>
          </a-descriptions>

          <a-divider>任务描述</a-divider>
          <div class="block-card">
            {{ currentRecord.task_description }}
          </div>

          <template v-if="currentRecord.error_message">
            <a-divider>错误信息</a-divider>
            <a-alert type="error" :title="currentRecord.error_message" />
          </template>

          <template v-if="currentRecord.planned_tasks?.length">
            <a-divider>规划任务</a-divider>
            <div class="item-list">
              <div v-for="task in currentRecord.planned_tasks" :key="task.id" class="item-card">
                <div class="item-head">
                  <span class="item-title">{{ task.title }}</span>
                  <a-tag :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</a-tag>
                </div>
                <div class="item-desc">{{ task.description }}</div>
                <div v-if="task.expected_result" class="item-meta">预期结果：{{ task.expected_result }}</div>
              </div>
            </div>
          </template>

          <template v-if="currentRecord.steps_completed?.length">
            <a-divider>已完成步骤</a-divider>
            <div class="item-list">
              <div v-for="step in currentRecord.steps_completed" :key="`${step.step}-${step.completed_at}`" class="item-card">
                <div class="item-head">
                  <span class="item-title">步骤 {{ step.step }} · {{ step.title }}</span>
                  <a-tag :color="step.status === 'passed' ? 'green' : 'red'">{{ step.status === 'passed' ? '成功' : '失败' }}</a-tag>
                </div>
                <div class="item-desc">{{ step.description }}</div>
                <div class="item-meta">{{ step.message }}</div>
              </div>
            </div>
          </template>

          <template v-if="currentRecord.logs">
            <a-divider>执行日志</a-divider>
            <pre class="log-panel">{{ currentRecord.logs }}</pre>
          </template>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconDelete,
  IconEdit,
  IconEye,
  IconPlayArrow,
  IconPlus,
  IconRefresh,
  IconStop,
} from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { aiCaseApi, aiExecutionApi } from '../api'
import type {
  UiAICase,
  UiAICaseForm,
  UiAIAdhocRunForm,
  UiAIExecutionBackend,
  UiAIExecutionMode,
  UiAIExecutionRecord,
  UiAIExecutionStatus,
} from '../types'
import {
  AI_BACKEND_LABELS,
  AI_MODE_LABELS,
  AI_STATUS_LABELS,
  extractPaginationData,
  extractResponseData,
} from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const activeView = ref<'cases' | 'records'>('cases')

const caseLoading = ref(false)
const caseSubmitting = ref(false)
const cases = ref<UiAICase[]>([])
const casePagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })
const caseFilters = reactive({
  search: '',
  default_execution_mode: undefined as UiAIExecutionMode | undefined,
})

const caseModalVisible = ref(false)
const editingCaseId = ref<number | null>(null)
const caseForm = reactive<UiAICaseForm>({
  project: 0,
  name: '',
  description: '',
  task_description: '',
  default_execution_mode: 'text',
})

const adhocModalVisible = ref(false)
const adhocSubmitting = ref(false)
const adhocForm = reactive<UiAIAdhocRunForm>({
  project: 0,
  case_name: '',
  task_description: '',
  execution_mode: 'text',
})

const recordLoading = ref(false)
const records = ref<UiAIExecutionRecord[]>([])
const recordPagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })
const recordFilters = reactive({
  search: '',
  status: undefined as UiAIExecutionStatus | undefined,
  execution_mode: undefined as UiAIExecutionMode | undefined,
})

const recordDrawerVisible = ref(false)
const recordDetailLoading = ref(false)
const currentRecord = ref<UiAIExecutionRecord | null>(null)

let pollingTimer: number | null = null

const modeColors: Record<UiAIExecutionMode, string> = {
  text: 'arcoblue',
  vision: 'purple',
}

const statusColors: Record<UiAIExecutionStatus, string> = {
  pending: 'gray',
  running: 'arcoblue',
  passed: 'green',
  failed: 'red',
  stopped: 'orange',
}

const backendColors: Record<UiAIExecutionBackend, string> = {
  planning: 'cyan',
  browser_use: 'purple',
}

const caseColumns = [
  { title: 'ID', dataIndex: 'id', width: 80, align: 'center' as const },
  { title: '用例名称', dataIndex: 'name', width: 180, ellipsis: true, tooltip: true },
  { title: '默认执行模式', slotName: 'default_execution_mode', width: 130, align: 'center' as const },
  { title: '任务描述', dataIndex: 'task_description', ellipsis: true, tooltip: true },
  { title: '更新人', dataIndex: 'creator_name', width: 110, align: 'center' as const },
  { title: '更新时间', slotName: 'updated_at', width: 170, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 180, fixed: 'right' as const, align: 'center' as const },
]

const recordColumns = [
  { title: 'ID', dataIndex: 'id', width: 80, align: 'center' as const },
  { title: '任务名称', dataIndex: 'case_name', width: 180, ellipsis: true, tooltip: true },
  { title: '执行模式', slotName: 'execution_mode', width: 110, align: 'center' as const },
  { title: '执行后端', slotName: 'execution_backend', width: 120, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 100, align: 'center' as const },
  { title: '进度', slotName: 'progress', width: 90, align: 'center' as const },
  { title: '模型配置', dataIndex: 'model_config_name', width: 160, ellipsis: true, tooltip: true },
  { title: '开始时间', slotName: 'start_time', width: 170, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 180, fixed: 'right' as const, align: 'center' as const },
]

const hasRunningRecords = computed(() => {
  if (currentRecord.value?.status === 'running' || currentRecord.value?.status === 'pending') {
    return true
  }
  return records.value.some(record => record.status === 'running' || record.status === 'pending')
})

const resetCaseForm = () => {
  caseForm.project = projectId.value || 0
  caseForm.name = ''
  caseForm.description = ''
  caseForm.task_description = ''
  caseForm.default_execution_mode = 'text'
}

const resetAdhocForm = () => {
  adhocForm.project = projectId.value || 0
  adhocForm.case_name = ''
  adhocForm.task_description = ''
  adhocForm.execution_mode = 'text'
}

const formatTime = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const formatProgress = (record: UiAIExecutionRecord) => {
  const total = record.planned_task_count ?? record.planned_tasks?.length ?? 0
  const completed = record.completed_task_count ?? record.steps_completed?.length ?? 0
  return `${completed}/${total}`
}

const taskStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
  }
  return labels[status] || status
}

const taskStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'gray',
    running: 'arcoblue',
    completed: 'green',
    failed: 'red',
  }
  return colors[status] || 'gray'
}

const fetchCases = async (showLoading = true) => {
  if (!projectId.value) return
  if (showLoading) caseLoading.value = true
  try {
    const response = await aiCaseApi.list({
      project: projectId.value,
      default_execution_mode: caseFilters.default_execution_mode,
      search: caseFilters.search || undefined,
      page: casePagination.current,
      page_size: casePagination.pageSize,
    })
    const { items, count } = extractPaginationData(response)
    cases.value = items
    casePagination.total = count
  } catch {
    Message.error('获取 AI 用例失败')
  } finally {
    if (showLoading) caseLoading.value = false
  }
}

const fetchRecords = async (showLoading = true) => {
  if (!projectId.value) return
  if (showLoading) recordLoading.value = true
  try {
    const response = await aiExecutionApi.list({
      project: projectId.value,
      status: recordFilters.status,
      execution_mode: recordFilters.execution_mode,
      search: recordFilters.search || undefined,
      page: recordPagination.current,
      page_size: recordPagination.pageSize,
    })
    const { items, count } = extractPaginationData(response)
    records.value = items
    recordPagination.total = count
  } catch {
    Message.error('获取 AI 执行记录失败')
  } finally {
    if (showLoading) recordLoading.value = false
  }
}

const loadRecordDetail = async (id: number, showLoading = true) => {
  if (showLoading) recordDetailLoading.value = true
  try {
    const response = await aiExecutionApi.get(id)
    const detail = extractResponseData<UiAIExecutionRecord>(response)
    if (detail) {
      currentRecord.value = detail
    }
  } catch {
    Message.error('获取执行详情失败')
  } finally {
    if (showLoading) recordDetailLoading.value = false
  }
}

const reloadCases = () => {
  casePagination.current = 1
  void fetchCases()
}

const reloadRecords = () => {
  recordPagination.current = 1
  void fetchRecords()
}

const onCasePageChange = (page: number) => {
  casePagination.current = page
  void fetchCases()
}

const onCasePageSizeChange = (size: number) => {
  casePagination.pageSize = size
  casePagination.current = 1
  void fetchCases()
}

const onRecordPageChange = (page: number) => {
  recordPagination.current = page
  void fetchRecords()
}

const onRecordPageSizeChange = (size: number) => {
  recordPagination.pageSize = size
  recordPagination.current = 1
  void fetchRecords()
}

const openCaseModal = (record?: UiAICase) => {
  if (record) {
    editingCaseId.value = record.id
    caseForm.project = record.project
    caseForm.name = record.name
    caseForm.description = record.description || ''
    caseForm.task_description = record.task_description
    caseForm.default_execution_mode = record.default_execution_mode
  } else {
    editingCaseId.value = null
    resetCaseForm()
  }
  caseModalVisible.value = true
}

const submitCase = async () => {
  if (!projectId.value) {
    Message.warning('请先选择项目')
    return false
  }
  if (!caseForm.name.trim()) {
    Message.warning('请输入用例名称')
    return false
  }
  if (!caseForm.task_description.trim()) {
    Message.warning('请输入任务描述')
    return false
  }

  caseSubmitting.value = true
  caseForm.project = projectId.value

  try {
    if (editingCaseId.value) {
      await aiCaseApi.update(editingCaseId.value, { ...caseForm })
      Message.success('AI 用例已更新')
    } else {
      await aiCaseApi.create({ ...caseForm })
      Message.success('AI 用例已创建')
    }
    caseModalVisible.value = false
    await fetchCases()
    return true
  } catch {
    Message.error(editingCaseId.value ? '更新 AI 用例失败' : '创建 AI 用例失败')
    return false
  } finally {
    caseSubmitting.value = false
  }
}

const deleteCase = async (id: number) => {
  try {
    await aiCaseApi.delete(id)
    Message.success('AI 用例已删除')
    await fetchCases()
  } catch {
    Message.error('删除 AI 用例失败')
  }
}

const runCase = async (record: UiAICase) => {
  try {
    const response = await aiCaseApi.run(record.id, record.default_execution_mode)
    const created = extractResponseData<UiAIExecutionRecord>(response)
    activeView.value = 'records'
    await fetchRecords()
    if (created?.id) {
      await loadRecordDetail(created.id)
      recordDrawerVisible.value = true
    }
    Message.success('AI 用例已开始执行')
  } catch (error: any) {
    Message.error(error?.response?.data?.error || '运行 AI 用例失败')
  }
}

const openAdhocModal = () => {
  resetAdhocForm()
  adhocModalVisible.value = true
}

const submitAdhoc = async () => {
  if (!projectId.value) {
    Message.warning('请先选择项目')
    return false
  }
  if (!adhocForm.task_description.trim()) {
    Message.warning('请输入任务描述')
    return false
  }

  adhocSubmitting.value = true
  adhocForm.project = projectId.value

  try {
    const response = await aiExecutionApi.runAdhoc({ ...adhocForm })
    const created = extractResponseData<UiAIExecutionRecord>(response)
    adhocModalVisible.value = false
    activeView.value = 'records'
    await fetchRecords()
    if (created?.id) {
      await loadRecordDetail(created.id)
      recordDrawerVisible.value = true
    }
    Message.success('临时 AI 任务已开始执行')
    return true
  } catch (error: any) {
    Message.error(error?.response?.data?.error || '临时 AI 任务执行失败')
    return false
  } finally {
    adhocSubmitting.value = false
  }
}

const viewRecord = async (id: number) => {
  recordDrawerVisible.value = true
  await loadRecordDetail(id)
}

const stopRecord = async (id: number) => {
  try {
    await aiExecutionApi.stop(id)
    Message.success('已发送停止信号')
    await Promise.all([
      fetchRecords(false),
      currentRecord.value?.id === id ? loadRecordDetail(id, false) : Promise.resolve(),
    ])
  } catch (error: any) {
    Message.error(error?.response?.data?.error || '停止任务失败')
  }
}

const deleteRecord = async (id: number) => {
  try {
    await aiExecutionApi.delete(id)
    if (currentRecord.value?.id === id) {
      recordDrawerVisible.value = false
      currentRecord.value = null
    }
    Message.success('执行记录已删除')
    await fetchRecords()
  } catch {
    Message.error('删除执行记录失败')
  }
}

const startPolling = () => {
  if (pollingTimer != null) return
  pollingTimer = window.setInterval(() => {
    void fetchRecords(false)
    if (recordDrawerVisible.value && currentRecord.value?.id) {
      void loadRecordDetail(currentRecord.value.id, false)
    }
  }, 2500)
}

const stopPolling = () => {
  if (pollingTimer != null) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

const refresh = () => {
  void Promise.all([fetchCases(), fetchRecords()])
}

defineExpose({ refresh })

watch(projectId, newValue => {
  resetCaseForm()
  resetAdhocForm()
  cases.value = []
  records.value = []
  currentRecord.value = null
  if (newValue) {
    casePagination.current = 1
    recordPagination.current = 1
    void Promise.all([fetchCases(), fetchRecords()])
  }
}, { immediate: true })

watch(hasRunningRecords, value => {
  if (value) {
    startPolling()
  } else {
    stopPolling()
  }
}, { immediate: true })

watch(recordDrawerVisible, visible => {
  if (!visible) {
    currentRecord.value = null
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.ai-mode-view {
  padding: 16px;
  background: var(--color-bg-2);
  border-radius: 8px;
}

.mode-tip {
  margin-bottom: 16px;
}

.empty-state {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.search-box,
.action-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.block-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--color-fill-2);
  color: var(--color-text-1);
  line-height: 1.7;
  white-space: pre-wrap;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.item-card {
  padding: 14px;
  border-radius: 10px;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-2);
}

.item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.item-title {
  font-weight: 600;
  color: var(--color-text-1);
}

.item-desc {
  margin-top: 8px;
  color: var(--color-text-1);
  line-height: 1.6;
  white-space: pre-wrap;
}

.item-meta {
  margin-top: 8px;
  color: var(--color-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.log-panel {
  margin: 0;
  padding: 14px;
  border-radius: 8px;
  background: var(--color-fill-2);
  color: var(--color-text-1);
  font-size: 12px;
  line-height: 1.6;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .search-box,
  .action-buttons {
    width: 100%;
  }
}
</style>
