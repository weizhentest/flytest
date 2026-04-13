<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再查看 APP 自动化执行报告" />
    </div>
    <template v-else>
      <ReportsHeaderBar :loading="loading" :last-updated-text="lastUpdatedText" @refresh="loadData" />

      <a-tabs v-model:active-key="activeTab">
        <a-tab-pane key="suite" title="套件报告">
          <ReportsSuitePanel
            :loading="loading"
            :filters="suiteFilters"
            :pagination="suitePagination"
            :statistics="suiteStats"
            :suites="pagedSuites"
            :total="filteredSuites.length"
            :format-date-time="formatDateTime"
            :get-suite-status="getSuiteStatus"
            :get-suite-health-rate="getSuiteHealthRate"
            @search="handleSuiteSearch"
            @reset="resetSuiteFilters"
            @open-detail="openSuiteDetail"
            @open-executions="openSuiteExecutions"
            @open-report="openSuiteReport"
          />
        </a-tab-pane>

        <a-tab-pane key="case" title="执行明细">
          <ReportsExecutionPanel
            :loading="loading"
            :filters="caseFilters"
            :pagination="casePagination"
            :statistics="caseStats"
            :executions="pagedExecutions"
            :total="filteredExecutions.length"
            :format-date-time="formatDateTime"
            :format-rate="formatRate"
            :format-duration="formatDuration"
            :get-execution-source="getExecutionSource"
            :get-execution-status="getExecutionStatus"
            :can-open-report="canOpenReport"
            @search="handleCaseSearch"
            @reset="resetCaseFilters"
            @open-detail="openExecutionDetail"
            @open-report="openExecutionReport"
          />
        </a-tab-pane>
      </a-tabs>

      <a-modal v-model:visible="suiteDetailVisible" title="套件详情" width="880px" :footer="false">
        <div v-if="selectedSuite" class="detail-shell">
          <div class="detail-grid">
            <div class="detail-card">
              <span class="detail-label">最近状态</span>
              <strong>{{ getSuiteStatus(selectedSuite).label }}</strong>
            </div>
            <div class="detail-card">
              <span class="detail-label">套件用例数</span>
              <strong>{{ selectedSuite.test_case_count || 0 }}</strong>
            </div>
            <div class="detail-card">
              <span class="detail-label">平均健康度</span>
              <strong>{{ getSuiteHealthRate(selectedSuite) }}%</strong>
            </div>
            <div class="detail-card">
              <span class="detail-label">最近执行</span>
              <strong>{{ formatDateTime(selectedSuite.last_run_at) }}</strong>
            </div>
          </div>

          <a-card class="detail-panel" title="套件说明">
            <div class="summary-text">{{ selectedSuite.description || '暂无套件说明。' }}</div>
            <div class="meta-row">
              <span>创建人：{{ selectedSuite.created_by || '-' }}</span>
              <span>创建时间：{{ formatDateTime(selectedSuite.created_at) }}</span>
              <span>更新时间：{{ formatDateTime(selectedSuite.updated_at) }}</span>
            </div>
          </a-card>

          <a-card class="detail-panel" title="套件用例清单">
            <div v-if="selectedSuite.suite_cases?.length" class="case-list">
              <div v-for="item in selectedSuite.suite_cases" :key="item.id" class="case-item">
                <strong>#{{ item.order }} {{ item.test_case.name }}</strong>
                <span>{{ item.test_case.description || '暂无用例描述' }}</span>
                <small>应用包：{{ item.test_case.package_name || '-' }}</small>
              </div>
            </div>
            <div v-else class="empty-note">该套件暂未配置用例</div>
          </a-card>
        </div>
      </a-modal>

      <a-modal
        v-model:visible="suiteExecutionsVisible"
        :title="selectedSuite ? `${selectedSuite.name} 执行记录` : '套件执行记录'"
        width="980px"
        :footer="false"
      >
        <a-table :data="suiteExecutions" :loading="suiteExecutionsLoading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="测试用例" data-index="case_name" />
            <a-table-column title="设备" data-index="device_name" />
            <a-table-column title="状态">
              <template #cell="{ record }">
                <a-tag :color="getExecutionStatus(record).color">{{ getExecutionStatus(record).label }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="通过率">
              <template #cell="{ record }">{{ formatRate(record.pass_rate) }}%</template>
            </a-table-column>
            <a-table-column title="操作" :width="180">
              <template #cell="{ record }">
                <a-space wrap>
                  <a-button type="text" @click="openExecutionDetail(record.id)">详情</a-button>
                  <a-button v-if="canOpenReport(record)" type="text" @click="openExecutionReport(record)">报告</a-button>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-modal>

      <a-modal v-model:visible="executionDetailVisible" title="执行详情" width="960px" :footer="false">
        <div v-if="currentExecution" class="detail-shell">
          <div class="detail-grid">
            <div class="detail-card">
              <span class="detail-label">执行状态</span>
              <strong>{{ getExecutionStatus(currentExecution).label }}</strong>
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
              {{ currentExecution.report_summary || currentExecution.error_message || '暂无执行摘要。' }}
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
              <a-button v-if="canOpenReport(currentExecution)" type="primary" @click="openExecutionReport(currentExecution)">
                打开执行报告
              </a-button>
            </a-space>
          </a-card>

          <a-card class="detail-panel" title="步骤统计">
            <div class="metric-row">
              <div class="metric-chip success-chip">通过 {{ currentExecution.passed_steps || 0 }}</div>
              <div class="metric-chip danger-chip">失败 {{ currentExecution.failed_steps || 0 }}</div>
              <div class="metric-chip neutral-chip">总计 {{ currentExecution.total_steps || 0 }}</div>
              <div class="metric-chip neutral-chip">进度 {{ formatRate(currentExecution.progress) }}%</div>
            </div>
            <a-alert v-if="currentExecution.error_message" type="error" class="detail-alert">
              {{ currentExecution.error_message }}
            </a-alert>
          </a-card>

          <a-card class="detail-panel" title="执行证据">
            <div v-if="executionArtifacts.length" class="artifact-list">
              <div v-for="item in executionArtifacts" :key="item.key" class="artifact-item">
                <div class="artifact-meta">
                  <a-tag :color="item.level === 'error' ? 'red' : item.level === 'warning' ? 'orange' : 'arcoblue'">
                    {{ item.level }}
                  </a-tag>
                  <span>{{ item.message }}</span>
                </div>
                <a-button type="text" @click="openExecutionArtifact(currentExecution, item.relativePath)">查看文件</a-button>
              </div>
            </div>
            <div v-else class="empty-note compact">当前执行暂无可查看的证据文件</div>
          </a-card>

          <a-card class="detail-panel" title="执行日志">
            <a-textarea
              :model-value="executionLogText"
              :auto-size="{ minRows: 12, maxRows: 20 }"
              readonly
            />
          </a-card>
        </div>
      </a-modal>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppExecution, AppTestSuite } from '../types'
