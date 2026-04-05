<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再查看 APP 自动化执行记录" />
    </div>
    <template v-else>
      <div class="page-header">
        <div>
          <h3>执行记录</h3>
          <p>聚合查看 APP 自动化的执行状态、运行进度、步骤通过率与完整日志，运行中的任务会自动刷新。</p>
        </div>
        <a-space>
          <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
          <a-button @click="handleSearch" :loading="loading">刷新</a-button>
        </a-space>
      </div>

      <a-card class="filter-card">
        <div class="filter-grid">
          <a-input-search
            v-model="filters.search"
            allow-clear
            placeholder="搜索用例、设备、触发人或摘要"
            @search="handleSearch"
          />
          <a-select v-model="filters.status" placeholder="执行状态">
            <a-option value="">全部状态</a-option>
            <a-option value="pending">等待执行</a-option>
            <a-option value="running">执行中</a-option>
            <a-option value="passed">执行通过</a-option>
            <a-option value="failed">执行失败</a-option>
            <a-option value="stopped">已停止</a-option>
          </a-select>
          <a-select v-model="filters.suite" placeholder="执行来源">
            <a-option value="all">全部来源</a-option>
            <a-option value="standalone">独立执行</a-option>
            <a-option v-for="suite in suites" :key="suite.id" :value="String(suite.id)">
              {{ suite.name }}
            </a-option>
          </a-select>
          <div class="filter-actions">
            <a-button @click="resetFilters">重置</a-button>
            <a-button type="primary" @click="handleSearch">查询</a-button>
          </div>
        </div>
      </a-card>

      <div class="stats-grid">
        <a-card class="stat-card">
          <span class="stat-label">执行总数</span>
          <strong>{{ statistics.total }}</strong>
          <span class="stat-desc">当前筛选范围内的执行记录数量</span>
        </a-card>
        <a-card class="stat-card">
          <span class="stat-label">运行中 / 等待</span>
          <strong>{{ statistics.running }}</strong>
          <span class="stat-desc">检测到运行中任务时页面会自动轮询更新</span>
        </a-card>
        <a-card class="stat-card">
          <span class="stat-label">通过记录</span>
          <strong>{{ statistics.passed }}</strong>
          <span class="stat-desc">已完成并通过的执行条目</span>
        </a-card>
        <a-card class="stat-card">
          <span class="stat-label">平均通过率</span>
          <strong>{{ statistics.averagePassRate }}%</strong>
          <span class="stat-desc">按当前结果集的步骤通过率计算</span>
        </a-card>
      </div>

      <a-card class="table-card">
        <a-table :data="pagedExecutions" :loading="loading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="用例 / 设备" :width="260">
              <template #cell="{ record }">
                <div class="name-cell">
                  <strong>{{ record.case_name || `执行 #${record.id}` }}</strong>
                  <span>{{ record.device_name || record.device_serial || '未绑定设备' }}</span>
                </div>
              </template>
            </a-table-column>

            <a-table-column title="执行来源" :width="220">
              <template #cell="{ record }">
                <div class="meta-stack">
                  <a-tag :color="record.test_suite_id ? 'green' : 'arcoblue'">
                    {{ record.test_suite_id ? '套件执行' : '独立执行' }}
                  </a-tag>
                  <span>{{ getExecutionSource(record) }}</span>
                  <small>触发人：{{ record.triggered_by || '-' }}</small>
                </div>
              </template>
            </a-table-column>

            <a-table-column title="状态 / 进度" :width="240">
              <template #cell="{ record }">
                <div class="progress-cell">
                  <div class="progress-head">
                    <a-tag :color="getExecutionStatusMeta(record).color">
                      {{ getExecutionStatusMeta(record).label }}
                    </a-tag>
                    <span>{{ formatProgress(record.progress) }}%</span>
                  </div>
                  <div class="progress-track">
                    <div
                      class="progress-fill"
                      :style="{
                        width: `${formatProgress(record.progress)}%`,
                        background: getExecutionStatusMeta(record).hex,
                      }"
                    />
                  </div>
                </div>
              </template>
            </a-table-column>

            <a-table-column title="步骤统计" :width="180">
              <template #cell="{ record }">
                <div class="stats-cell">
                  <span class="success-text">通过 {{ record.passed_steps || 0 }}</span>
                  <span class="danger-text">失败 {{ record.failed_steps || 0 }}</span>
                  <small>总计 {{ record.total_steps || 0 }} 步 / 通过率 {{ formatRate(record.pass_rate) }}%</small>
                </div>
              </template>
            </a-table-column>

            <a-table-column title="时间信息" :width="220">
              <template #cell="{ record }">
                <div class="meta-stack">
                  <span>开始：{{ formatDateTime(record.started_at || record.created_at) }}</span>
                  <small>结束：{{ formatDateTime(record.finished_at) }}</small>
                  <small>耗时：{{ formatDuration(record.duration) }}</small>
                </div>
              </template>
            </a-table-column>

            <a-table-column title="操作" :width="240" fixed="right">
              <template #cell="{ record }">
                <a-space wrap>
                  <a-button type="text" @click="viewDetail(record.id)">详情</a-button>
                  <a-button v-if="canOpenReport(record)" type="text" @click="openReport(record)">报告</a-button>
                  <a-button
                    v-if="isExecutionRunning(record)"
                    type="text"
                    status="danger"
                    :loading="Boolean(stoppingIds[record.id])"
                    @click="stopExecution(record)"
                  >
                    停止
                  </a-button>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>

        <div class="pagination-row">
          <a-pagination
            v-model:current="pagination.current"
            v-model:page-size="pagination.pageSize"
            :total="filteredExecutions.length"
            :show-total="true"
            :show-jumper="true"
            :show-page-size="true"
            :page-size-options="['10', '20', '50']"
          />
        </div>
      </a-card>

      <a-modal v-model:visible="detailVisible" title="执行详情" width="980px" :footer="false">
        <div v-if="detailLoading" class="modal-state">正在加载执行详情...</div>
        <div v-else-if="currentExecution" class="detail-shell">
          <div class="detail-grid">
            <div class="detail-card">
              <span class="detail-label">执行状态</span>
              <strong>{{ getExecutionStatusMeta(currentExecution).label }}</strong>
            </div>
            <div class="detail-card">
              <span class="detail-label">执行来源</span>
              <strong>{{ getExecutionSource(currentExecution) }}</strong>
            </div>
            <div class="detail-card">
              <span class="detail-label">步骤通过率</span>
              <strong>{{ formatRate(currentExecution.pass_rate) }}%</strong>
            </div>
            <div class="detail-card">
              <span class="detail-label">执行耗时</span>
              <strong>{{ formatDuration(currentExecution.duration) }}</strong>
            </div>
          </div>

          <a-card class="detail-panel" title="执行摘要">
            <div class="summary-text">
              {{ currentExecution.report_summary || currentExecution.error_message || '暂无执行摘要，可继续查看日志定位运行细节。' }}
            </div>
            <div class="meta-row">
              <span>用例：{{ currentExecution.case_name || `执行 #${currentExecution.id}` }}</span>
              <span>设备：{{ currentExecution.device_name || currentExecution.device_serial || '-' }}</span>
              <span>触发方式：{{ currentExecution.trigger_mode || '-' }}</span>
              <span>触发人：{{ currentExecution.triggered_by || '-' }}</span>
              <span>开始时间：{{ formatDateTime(currentExecution.started_at || currentExecution.created_at) }}</span>
              <span>结束时间：{{ formatDateTime(currentExecution.finished_at) }}</span>
            </div>
            <a-space wrap>
              <a-button v-if="canOpenReport(currentExecution)" type="primary" @click="openReport(currentExecution)">打开执行报告</a-button>
              <a-button
                v-if="isExecutionRunning(currentExecution)"
                status="danger"
                :loading="Boolean(stoppingIds[currentExecution.id])"
                @click="stopExecution(currentExecution)"
              >
                停止执行
              </a-button>
            </a-space>
          </a-card>

          <a-card class="detail-panel" title="步骤统计与诊断">
            <div class="metric-row">
              <div class="metric-chip success-chip">通过 {{ currentExecution.passed_steps || 0 }}</div>
              <div class="metric-chip danger-chip">失败 {{ currentExecution.failed_steps || 0 }}</div>
              <div class="metric-chip neutral-chip">总计 {{ currentExecution.total_steps || 0 }}</div>
              <div class="metric-chip neutral-chip">进度 {{ formatProgress(currentExecution.progress) }}%</div>
            </div>
            <a-alert v-if="currentExecution.error_message" type="error" class="detail-alert">
              {{ currentExecution.error_message }}
            </a-alert>
          </a-card>

          <a-card class="detail-panel" title="执行日志">
            <div v-if="currentExecution.logs?.length" class="log-list">
              <div v-for="(log, index) in currentExecution.logs" :key="`${log.timestamp}-${index}`" class="log-item">
                <div class="log-meta">
                  <span>{{ formatDateTime(log.timestamp) }}</span>
                  <a-tag size="small" :color="getLogLevelColor(log.level)">{{ log.level || 'info' }}</a-tag>
                </div>
                <div class="log-message">{{ log.message || '-' }}</div>
              </div>
            </div>
            <div v-else class="modal-state">暂无执行日志</div>
          </a-card>
        </div>
      </a-modal>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppExecution, AppExecutionLog, AppTestSuite } from '../types'

