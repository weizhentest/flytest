import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppExecution, AppTestSuite } from '../../types'

interface ExecutionFilters {
  search: string
  status: string
  suite: string
}

interface PaginationState {
  current: number
  pageSize: number
}

interface ExecutionArtifact {
  key: string
  relativePath: string
  message: string
  level: string
}

const statusConfig = {
  pending: { label: '等待执行', color: 'gold', hex: '#ffb400' },
  running: { label: '执行中', color: 'arcoblue', hex: '#165dff' },
  passed: { label: '执行通过', color: 'green', hex: '#00b42a' },
  failed: { label: '执行失败', color: 'red', hex: '#f53f3f' },
  stopped: { label: '已停止', color: 'orange', hex: '#ff7d00' },
  completed: { label: '已完成', color: 'cyan', hex: '#14c9c9' },
  unknown: { label: '未知', color: 'gray', hex: '#86909c' },
} as const

export function useAppAutomationExecutions() {
  const projectStore = useProjectStore()
  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const detailLoading = ref(false)
  const detailVisible = ref(false)
  const lastUpdatedAt = ref<string | null>(null)
  const executions = ref<AppExecution[]>([])
  const suites = ref<AppTestSuite[]>([])
  const currentExecution = ref<AppExecution | null>(null)
  const stoppingIds = reactive<Record<number, boolean>>({})

  const filters = reactive<ExecutionFilters>({
    search: '',
    status: '',
    suite: 'all',
  })

  const pagination = reactive<PaginationState>({
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

  const formatRate = (value?: number | null) => Math.round(Number(value || 0) * 10) / 10

  const formatProgress = (value?: number | null) => {
    const progress = Number(value || 0)
    return Math.max(0, Math.min(100, Math.round(progress)))
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

  const getExecutionState = (record: AppExecution) => {
    if (record.result === 'passed') return 'passed'
    if (record.result === 'failed' || record.status === 'failed') return 'failed'
    if (record.result === 'stopped' || record.status === 'stopped') return 'stopped'
    if (record.status === 'running') return 'running'
    if (record.status === 'pending') return 'pending'
    if (record.status === 'completed') return 'completed'
    return 'unknown'
  }

  const getExecutionStatusMeta = (record: AppExecution) =>
    statusConfig[getExecutionState(record)] || statusConfig.unknown

  const getExecutionSource = (record: AppExecution) => {
    if (!record.test_suite_id) return '独立执行'
    return suiteNameMap.value[record.test_suite_id] || `套件 #${record.test_suite_id}`
  }

  const isExecutionRunning = (record: AppExecution) =>
    ['pending', 'running'].includes(record.status)

  const canOpenReport = (record: AppExecution) =>
    Boolean(record.report_path) ||
    ['completed', 'failed', 'stopped'].includes(record.status) ||
    ['passed', 'failed', 'stopped'].includes(record.result)

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

        if (
          filters.suite !== 'all' &&
          filters.suite !== 'standalone' &&
          record.test_suite_id !== Number(filters.suite)
        ) {
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
      .sort(
        (left, right) =>
          new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
      )
  })

  const pagedExecutions = computed(() => {
    const start = (pagination.current - 1) * pagination.pageSize
    return filteredExecutions.value.slice(start, start + pagination.pageSize)
  })

  const statistics = computed(() => {
    const running = filteredExecutions.value.filter(item => isExecutionRunning(item)).length
    const passed = filteredExecutions.value.filter(
      item => getExecutionState(item) === 'passed',
    ).length
    const averagePassRate = filteredExecutions.value.length
      ? Math.round(
          (filteredExecutions.value.reduce(
            (total, item) => total + Number(item.pass_rate || 0),
            0,
          ) /
            filteredExecutions.value.length) *
            10,
        ) / 10
      : 0

    return {
      total: filteredExecutions.value.length,
      running,
      passed,
      averagePassRate,
    }
  })

  const lastUpdatedText = computed(() =>
    lastUpdatedAt.value ? formatDateTime(lastUpdatedAt.value) : '-',
  )

  const hasRunningExecutions = computed(() =>
    executions.value.some(item => isExecutionRunning(item)),
  )

  const executionArtifacts = computed<ExecutionArtifact[]>(() => {
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
      .filter(Boolean) as ExecutionArtifact[]
  })

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
      const currentText = Array.isArray(currentValue)
        ? String(currentValue[0] ?? '')
        : String(currentValue ?? '')
      const nextText = Array.isArray(nextValue)
        ? String(nextValue[0] ?? '')
        : String(nextValue ?? '')
      return currentText !== nextText
    })

    if (!changed) return

    await router.replace({
      path: '/app-automation',
      query: nextQuery,
    })
  }

  const syncRouteContext = async () => {
    if (route.query.tab !== 'executions' || !projectStore.currentProjectId) {
      return
    }

    const suiteId = Number(route.query.suiteId || 0)
    if (suiteId > 0) {
      filters.suite = String(suiteId)
    }

    const executionId = Number(route.query.executionId || 0)
    if (
      executionId > 0 &&
      (!detailVisible.value || currentExecution.value?.id !== executionId)
    ) {
      await loadExecutionDetail(executionId, { open: true, syncRoute: false })
    }
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

  const loadExecutionDetail = async (
    id: number,
    options: { silent?: boolean; open?: boolean; syncRoute?: boolean } = {},
  ) => {
    if (!options.silent) {
      detailLoading.value = true
    }

    try {
      currentExecution.value = await AppAutomationService.getExecutionDetail(id)
      if (options.open) {
        detailVisible.value = true
      }

      if (options.syncRoute !== false) {
        await replaceRouteQuery({
          tab: 'executions',
          executionId: String(id),
        })
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

      await syncRouteContext()
    } catch (error: any) {
      Message.error(error.message || '加载执行记录失败')
    } finally {
      loading.value = false
    }
  }

  const handleSearch = () => {
    pagination.current = 1
  }

  const resetFilters = () => {
    filters.search = ''
    filters.status = ''
    filters.suite = 'all'
    pagination.current = 1
  }

  const viewDetail = async (id: number) => {
    await loadExecutionDetail(id, { open: true })
  }

  const openReport = (record: AppExecution) => {
    window.open(AppAutomationService.getExecutionReportUrl(record.id), '_blank', 'noopener')
  }

  const openExecutionArtifact = (record: AppExecution, relativePath: string) => {
    if (!relativePath) return

    if (
      relativePath.startsWith('http://') ||
      relativePath.startsWith('https://') ||
      relativePath.startsWith('data:')
    ) {
      window.open(relativePath, '_blank', 'noopener')
      return
    }

    window.open(
      AppAutomationService.getExecutionReportAssetUrl(record.id, relativePath),
      '_blank',
      'noopener',
    )
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
            await loadExecutionDetail(record.id, { open: true, syncRoute: false })
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
        await loadExecutionDetail(currentExecution.value.id, {
          silent: true,
          syncRoute: false,
        })
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
    () => detailVisible.value,
    value => {
      if (!value && route.query.tab === 'executions' && route.query.executionId) {
        void replaceRouteQuery({ executionId: undefined })
      }
    },
  )

  watch(
    () => projectStore.currentProjectId,
    () => {
      pagination.current = 1
      detailVisible.value = false
      currentExecution.value = null
      filters.search = ''
      filters.status = ''
      filters.suite = 'all'
      void loadData()
    },
    { immediate: true },
  )

  watch(
    () => [
      route.query.tab,
      route.query.executionId,
      route.query.suiteId,
      projectStore.currentProjectId,
    ],
    () => {
      void syncRouteContext()
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

  return {
    projectStore,
    loading,
    detailLoading,
    detailVisible,
    lastUpdatedText,
    executions,
    suites,
    currentExecution,
    stoppingIds,
    filters,
    pagination,
    formatDateTime,
    formatDuration,
    formatRate,
    formatProgress,
    getExecutionStatusMeta,
    getExecutionSource,
    isExecutionRunning,
    canOpenReport,
    getLogLevelColor,
    filteredExecutions,
    pagedExecutions,
    statistics,
    executionArtifacts,
    loadData,
    handleSearch,
    resetFilters,
    viewDetail,
    openReport,
    openExecutionArtifact,
    stopExecution,
  }
}
