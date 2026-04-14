import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import {
  openExecutionArtifactWindow,
  openExecutionReportWindow,
  replaceAppAutomationQuery,
} from '../appAutomationNavigation'
import type { AppExecution, AppTestSuite } from '../../types'
import type {
  ReportCaseFilters,
  ReportCaseStats,
  ReportExecutionArtifact,
  ReportPaginationState,
  ReportStatusMeta,
  ReportSuiteFilters,
  ReportSuiteStats,
} from './reportViewModels'

export function useAppAutomationReports() {
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

  const suiteFilters = reactive<ReportSuiteFilters>({
    search: '',
    status: '',
  })

  const caseFilters = reactive<ReportCaseFilters>({
    search: '',
    status: '',
    source: 'all',
  })

  const suitePagination = reactive<ReportPaginationState>({
    current: 1,
    pageSize: 10,
  })

  const casePagination = reactive<ReportPaginationState>({
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
    if (
      value.startsWith('http://') ||
      value.startsWith('https://') ||
      value.startsWith('data:')
    ) {
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

  const getSuiteStatus = (suite: AppTestSuite): ReportStatusMeta => {
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

  const getExecutionStatus = (record: AppExecution): ReportStatusMeta => {
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
    record.test_suite_id
      ? suiteNameMap.value[record.test_suite_id] || `套件 #${record.test_suite_id}`
      : '独立执行'

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
        return [item.name, item.description, item.created_by]
          .join(' ')
          .toLowerCase()
          .includes(keyword)
      })
      .sort(
        (left, right) =>
          new Date(right.last_run_at || right.updated_at).getTime() -
          new Date(left.last_run_at || left.updated_at).getTime(),
      )
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
      .sort(
        (left, right) =>
          new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
      )
  })

  const pagedSuites = computed(() => {
    const start = (suitePagination.current - 1) * suitePagination.pageSize
    return filteredSuites.value.slice(start, start + suitePagination.pageSize)
  })

  const pagedExecutions = computed(() => {
    const start = (casePagination.current - 1) * casePagination.pageSize
    return filteredExecutions.value.slice(start, start + casePagination.pageSize)
  })

  const suiteStats = computed<ReportSuiteStats>(() => ({
    total: filteredSuites.value.length,
    running: filteredSuites.value.filter(item => getSuiteState(item) === 'running').length,
    passed: filteredSuites.value.filter(item => getSuiteState(item) === 'passed').length,
    health: filteredSuites.value.length
      ? Math.round(
          (filteredSuites.value.reduce((sum, item) => sum + getSuiteHealthRate(item), 0) /
            filteredSuites.value.length) *
            10,
        ) / 10
      : 0,
  }))

  const caseStats = computed<ReportCaseStats>(() => ({
    total: filteredExecutions.value.length,
    passed: filteredExecutions.value.filter(item => getExecutionState(item) === 'passed').length,
    failed: filteredExecutions.value.filter(item => getExecutionState(item) === 'failed').length,
    passRate: filteredExecutions.value.length
      ? Math.round(
          (filteredExecutions.value.reduce((sum, item) => sum + Number(item.pass_rate || 0), 0) /
            filteredExecutions.value.length) *
            10,
        ) / 10
      : 0,
  }))

  const lastUpdatedText = computed(() =>
    lastUpdatedAt.value ? formatDateTime(lastUpdatedAt.value) : '-',
  )

  const executionArtifacts = computed<ReportExecutionArtifact[]>(() => {
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
      .filter(Boolean) as ReportExecutionArtifact[]
  })

  const executionLogText = computed(() =>
    currentExecution.value?.logs?.length
      ? currentExecution.value.logs
          .map(item =>
            `[${item.level || 'info'}] ${item.timestamp || '-'} ${item.message || ''}`.trim(),
          )
          .join('\n')
      : '暂无执行日志',
  )

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

  const openSuiteDetail = async (
    suite: AppTestSuite,
    options: { syncRoute?: boolean } = {},
  ) => {
    selectedSuite.value = suite
    suiteDetailVisible.value = true
    activeTab.value = 'suite'

      if (options.syncRoute !== false) {
        await replaceAppAutomationQuery(route, router, {
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
        await replaceAppAutomationQuery(route, router, {
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
    openExecutionReportWindow(record.id)
  }

  const openExecutionArtifact = (record: AppExecution, relativePath: string) => {
    openExecutionArtifactWindow(record.id, relativePath)
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

    if (
      executionId > 0 &&
      (!executionDetailVisible.value || currentExecution.value?.id !== executionId)
    ) {
      await openExecutionDetail(executionId, { syncRoute: false })
    }
  }

  watch(
    () => route.query.tab,
    tab => {
      if (tab === 'reports') {
        return
      }
      suiteDetailVisible.value = false
      suiteExecutionsVisible.value = false
      executionDetailVisible.value = false
    },
  )

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
        void replaceAppAutomationQuery(route, router, { suiteId: undefined })
      }
      if (!value && !suiteExecutionsVisible.value) {
        selectedSuite.value = null
      }
    },
  )

  watch(
    () => executionDetailVisible.value,
    value => {
      if (!value && route.query.tab === 'reports' && route.query.executionId) {
        void replaceAppAutomationQuery(route, router, { executionId: undefined })
      }
      if (!value) {
        currentExecution.value = null
      }
    },
  )

  watch(
    () => suiteExecutionsVisible.value,
    value => {
      if (!value) {
        suiteExecutions.value = []
        suiteExecutionsLoading.value = false
        if (!suiteDetailVisible.value) {
          selectedSuite.value = null
        }
      }
    },
  )

  watch(
    () => [
      route.query.tab,
      route.query.reportMode,
      route.query.suiteId,
      route.query.executionId,
      projectStore.currentProjectId,
    ],
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

  return {
    projectStore,
    activeTab,
    loading,
    suites,
    executions,
    selectedSuite,
    suiteExecutions,
    suiteExecutionsVisible,
    suiteExecutionsLoading,
    suiteDetailVisible,
    executionDetailVisible,
    currentExecution,
    suiteFilters,
    caseFilters,
    suitePagination,
    casePagination,
    formatDateTime,
    formatRate,
    formatDuration,
    getSuiteStatus,
    getExecutionStatus,
    getSuiteHealthRate,
    getExecutionSource,
    canOpenReport,
    filteredSuites,
    filteredExecutions,
    pagedSuites,
    pagedExecutions,
    suiteStats,
    caseStats,
    lastUpdatedText,
    executionArtifacts,
    executionLogText,
    loadData,
    handleSuiteSearch,
    handleCaseSearch,
    resetSuiteFilters,
    resetCaseFilters,
    openSuiteDetail,
    openSuiteExecutions,
    openExecutionDetail,
    openExecutionReport,
    openExecutionArtifact,
    openSuiteReport,
  }
}