const projectStore = useProjectStore()

const loading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const lastUpdatedAt = ref<string | null>(null)
const executions = ref<AppExecution[]>([])
const suites = ref<AppTestSuite[]>([])
const currentExecution = ref<AppExecution | null>(null)
const stoppingIds = reactive<Record<number, boolean>>({})

const filters = reactive({
  search: '',
  status: '',
  suite: 'all',
})

const pagination = reactive({
  current: 1,
  pageSize: 10,
})

const statusConfig = {
  pending: { label: '等待执行', color: 'gold', hex: '#ffb400' },
  running: { label: '执行中', color: 'arcoblue', hex: '#165dff' },
  passed: { label: '执行通过', color: 'green', hex: '#00b42a' },
  failed: { label: '执行失败', color: 'red', hex: '#f53f3f' },
  stopped: { label: '已停止', color: 'orange', hex: '#ff7d00' },
  completed: { label: '已完成', color: 'cyan', hex: '#14c9c9' },
  unknown: { label: '未知', color: 'gray', hex: '#86909c' },
} as const

const suiteNameMap = computed<Record<number, string>>(() =>
  suites.value.reduce<Record<number, string>>((result, item) => {
    result[item.id] = item.name
    return result
  }, {}),
)

const getExecutionState = (record: AppExecution) => {
  if (record.result === 'passed') return 'passed'
  if (record.result === 'failed' || record.status === 'failed') return 'failed'
  if (record.result === 'stopped' || record.status === 'stopped') return 'stopped'
  if (record.status === 'running') return 'running'
  if (record.status === 'pending') return 'pending'
  if (record.status === 'completed') return 'completed'
  return 'unknown'
}