import ReportsExecutionPanel from './reports/ReportsExecutionPanel.vue'
import ReportsHeaderBar from './reports/ReportsHeaderBar.vue'
import ReportsSuitePanel from './reports/ReportsSuitePanel.vue'

const projectStore = useProjectStore()
const route = useRoute()
const router = useRouter()

const activeTab = ref<'suite' | 'case'>('suite')
const loading = ref(false)
const suites = ref<AppTestSuite[]>([])
const executions = ref<AppExecution[]>([])
const selectedSuite = ref<AppTestSuite | null>(null)
const suiteExecutions = ref<AppExecution[]>([])
const suiteExecutionsVisible = ref(false)
const suiteExecutionsLoading = ref(false)
const suiteDetailVisible = ref(false)
const executionDetailVisible = ref(false)
const currentExecution = ref<AppExecution | null>(null)
const lastUpdatedAt = ref<string | null>(null)

const suiteFilters = reactive({
  search: '',
  status: '',
})

const caseFilters = reactive({
  search: '',
  status: '',
  source: 'all',
})

const suitePagination = reactive({
  current: 1,
  pageSize: 10,
})

const casePagination = reactive({
  current: 1,
  pageSize: 10,
})

const suiteNameMap = computed<Record<number, string>>(() =>
  suites.value.reduce<Record<number, string>>((result, item) => {
    result[item.id] = item.name
    return result
  }, {}),
)

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const formatRate = (value?: number | null) => Math.round(Number(value || 0) * 10) / 10

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

const resolveArtifactRelativePath = (artifact?: string | null) => {
  const value = String(artifact || '').trim()
  if (!value) return ''
  if (value.startsWith('http://') || value.startsWith('https://') || value.startsWith('data:')) {
    return value
  }

  const normalized = value.replace(/\\/g, '/')
  const marker = '/artifacts/'
  const index = normalized.lastIndexOf(marker)
  if (index >= 0) {
    return normalized.slice(index + 1)
  }
  if (normalized.startsWith('artifacts/')) {
    return normalized
  }
  return normalized
}

