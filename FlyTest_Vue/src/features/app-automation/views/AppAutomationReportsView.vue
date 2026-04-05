<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再查看 APP 自动化执行报告" />
    </div>
    <template v-else>
      <div class="page-header">
        <div>
          <h3>执行报告</h3>
          <p>从套件和执行明细两个维度查看 APP 自动化结果，支持筛选、分页、详情钻取和报告入口。</p>
        </div>
        <a-space>
          <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
          <a-button @click="loadData" :loading="loading">刷新</a-button>
        </a-space>
      </div>

      <a-tabs v-model:active-key="activeTab">
        <a-tab-pane key="suite" title="套件报告">
          <a-card class="filter-card">
            <div class="filter-grid">
              <a-input-search
                v-model="suiteFilters.search"
                allow-clear
                placeholder="搜索套件名称、描述或创建人"
                @search="handleSuiteSearch"
              />
              <a-select v-model="suiteFilters.status" placeholder="最近状态">
                <a-option value="">全部状态</a-option>
                <a-option value="not_run">未执行</a-option>
                <a-option value="running">执行中</a-option>
                <a-option value="passed">执行通过</a-option>
                <a-option value="failed">执行失败</a-option>
              </a-select>
              <div class="filter-actions">
                <a-button @click="resetSuiteFilters">重置</a-button>
                <a-button type="primary" @click="handleSuiteSearch">查询</a-button>
              </div>
            </div>
          </a-card>

          <div class="stats-grid">
            <a-card class="stat-card"><span class="stat-label">套件总数</span><strong>{{ suiteStats.total }}</strong></a-card>
            <a-card class="stat-card"><span class="stat-label">运行中</span><strong>{{ suiteStats.running }}</strong></a-card>
            <a-card class="stat-card"><span class="stat-label">通过套件</span><strong>{{ suiteStats.passed }}</strong></a-card>
            <a-card class="stat-card"><span class="stat-label">平均健康度</span><strong>{{ suiteStats.health }}%</strong></a-card>
          </div>

          <a-card class="table-card">
            <a-table :data="pagedSuites" :loading="loading" :pagination="false" row-key="id">
              <template #columns>
                <a-table-column title="套件 / 描述" :width="280">
                  <template #cell="{ record }">
                    <div class="stack">
                      <strong>{{ record.name }}</strong>
                      <span>{{ record.description || '暂无套件描述' }}</span>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="状态 / 健康度" :width="220">
                  <template #cell="{ record }">
                    <div class="stack">
                      <a-tag :color="getSuiteStatus(record).color">{{ getSuiteStatus(record).label }}</a-tag>
                      <small>健康度 {{ getSuiteHealthRate(record) }}%</small>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="用例 / 结果" :width="220">
                  <template #cell="{ record }">
                    <div class="stack">
                      <span>用例数 {{ record.test_case_count || 0 }}</span>
                      <small>通过 {{ record.passed_count || 0 }} / 失败 {{ record.failed_count || 0 }}</small>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="最近执行" :width="180">
                  <template #cell="{ record }">{{ formatDateTime(record.last_run_at) }}</template>
                </a-table-column>
                <a-table-column title="操作" :width="220" fixed="right">
                  <template #cell="{ record }">
                    <a-space wrap>
                      <a-button type="text" @click="openSuiteDetail(record)">详情</a-button>
                      <a-button type="text" @click="openSuiteExecutions(record)">执行记录</a-button>
                      <a-button type="text" @click="openSuiteReport(record)">报告</a-button>
                    </a-space>
                  </template>
                </a-table-column>
              </template>
            </a-table>
            <div class="pagination-row">
              <a-pagination
                v-model:current="suitePagination.current"
                v-model:page-size="suitePagination.pageSize"
                :total="filteredSuites.length"
                :show-total="true"
                :show-jumper="true"
                :show-page-size="true"
                :page-size-options="['10', '20', '50']"
              />
            </div>
          </a-card>
        </a-tab-pane>

        <a-tab-pane key="case" title="执行明细">
          <a-card class="filter-card">
            <div class="filter-grid case-filter-grid">
              <a-input-search
                v-model="caseFilters.search"
                allow-clear
                placeholder="搜索用例、设备、触发人或套件"
                @search="handleCaseSearch"
              />
              <a-select v-model="caseFilters.status" placeholder="执行状态">
                <a-option value="">全部状态</a-option>
                <a-option value="pending">等待执行</a-option>
                <a-option value="running">执行中</a-option>
                <a-option value="passed">执行通过</a-option>
                <a-option value="failed">执行失败</a-option>
                <a-option value="stopped">已停止</a-option>
              </a-select>
              <a-select v-model="caseFilters.source" placeholder="执行来源">
                <a-option value="all">全部来源</a-option>
                <a-option value="suite">套件执行</a-option>
                <a-option value="standalone">独立执行</a-option>
              </a-select>
              <div class="filter-actions">
                <a-button @click="resetCaseFilters">重置</a-button>
                <a-button type="primary" @click="handleCaseSearch">查询</a-button>
              </div>
            </div>
          </a-card>

          <div class="stats-grid">
            <a-card class="stat-card"><span class="stat-label">执行记录</span><strong>{{ caseStats.total }}</strong></a-card>
            <a-card class="stat-card"><span class="stat-label">通过记录</span><strong>{{ caseStats.passed }}</strong></a-card>
            <a-card class="stat-card"><span class="stat-label">失败记录</span><strong>{{ caseStats.failed }}</strong></a-card>
            <a-card class="stat-card"><span class="stat-label">平均通过率</span><strong>{{ caseStats.passRate }}%</strong></a-card>
          </div>

          <a-card class="table-card">
            <a-table :data="pagedExecutions" :loading="loading" :pagination="false" row-key="id">
              <template #columns>
                <a-table-column title="用例 / 设备" :width="260">
                  <template #cell="{ record }">
                    <div class="stack">
                      <strong>{{ record.case_name || `执行 #${record.id}` }}</strong>
                      <span>{{ record.device_name || record.device_serial || '未绑定设备' }}</span>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="执行来源" :width="220">
                  <template #cell="{ record }">
                    <div class="stack">
                      <a-tag :color="record.test_suite_id ? 'green' : 'arcoblue'">
                        {{ record.test_suite_id ? '套件执行' : '独立执行' }}
                      </a-tag>
                      <small>{{ getExecutionSource(record) }}</small>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="状态 / 通过率" :width="220">
                  <template #cell="{ record }">
                    <div class="stack">
                      <a-tag :color="getExecutionStatus(record).color">{{ getExecutionStatus(record).label }}</a-tag>
                      <small>通过率 {{ formatRate(record.pass_rate) }}%</small>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="时间 / 耗时" :width="220">
                  <template #cell="{ record }">
                    <div class="stack">
                      <span>{{ formatDateTime(record.started_at || record.created_at) }}</span>
                      <small>耗时 {{ formatDuration(record.duration) }}</small>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="操作" :width="180" fixed="right">
                  <template #cell="{ record }">
                    <a-space wrap>
                      <a-button type="text" @click="openExecutionDetail(record.id)">详情</a-button>
                      <a-button v-if="canOpenReport(record)" type="text" @click="openExecutionReport(record)">报告</a-button>
                    </a-space>
                  </template>
                </a-table-column>
              </template>
            </a-table>
            <div class="pagination-row">
              <a-pagination
                v-model:current="casePagination.current"
                v-model:page-size="casePagination.pageSize"
                :total="filteredExecutions.length"
                :show-total="true"
                :show-jumper="true"
                :show-page-size="true"
                :page-size-options="['10', '20', '50']"
              />
            </div>
          </a-card>
        </a-tab-pane>
      </a-tabs>

      <a-modal v-model:visible="suiteDetailVisible" title="套件详情" width="860px" :footer="false">
        <div v-if="selectedSuite" class="detail-shell">
          <div class="detail-grid">
            <div class="detail-card"><span class="detail-label">最近状态</span><strong>{{ getSuiteStatus(selectedSuite).label }}</strong></div>
            <div class="detail-card"><span class="detail-label">套件用例数</span><strong>{{ selectedSuite.test_case_count || 0 }}</strong></div>
            <div class="detail-card"><span class="detail-label">平均健康度</span><strong>{{ getSuiteHealthRate(selectedSuite) }}%</strong></div>
            <div class="detail-card"><span class="detail-label">最近执行</span><strong>{{ formatDateTime(selectedSuite.last_run_at) }}</strong></div>
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
            <a-table-column title="用例" data-index="case_name" />
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
                <a-space>
                  <a-button type="text" @click="openExecutionDetail(record.id)">详情</a-button>
                  <a-button v-if="canOpenReport(record)" type="text" @click="openExecutionReport(record)">报告</a-button>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-modal>

      <a-modal v-model:visible="executionDetailVisible" title="执行详情" width="920px" :footer="false">
        <div v-if="currentExecution" class="detail-shell">
          <div class="detail-grid">
            <div class="detail-card"><span class="detail-label">执行状态</span><strong>{{ getExecutionStatus(currentExecution).label }}</strong></div>
            <div class="detail-card"><span class="detail-label">执行来源</span><strong>{{ getExecutionSource(currentExecution) }}</strong></div>
            <div class="detail-card"><span class="detail-label">步骤通过率</span><strong>{{ formatRate(currentExecution.pass_rate) }}%</strong></div>
            <div class="detail-card"><span class="detail-label">执行耗时</span><strong>{{ formatDuration(currentExecution.duration) }}</strong></div>
          </div>
          <a-card class="detail-panel" title="执行摘要">
            <div class="summary-text">{{ currentExecution.report_summary || currentExecution.error_message || '暂无执行摘要。' }}</div>
            <div class="meta-row">
              <span>用例：{{ currentExecution.case_name || `执行 #${currentExecution.id}` }}</span>
              <span>设备：{{ currentExecution.device_name || currentExecution.device_serial || '-' }}</span>
              <span>触发方式：{{ currentExecution.trigger_mode || '-' }}</span>
              <span>触发人：{{ currentExecution.triggered_by || '-' }}</span>
            </div>
            <a-button v-if="canOpenReport(currentExecution)" type="primary" @click="openExecutionReport(currentExecution)">打开执行报告</a-button>
          </a-card>
          <a-card class="detail-panel" title="执行日志">
            <a-alert v-if="currentExecution.error_message" type="error" class="detail-alert">{{ currentExecution.error_message }}</a-alert>
            <a-textarea
              :model-value="currentExecution.logs.map(item => `[${item.level}] ${item.timestamp} ${item.message}`).join('\n')"
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
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppExecution, AppTestSuite } from '../types'