const getExecutionStatusMeta = (record: AppExecution) => statusConfig[getExecutionState(record)] || statusConfig.unknown

const getExecutionSource = (record: AppExecution) => {
  if (!record.test_suite_id) return '独立执行'
  return suiteNameMap.value[record.test_suite_id] || `套件 #${record.test_suite_id}`
}

const isExecutionRunning = (record: AppExecution) => ['pending', 'running'].includes(record.status)

const canOpenReport = (record: AppExecution) =>
  Boolean(record.report_path) ||
  ['completed', 'failed', 'stopped'].includes(record.status) ||
  ['passed', 'failed', 'stopped'].includes(record.result)

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const formatDuration = (value?: number | null) => {
  const seconds = Number(value || 0)
  if (!seconds) return '-'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  const minutes = Math.floor(seconds / 60)
  const remainSeconds = Math.round(seconds % 60)
  if (minutes < 60) return `${minutes} 分 ${remainSeconds} 秒`
  const hours = Math.floor(minutes / 60)
  const remainMinutes = minutes % 60
  return `${hours} 小时 ${remainMinutes} 分`
}

const formatRate = (value?: number | null) => {
  const rate = Number(value || 0)
  return Math.round(rate * 10) / 10
}

const formatProgress = (value?: number | null) => {
  const progress = Number(value || 0)
  return Math.max(0, Math.min(100, Math.round(progress)))
}