const getSuiteState = (suite: AppTestSuite) => {
  if (suite.execution_status === 'running') return 'running'
  if (!suite.last_run_at) return 'not_run'
  if (suite.execution_result === 'passed') return 'passed'
  if (suite.execution_result === 'failed') return 'failed'
  if (suite.execution_result === 'stopped') return 'stopped'
  return 'not_run'
}

const getSuiteStatus = (suite: AppTestSuite) => {
  const state = getSuiteState(suite)
  if (state === 'running') return { label: '执行中', color: 'arcoblue' }
  if (state === 'passed') return { label: '执行通过', color: 'green' }
  if (state === 'failed') return { label: '执行失败', color: 'red' }
  if (state === 'stopped') return { label: '已停止', color: 'orange' }
  return { label: '未执行', color: 'gray' }
}

const getExecutionState = (record: AppExecution) => {
  if (record.result === 'passed') return 'passed'
  if (record.result === 'failed' || record.status === 'failed') return 'failed'
  if (record.result === 'stopped' || record.status === 'stopped') return 'stopped'
  if (record.status === 'running') return 'running'
  if (record.status === 'pending') return 'pending'
  return 'unknown'
}

const getExecutionStatus = (record: AppExecution) => {
  const state = getExecutionState(record)
  if (state === 'running') return { label: '执行中', color: 'arcoblue' }
  if (state === 'pending') return { label: '等待执行', color: 'gold' }
  if (state === 'passed') return { label: '执行通过', color: 'green' }
  if (state === 'failed') return { label: '执行失败', color: 'red' }
  if (state === 'stopped') return { label: '已停止', color: 'orange' }
  return { label: record.result || record.status || '未知', color: 'gray' }
}

const getSuiteHealthRate = (suite: AppTestSuite) => {
  const passed = Number(suite.passed_count || 0)
  const failed = Number(suite.failed_count || 0)
  const stopped = Number(suite.stopped_count || 0)
  const total = passed + failed + stopped
  return total ? Math.round((passed / total) * 1000) / 10 : 0
}

const getExecutionSource = (record: AppExecution) =>
  record.test_suite_id ? suiteNameMap.value[record.test_suite_id] || `套件 #${record.test_suite_id}` : '独立执行'

const canOpenReport = (record: AppExecution) =>
  Boolean(record.report_path) ||
  ['completed', 'failed', 'stopped'].includes(record.status) ||
  ['passed', 'failed', 'stopped'].includes(record.result)

const filteredSuites = computed(() => {
  const keyword = suiteFilters.search.trim().toLowerCase()
  return [...suites.value]
    .filter(item => {
      if (suiteFilters.status && getSuiteState(item) !== suiteFilters.status) return false
      if (!keyword) return true
      return [item.name, item.description, item.created_by].join(' ').toLowerCase().includes(keyword)
    })
    .sort((left, right) => new Date(right.last_run_at || right.updated_at).getTime() - new Date(left.last_run_at || left.updated_at).getTime())
})

const filteredExecutions = computed(() => {
  const keyword = caseFilters.search.trim().toLowerCase()
  return [...executions.value]
    .filter(item => {
      if (caseFilters.status && getExecutionState(item) !== caseFilters.status) return false
      if (caseFilters.source === 'suite' && !item.test_suite_id) return false
      if (caseFilters.source === 'standalone' && item.test_suite_id) return false
      if (!keyword) return true

      return [
        item.case_name,
        item.device_name,
        item.device_serial,
        item.triggered_by,
        getExecutionSource(item),
        item.error_message,
      ]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    })
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
})

const pagedSuites = computed(() => {
  const start = (suitePagination.current - 1) * suitePagination.pageSize
  return filteredSuites.value.slice(start, start + suitePagination.pageSize)
})

const pagedExecutions = computed(() => {
  const start = (casePagination.current - 1) * casePagination.pageSize
  return filteredExecutions.value.slice(start, start + casePagination.pageSize)
})

const suiteStats = computed(() => ({
  total: filteredSuites.value.length,
  running: filteredSuites.value.filter(item => getSuiteState(item) === 'running').length,
  passed: filteredSuites.value.filter(item => getSuiteState(item) === 'passed').length,
  health: filteredSuites.value.length
    ? Math.round((filteredSuites.value.reduce((sum, item) => sum + getSuiteHealthRate(item), 0) / filteredSuites.value.length) * 10) / 10
    : 0,
}))