const projectStore = useProjectStore()
const activeTab = ref('suite')
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

const suiteFilters = reactive({ search: '', status: '' })
const caseFilters = reactive({ search: '', status: '', source: 'all' })
const suitePagination = reactive({ current: 1, pageSize: 10 })
const casePagination = reactive({ current: 1, pageSize: 10 })

const suiteNameMap = computed<Record<number, string>>(() =>
  suites.value.reduce<Record<number, string>>((acc, item) => {
    acc[item.id] = item.name
    return acc
  }, {}),
)

const formatDateTime = (value?: string | null) => (value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-')
const formatRate = (value?: number | null) => Math.round(Number(value || 0) * 10) / 10
const formatDuration = (value?: number | null) => {
  const seconds = Number(value || 0)
  if (!seconds) return '-'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  const minutes = Math.floor(seconds / 60)
  return `${minutes} 分 ${Math.round(seconds % 60)} 秒`
}

const getSuiteState = (suite: AppTestSuite) => {
  if (suite.execution_status === 'running') return 'running'
  if (!suite.last_run_at) return 'not_run'
  if (suite.execution_result === 'passed') return 'passed'
  if (suite.execution_result === 'failed') return 'failed'
  return 'not_run'
}

const getSuiteStatus = (suite: AppTestSuite) => {
  const state = getSuiteState(suite)
  if (state === 'running') return { label: '执行中', color: 'arcoblue' }
  if (state === 'passed') return { label: '执行通过', color: 'green' }
  if (state === 'failed') return { label: '执行失败', color: 'red' }
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
  const total = passed + failed
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
    .sort((a, b) => new Date(b.last_run_at || b.updated_at).getTime() - new Date(a.last_run_at || a.updated_at).getTime())
})