const getLogLevelColor = (value?: string) => {
  if (value === 'error') return 'red'
  if (value === 'warning') return 'orange'
  if (value === 'success') return 'green'
  return 'arcoblue'
}

const filteredExecutions = computed(() => {
  const keyword = filters.search.trim().toLowerCase()

  return [...executions.value]
    .filter(record => {
      if (filters.status && getExecutionState(record) !== filters.status) {
        return false
      }

      if (filters.suite === 'standalone' && record.test_suite_id) {
        return false
      }

      if (filters.suite !== 'all' && filters.suite !== 'standalone' && record.test_suite_id !== Number(filters.suite)) {
        return false
      }

      if (!keyword) {
        return true
      }

      return [
        record.case_name,
        record.device_name,
        record.device_serial,
        record.triggered_by,
        record.trigger_mode,
        record.report_summary,
        record.error_message,
        getExecutionSource(record),
      ]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    })
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
})

const pagedExecutions = computed(() => {
  const start = (pagination.current - 1) * pagination.pageSize
  return filteredExecutions.value.slice(start, start + pagination.pageSize)
})

const statistics = computed(() => {
  const running = filteredExecutions.value.filter(item => isExecutionRunning(item)).length
  const passed = filteredExecutions.value.filter(item => getExecutionState(item) === 'passed').length
  const failed = filteredExecutions.value.filter(item => getExecutionState(item) === 'failed').length
  const averagePassRate = filteredExecutions.value.length
    ? Math.round(
        (filteredExecutions.value.reduce((total, item) => total + Number(item.pass_rate || 0), 0) / filteredExecutions.value.length) *
          10,
      ) / 10
    : 0

  return {
    total: filteredExecutions.value.length,
    running,
    passed,
    failed,
    averagePassRate,
  }
})

const lastUpdatedText = computed(() => (lastUpdatedAt.value ? formatDateTime(lastUpdatedAt.value) : '-'))
const hasRunningExecutions = computed(() => executions.value.some(item => isExecutionRunning(item)))

const loadSuites = async () => {
  if (!projectStore.currentProjectId) {
    suites.value = []
    return
  }

  suites.value = await AppAutomationService.getTestSuites(projectStore.currentProjectId)
}

const loadExecutions = async (options: { silent?: boolean } = {}) => {
  if (!projectStore.currentProjectId) {
    executions.value = []
    return
  }

  if (!options.silent) {
    loading.value = true
  }

  try {
    executions.value = await AppAutomationService.getExecutions(projectStore.currentProjectId)
    lastUpdatedAt.value = new Date().toISOString()
  } catch (error: any) {
    Message.error(error.message || '加载执行记录失败')
  } finally {
    if (!options.silent) {
      loading.value = false
    }
  }
}

const loadExecutionDetail = async (id: number, options: { silent?: boolean; open?: boolean } = {}) => {
  if (!options.silent) {
    detailLoading.value = true
  }

  try {
    currentExecution.value = await AppAutomationService.getExecutionDetail(id)
    if (options.open) {
      detailVisible.value = true
    }
  } catch (error: any) {
    if (!options.silent) {
      Message.error(error.message || '加载执行详情失败')
    }
  } finally {
    if (!options.silent) {
      detailLoading.value = false
    }
  }
}