const caseStats = computed(() => ({
  total: filteredExecutions.value.length,
  passed: filteredExecutions.value.filter(item => getExecutionState(item) === 'passed').length,
  failed: filteredExecutions.value.filter(item => getExecutionState(item) === 'failed').length,
  passRate: filteredExecutions.value.length
    ? Math.round((filteredExecutions.value.reduce((sum, item) => sum + Number(item.pass_rate || 0), 0) / filteredExecutions.value.length) * 10) / 10
    : 0,
}))

const lastUpdatedText = computed(() => (lastUpdatedAt.value ? formatDateTime(lastUpdatedAt.value) : '-'))

const executionArtifacts = computed(() => {
  if (!currentExecution.value?.logs?.length) return []

  const seen = new Set<string>()
  return currentExecution.value.logs
    .map((item, index) => {
      const relativePath = resolveArtifactRelativePath(item.artifact)
      if (!relativePath || seen.has(relativePath)) return null

      seen.add(relativePath)
      return {
        key: `${relativePath}-${index}`,
        relativePath,
        message: item.message || '执行证据',
        level: item.level || 'info',
      }
    })
    .filter(Boolean) as Array<{ key: string; relativePath: string; message: string; level: string }>
})

const executionLogText = computed(() =>
  currentExecution.value?.logs?.length
    ? currentExecution.value.logs.map(item => `[${item.level || 'info'}] ${item.timestamp || '-'} ${item.message || ''}`.trim()).join('\n')
    : '暂无执行日志',
)

const replaceRouteQuery = async (patch: Record<string, string | undefined>) => {
  const nextQuery: LocationQueryRaw = { ...route.query }

  Object.entries(patch).forEach(([key, value]) => {
    if (value === undefined || value === '') {
      delete nextQuery[key]
    } else {
      nextQuery[key] = value
    }
  })

  const keys = new Set([...Object.keys(route.query), ...Object.keys(nextQuery)])
  const changed = [...keys].some(key => {
    const currentValue = route.query[key]
    const nextValue = nextQuery[key]
    const currentText = Array.isArray(currentValue) ? String(currentValue[0] ?? '') : String(currentValue ?? '')
    const nextText = Array.isArray(nextValue) ? String(nextValue[0] ?? '') : String(nextValue ?? '')
    return currentText !== nextText
  })

  if (!changed) return

  await router.replace({
    path: '/app-automation',
    query: nextQuery,
  })
}

const loadData = async () => {
  if (!projectStore.currentProjectId) {
    suites.value = []
    executions.value = []
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

    await syncRouteContext()
  } catch (error: any) {
    Message.error(error.message || '加载执行报告失败')
  } finally {
    loading.value = false
  }
}

const handleSuiteSearch = () => {
  suitePagination.current = 1
}

const handleCaseSearch = () => {
  casePagination.current = 1
}

const resetSuiteFilters = () => {
  suiteFilters.search = ''
  suiteFilters.status = ''
  suitePagination.current = 1
}

const resetCaseFilters = () => {
  caseFilters.search = ''
  caseFilters.status = ''
  caseFilters.source = 'all'
  casePagination.current = 1
}

const openSuiteDetail = async (suite: AppTestSuite, options: { syncRoute?: boolean } = {}) => {
  selectedSuite.value = suite
  suiteDetailVisible.value = true
  activeTab.value = 'suite'

  if (options.syncRoute !== false) {
    await replaceRouteQuery({
      tab: 'reports',
      reportMode: 'suite',
      suiteId: String(suite.id),
      executionId: undefined,
    })
  }
}

const openSuiteExecutions = async (suite: AppTestSuite) => {
  selectedSuite.value = suite
  suiteExecutionsVisible.value = true
  suiteExecutionsLoading.value = true

  try {
    suiteExecutions.value = await AppAutomationService.getTestSuiteExecutions(suite.id)
  } catch (error: any) {
    Message.error(error.message || '加载套件执行记录失败')
  } finally {
    suiteExecutionsLoading.value = false
  }
}

const openExecutionDetail = async (id: number, options: { syncRoute?: boolean } = {}) => {
  try {
    currentExecution.value = await AppAutomationService.getExecutionDetail(id)
    executionDetailVisible.value = true
    activeTab.value = 'case'

    if (options.syncRoute !== false) {
      await replaceRouteQuery({
        tab: 'reports',
        reportMode: 'case',
        executionId: String(id),
        suiteId: undefined,
      })
    }
  } catch (error: any) {
    Message.error(error.message || '加载执行详情失败')
  }
}