const filteredExecutions = computed(() => {
  const keyword = caseFilters.search.trim().toLowerCase()
  return [...executions.value]
    .filter(item => {
      if (caseFilters.status && getExecutionState(item) !== caseFilters.status) return false
      if (caseFilters.source === 'suite' && !item.test_suite_id) return false
      if (caseFilters.source === 'standalone' && item.test_suite_id) return false
      if (!keyword) return true
      return [item.case_name, item.device_name, item.triggered_by, getExecutionSource(item), item.error_message].join(' ').toLowerCase().includes(keyword)
    })
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
})

const pagedSuites = computed(() => filteredSuites.value.slice((suitePagination.current - 1) * suitePagination.pageSize, suitePagination.current * suitePagination.pageSize))
const pagedExecutions = computed(() => filteredExecutions.value.slice((casePagination.current - 1) * casePagination.pageSize, casePagination.current * casePagination.pageSize))

const suiteStats = computed(() => ({
  total: filteredSuites.value.length,
  running: filteredSuites.value.filter(item => getSuiteState(item) === 'running').length,
  passed: filteredSuites.value.filter(item => getSuiteState(item) === 'passed').length,
  health: filteredSuites.value.length ? Math.round((filteredSuites.value.reduce((sum, item) => sum + getSuiteHealthRate(item), 0) / filteredSuites.value.length) * 10) / 10 : 0,
}))

const caseStats = computed(() => ({
  total: filteredExecutions.value.length,
  passed: filteredExecutions.value.filter(item => getExecutionState(item) === 'passed').length,
  failed: filteredExecutions.value.filter(item => getExecutionState(item) === 'failed').length,
  passRate: filteredExecutions.value.length ? Math.round((filteredExecutions.value.reduce((sum, item) => sum + Number(item.pass_rate || 0), 0) / filteredExecutions.value.length) * 10) / 10 : 0,
}))