const loadData = async () => {
  if (!projectStore.currentProjectId) {
    suites.value = []
    executions.value = []
    currentExecution.value = null
    return
  }

  loading.value = true
  try {
    const [suiteList, executionList] = await Promise.all([
      AppAutomationService.getTestSuites(projectStore.currentProjectId),
      AppAutomationService.getExecutions(projectStore.currentProjectId),
    ])
    suites.value = suiteList
    executions.value = executionList
    lastUpdatedAt.value = new Date().toISOString()
  } catch (error: any) {
    Message.error(error.message || '加载执行记录失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  void loadExecutions()
}

const resetFilters = () => {
  filters.search = ''
  filters.status = ''
  filters.suite = 'all'
  pagination.current = 1
  void loadExecutions()
}

const viewDetail = async (id: number) => {
  await loadExecutionDetail(id, { open: true })
}

const openReport = (record: AppExecution) => {
  window.open(AppAutomationService.getExecutionReportUrl(record.id), '_blank', 'noopener')
}

const stopExecution = (record: AppExecution) => {
  Modal.confirm({
    title: '停止执行',
    content: `确认停止“${record.case_name || `执行 #${record.id}`}”吗？`,
    onOk: async () => {
      stoppingIds[record.id] = true
      try {
        await AppAutomationService.stopExecution(record.id)
        Message.success('执行已停止')
        await loadExecutions()
        if (currentExecution.value?.id === record.id) {
          await loadExecutionDetail(record.id, { open: true })
        }
      } catch (error: any) {
        Message.error(error.message || '停止执行失败')
      } finally {
        stoppingIds[record.id] = false
      }
    },
  })
}

let timer: number | null = null
let polling = false

const pollRunningExecutions = async () => {
  if (polling || !hasRunningExecutions.value) {
    return
  }

  polling = true
  try {
    await loadExecutions({ silent: true })
    if (detailVisible.value && currentExecution.value?.id) {
      await loadExecutionDetail(currentExecution.value.id, { silent: true })
    }
  } finally {
    polling = false
  }
}

watch(
  () => filteredExecutions.value.length,
  total => {
    const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize))
    if (pagination.current > maxPage) {
      pagination.current = maxPage
    }
  },
)

watch(
  () => pagination.pageSize,
  () => {
    pagination.current = 1
  },
)

watch(
  () => projectStore.currentProjectId,
  () => {
    pagination.current = 1
    detailVisible.value = false
    currentExecution.value = null
    void loadData()
  },
  { immediate: true },
)

onMounted(() => {
  timer = window.setInterval(() => {
    void pollRunningExecutions()
  }, 4000)
})

onUnmounted(() => {
  if (timer) {
    window.clearInterval(timer)
  }
})
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-shell,
.modal-state {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
  color: var(--theme-text-secondary);
}

.modal-state {
  min-height: 200px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

.header-tip {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.filter-card,
.table-card,
.stat-card,
.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.6fr 180px 220px auto;
  gap: 12px;
  align-items: center;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.stat-card strong {
  color: var(--theme-text);
  font-size: 30px;
  line-height: 1;
}

.stat-desc {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.name-cell,
.meta-stack,
.stats-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-cell strong,
.meta-stack span,
.stats-cell span {
  color: var(--theme-text);
}

.name-cell span,
.meta-stack small,
.stats-cell small {
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.progress-cell {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.progress-head span {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(var(--theme-accent-rgb), 0.08);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.2s ease;
}

.success-text {
  color: #4caf50 !important;
}

.danger-text {
  color: #f44336 !important;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.detail-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-label {
  display: block;
  margin-bottom: 8px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.detail-card strong {
  color: var(--theme-text);
  font-size: 18px;
}

.summary-text {
  color: var(--theme-text);
  line-height: 1.7;
  margin-bottom: 14px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-bottom: 14px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.metric-chip {
  padding: 10px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.success-chip {
  background: rgba(76, 175, 80, 0.12);
  color: #4caf50;
}

.danger-chip {
  background: rgba(244, 67, 54, 0.12);
  color: #f44336;
}

.neutral-chip {
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: var(--theme-text);
}

.detail-alert {
  margin-top: 14px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-item {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.log-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.log-message {
  color: var(--theme-text);
  line-height: 1.7;
  word-break: break-word;
}

@media (max-width: 1280px) {
  .filter-grid,
  .stats-grid,
  .detail-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-grid,
  .stats-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions,
  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