const openExecutionReport = (record: AppExecution) => {
  window.open(AppAutomationService.getExecutionReportUrl(record.id), '_blank', 'noopener')
}

const openExecutionArtifact = (record: AppExecution, relativePath: string) => {
  if (!relativePath) return

  if (relativePath.startsWith('http://') || relativePath.startsWith('https://') || relativePath.startsWith('data:')) {
    window.open(relativePath, '_blank', 'noopener')
    return
  }

  window.open(AppAutomationService.getExecutionReportAssetUrl(record.id, relativePath), '_blank', 'noopener')
}

const openSuiteReport = async (suite: AppTestSuite) => {
  try {
    const records = await AppAutomationService.getTestSuiteExecutions(suite.id)
    const target = records.find(item => canOpenReport(item))
    if (!target) {
      Message.warning('该套件暂无可打开的执行报告')
      return
    }
    openExecutionReport(target)
  } catch (error: any) {
    Message.error(error.message || '打开套件报告失败')
  }
}

const syncRouteContext = async () => {
  if (route.query.tab !== 'reports' || !projectStore.currentProjectId) {
    return
  }

  const routeMode = String(route.query.reportMode || '')
  const suiteId = Number(route.query.suiteId || 0)
  const executionId = Number(route.query.executionId || 0)

  if (routeMode === 'case' || executionId > 0) {
    activeTab.value = 'case'
  } else {
    activeTab.value = 'suite'
  }

  if (suiteId > 0) {
    const suite = suites.value.find(item => item.id === suiteId)
    if (suite && (!suiteDetailVisible.value || selectedSuite.value?.id !== suiteId)) {
      await openSuiteDetail(suite, { syncRoute: false })
    }
  }

  if (executionId > 0 && (!executionDetailVisible.value || currentExecution.value?.id !== executionId)) {
    await openExecutionDetail(executionId, { syncRoute: false })
  }
}

watch(
  () => filteredSuites.value.length,
  total => {
    const maxPage = Math.max(1, Math.ceil(total / suitePagination.pageSize))
    if (suitePagination.current > maxPage) {
      suitePagination.current = maxPage
    }
  },
)

watch(
  () => filteredExecutions.value.length,
  total => {
    const maxPage = Math.max(1, Math.ceil(total / casePagination.pageSize))
    if (casePagination.current > maxPage) {
      casePagination.current = maxPage
    }
  },
)

watch(
  () => suitePagination.pageSize,
  () => {
    suitePagination.current = 1
  },
)

watch(
  () => casePagination.pageSize,
  () => {
    casePagination.current = 1
  },
)

watch(
  () => suiteDetailVisible.value,
  value => {
    if (!value && route.query.tab === 'reports' && route.query.suiteId) {
      void replaceRouteQuery({ suiteId: undefined })
    }
  },
)

watch(
  () => executionDetailVisible.value,
  value => {
    if (!value && route.query.tab === 'reports' && route.query.executionId) {
      void replaceRouteQuery({ executionId: undefined })
    }
  },
)

watch(
  () => [route.query.tab, route.query.reportMode, route.query.suiteId, route.query.executionId, projectStore.currentProjectId],
  () => {
    void syncRouteContext()
  },
)

watch(
  () => projectStore.currentProjectId,
  () => {
    activeTab.value = 'suite'
    suitePagination.current = 1
    casePagination.current = 1
    suiteDetailVisible.value = false
    suiteExecutionsVisible.value = false
    executionDetailVisible.value = false
    selectedSuite.value = null
    currentExecution.value = null
    suiteExecutions.value = []
    void loadData()
  },
  { immediate: true },
)
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-shell,
.case-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-shell,
.empty-note {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-secondary);
}

.empty-shell {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}

.empty-note.compact {
  min-height: 0;
  justify-content: flex-start;
}

.meta-row,
.detail-label,
.case-item span,
.case-item small {
  color: var(--theme-text-secondary);
}

.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-card strong,
.case-item strong {
  color: var(--theme-text);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-card,
.case-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
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

.artifact-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.artifact-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.artifact-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--theme-text);
}

.case-list {
  gap: 10px;
}

@media (max-width: 1280px) {
  .detail-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions,
  .pagination-row,
  .artifact-item {
    justify-content: flex-start;
  }

  .artifact-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