const lastUpdatedText = computed(() => (lastUpdatedAt.value ? formatDateTime(lastUpdatedAt.value) : '-'))

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
  } catch (error: any) {
    Message.error(error.message || '加载执行报告失败')
  } finally {
    loading.value = false
  }
}

const handleSuiteSearch = () => {
  suitePagination.current = 1
  void loadData()
}

const handleCaseSearch = () => {
  casePagination.current = 1
  void loadData()
}

const resetSuiteFilters = () => {
  suiteFilters.search = ''
  suiteFilters.status = ''
  suitePagination.current = 1
  void loadData()
}

const resetCaseFilters = () => {
  caseFilters.search = ''
  caseFilters.status = ''
  caseFilters.source = 'all'
  casePagination.current = 1
  void loadData()
}

const openSuiteDetail = (suite: AppTestSuite) => {
  selectedSuite.value = suite
  suiteDetailVisible.value = true
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

const openExecutionDetail = async (id: number) => {
  try {
    currentExecution.value = await AppAutomationService.getExecutionDetail(id)
    executionDetailVisible.value = true
  } catch (error: any) {
    Message.error(error.message || '加载执行详情失败')
  }
}

const openExecutionReport = (record: AppExecution) => {
  window.open(AppAutomationService.getExecutionReportUrl(record.id), '_blank', 'noopener')
}

const openSuiteReport = async (suite: AppTestSuite) => {
  try {
    const records = await AppAutomationService.getTestSuiteExecutions(suite.id)
    const target = records.find(item => canOpenReport(item))
    if (!target) return Message.warning('该套件暂无可打开的执行报告')
    openExecutionReport(target)
  } catch (error: any) {
    Message.error(error.message || '打开套件报告失败')
  }
}

watch(
  () => filteredSuites.value.length,
  total => {
    const maxPage = Math.max(1, Math.ceil(total / suitePagination.pageSize))
    if (suitePagination.current > maxPage) suitePagination.current = maxPage
  },
)

watch(
  () => filteredExecutions.value.length,
  total => {
    const maxPage = Math.max(1, Math.ceil(total / casePagination.pageSize))
    if (casePagination.current > maxPage) casePagination.current = maxPage
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
.page-shell,.detail-shell,.stack,.case-list{display:flex;flex-direction:column}
.page-shell,.detail-shell,.stack,.case-list{gap:16px}
.empty-shell,.empty-note{min-height:220px;display:flex;align-items:center;justify-content:center;color:var(--theme-text-secondary)}
.empty-shell{background:var(--theme-card-bg);border:1px solid var(--theme-card-border);border-radius:16px}
.page-header{display:flex;align-items:center;justify-content:space-between;gap:16px}
.page-header h3{margin:0;color:var(--theme-text)}
.page-header p,.header-tip,.stack span,.stack small,.meta-row,.detail-label,.case-item span,.case-item small{color:var(--theme-text-secondary)}
.page-header p{margin:6px 0 0}
.filter-card,.table-card,.stat-card,.detail-panel{border-radius:16px;border:1px solid var(--theme-card-border);background:var(--theme-card-bg);box-shadow:var(--theme-card-shadow)}
.filter-grid{display:grid;grid-template-columns:1.6fr 180px auto;gap:12px;align-items:center}
.case-filter-grid{grid-template-columns:1.5fr 180px 180px auto}
.filter-actions,.pagination-row{display:flex;gap:10px}
.filter-actions,.pagination-row{justify-content:flex-end}
.stats-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:16px 0}
.stat-card :deep(.arco-card-body){display:flex;flex-direction:column;gap:8px}
.stat-label{font-size:13px;color:var(--theme-text-secondary)}
.stat-card strong,.detail-card strong,.case-item strong,.stack strong{color:var(--theme-text)}
.stat-card strong{font-size:30px;line-height:1}
.detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.detail-card,.case-item{padding:16px;border-radius:16px;border:1px solid var(--theme-card-border);background:rgba(var(--theme-accent-rgb),.04)}
.detail-label{display:block;margin-bottom:8px;font-size:13px}
.summary-text{color:var(--theme-text);line-height:1.7;margin-bottom:14px}
.meta-row{display:flex;flex-wrap:wrap;gap:12px 20px;margin-bottom:14px;font-size:13px}
.detail-alert{margin-bottom:12px}
.case-list{gap:10px}
@media (max-width: 1280px){.filter-grid,.case-filter-grid,.stats-grid,.detail-grid{grid-template-columns:1fr 1fr}}
@media (max-width: 900px){.page-header,.filter-grid,.case-filter-grid,.stats-grid,.detail-grid{grid-template-columns:1fr}.page-header{flex-direction:column;align-items:flex-start}.filter-actions,.pagination-row{justify-content:flex-start}}
</style>
