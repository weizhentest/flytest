import { computed, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppDevice, AppExecution, AppTestCase, AppTestSuite } from '../../types'
import type {
  SuiteFilters,
  SuiteFormModel,
  SuiteExecutionArtifact,
  SuiteRunFormModel,
  SuiteStats,
  SuiteStatusMeta,
} from './suiteViewModels'

export function useAppAutomationSuites() {
  const authStore = useAuthStore()
  const projectStore = useProjectStore()
  const router = useRouter()

  const loading = ref(false)
  const visible = ref(false)
  const runVisible = ref(false)
  const detailVisible = ref(false)
  const historyVisible = ref(false)
  const historyLoading = ref(false)
  const executionDetailVisible = ref(false)

  const suites = ref<AppTestSuite[]>([])
  const testCases = ref<AppTestCase[]>([])
  const devices = ref<AppDevice[]>([])
  const history = ref<AppExecution[]>([])
  const selectedSuite = ref<AppTestSuite | null>(null)
  const currentExecution = ref<AppExecution | null>(null)
  const currentSuiteId = ref<number | null>(null)

  const filters = reactive<SuiteFilters>({
    search: '',
    status: '',
  })

  const form = reactive<SuiteFormModel>({
    id: 0,
    name: '',
    description: '',
    test_case_ids: [],
  })

  const runForm = reactive<SuiteRunFormModel>({
    device_id: undefined,
  })

  const availableDevices = computed(() =>
    devices.value.filter(item => item.status === 'available' || item.status === 'online'),
  )

  const selectedCases = computed(
    () =>
      form.test_case_ids
        .map(id => testCases.value.find(item => item.id === id))
        .filter(Boolean) as AppTestCase[],
  )

  const getSuiteState = (record: AppTestSuite) => {
    if (record.execution_status === 'running') return 'running'
    if (!record.last_run_at) return 'not_run'
    if (record.execution_result === 'passed') return 'passed'
    if (record.execution_result === 'failed') return 'failed'
    if (record.execution_result === 'stopped') return 'stopped'
    return 'not_run'
  }

  const getSuiteStatusMeta = (record: AppTestSuite): SuiteStatusMeta => {
    const state = getSuiteState(record)
    if (state === 'running') return { label: '执行中', color: 'arcoblue' }
    if (state === 'passed') return { label: '执行通过', color: 'green' }
    if (state === 'failed') return { label: '执行失败', color: 'red' }
    if (state === 'stopped') return { label: '已停止', color: 'orange' }
    return { label: '未执行', color: 'gray' }
  }

  const getSuiteHealthRate = (record: AppTestSuite) => {
    const passed = Number(record.passed_count || 0)
    const failed = Number(record.failed_count || 0)
    const stopped = Number(record.stopped_count || 0)
    const total = passed + failed + stopped
    return total ? Math.round((passed / total) * 1000) / 10 : 0
  }

  const getExecutionState = (record: AppExecution) => {
    if (record.result === 'passed') return 'passed'
    if (record.result === 'failed' || record.status === 'failed') return 'failed'
    if (record.result === 'stopped' || record.status === 'stopped') return 'stopped'
    if (record.status === 'running') return 'running'
    if (record.status === 'pending') return 'pending'
    return 'unknown'
  }

  const getExecutionStatusMeta = (record: AppExecution): SuiteStatusMeta => {
    const state = getExecutionState(record)
    if (state === 'running') return { label: '执行中', color: 'arcoblue' }
    if (state === 'pending') return { label: '等待执行', color: 'gold' }
    if (state === 'passed') return { label: '执行通过', color: 'green' }
    if (state === 'failed') return { label: '执行失败', color: 'red' }
    if (state === 'stopped') return { label: '已停止', color: 'orange' }
    return { label: record.result || record.status || '未知', color: 'gray' }
  }

  const canOpenReport = (record: AppExecution) =>
    Boolean(record.report_path) ||
    ['completed', 'failed', 'stopped'].includes(record.status) ||
    ['passed', 'failed', 'stopped'].includes(record.result)

  const formatDateTime = (value?: string | null) =>
    value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'

  const formatRate = (value?: number | null) => Math.round(Number(value || 0) * 10) / 10

  const formatDuration = (value?: number | null) => {
    const seconds = Number(value || 0)
    if (!seconds) return '-'
    if (seconds < 60) return `${Math.round(seconds)} 秒`
    const minutes = Math.floor(seconds / 60)
    const remainSeconds = Math.round(seconds % 60)
    if (minutes < 60) return `${minutes} 分 ${remainSeconds} 秒`
    const hours = Math.floor(minutes / 60)
    return `${hours} 小时 ${minutes % 60} 分`
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

  const getLogLevelColor = (value?: string) => {
    if (value === 'error') return 'red'
    if (value === 'warning') return 'orange'
    if (value === 'success') return 'green'
    return 'arcoblue'
  }

  const filteredSuites = computed(() =>
    suites.value.filter(item => {
      if (filters.status && getSuiteState(item) !== filters.status) return false
      return true
    }),
  )

  const suiteStats = computed<SuiteStats>(() => ({
    total: filteredSuites.value.length,
    running: filteredSuites.value.filter(item => getSuiteState(item) === 'running').length,
    passed: filteredSuites.value.filter(item => getSuiteState(item) === 'passed').length,
    stopped: filteredSuites.value.filter(item => getSuiteState(item) === 'stopped').length,
    health: filteredSuites.value.length
      ? Math.round(
          (filteredSuites.value.reduce((sum, item) => sum + getSuiteHealthRate(item), 0) /
            filteredSuites.value.length) *
            10,
        ) / 10
      : 0,
  }))

  const executionArtifacts = computed<SuiteExecutionArtifact[]>(() => {
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
      .filter(Boolean) as SuiteExecutionArtifact[]
  })

  const resetForm = () => {
    form.id = 0
    form.name = ''
    form.description = ''
    form.test_case_ids = []
  }

  const loadData = async () => {
    if (!projectStore.currentProjectId) {
      suites.value = []
      return
    }

    loading.value = true
    try {
      const [suiteList, caseList, deviceList] = await Promise.all([
        AppAutomationService.getTestSuites(
          projectStore.currentProjectId,
          filters.search.trim() || undefined,
        ),
        AppAutomationService.getTestCases(projectStore.currentProjectId),
        AppAutomationService.getDevices(),
      ])
      suites.value = suiteList
      testCases.value = caseList
      devices.value = deviceList
    } catch (error: any) {
      Message.error(error.message || '加载测试套件失败')
    } finally {
      loading.value = false
    }
  }

  const resetFilters = async () => {
    filters.search = ''
    filters.status = ''
    await loadData()
  }

  const openCreate = () => {
    resetForm()
    visible.value = true
  }

  const openEdit = (record: AppTestSuite) => {
    form.id = record.id
    form.name = record.name
    form.description = record.description
    form.test_case_ids = record.suite_cases.map(item => item.test_case_id)
    visible.value = true
  }

  const saveSuite = async () => {
    if (!projectStore.currentProjectId) return
    if (!form.name.trim()) {
      Message.warning('请输入套件名称')
      return
    }

    const payload = {
      project_id: projectStore.currentProjectId,
      name: form.name.trim(),
      description: form.description.trim(),
      test_case_ids: form.test_case_ids,
    }

    try {
      if (form.id) {
        await AppAutomationService.updateTestSuite(form.id, payload)
        Message.success('测试套件已更新')
      } else {
        await AppAutomationService.createTestSuite(payload)
        Message.success('测试套件已创建')
      }
      visible.value = false
      resetForm()
      await loadData()
    } catch (error: any) {
      Message.error(error.message || '保存测试套件失败')
    }
  }

  const moveCase = (index: number, delta: -1 | 1) => {
    const targetIndex = index + delta
    if (targetIndex < 0 || targetIndex >= form.test_case_ids.length) return
    const next = [...form.test_case_ids]
    const [current] = next.splice(index, 1)
    next.splice(targetIndex, 0, current)
    form.test_case_ids = next
  }

  const openRun = (record: AppTestSuite) => {
    currentSuiteId.value = record.id
    runForm.device_id = availableDevices.value[0]?.id
    runVisible.value = true
  }

  const openExecutionWorkspace = async (
    executionId?: number,
    suiteId?: number | null,
  ) => {
    await router.push({
      path: '/app-automation',
      query: {
        tab: 'executions',
        executionId: executionId ? String(executionId) : undefined,
        suiteId: suiteId ? String(suiteId) : undefined,
      },
    })
  }

  const runSuite = async () => {
    if (!currentSuiteId.value || !runForm.device_id) {
      Message.warning('请选择执行设备')
      return
    }

    try {
      const result = await AppAutomationService.runTestSuite(currentSuiteId.value, {
        device_id: runForm.device_id,
        triggered_by: authStore.currentUser?.username || 'FlyTest',
      })
      runVisible.value = false
      Message.success(`测试套件已提交执行，共创建 ${result.test_case_count} 条执行记录`)
      await openExecutionWorkspace(
        result.execution_ids?.[0],
        result.suite_id || currentSuiteId.value,
      )
    } catch (error: any) {
      Message.error(error.message || '执行测试套件失败')
    }
  }

  const openDetail = async (record: AppTestSuite) => {
    try {
      selectedSuite.value = await AppAutomationService.getTestSuite(record.id)
      detailVisible.value = true
    } catch (error: any) {
      Message.error(error.message || '加载套件详情失败')
    }
  }

  const openHistory = async (record: AppTestSuite) => {
    selectedSuite.value = record
    historyVisible.value = true
    historyLoading.value = true
    try {
      history.value = await AppAutomationService.getTestSuiteExecutions(record.id)
    } catch (error: any) {
      Message.error(error.message || '加载执行历史失败')
      history.value = []
    } finally {
      historyLoading.value = false
    }
  }

  const openExecutionDetail = async (executionId: number) => {
    try {
      currentExecution.value = await AppAutomationService.getExecutionDetail(executionId)
      executionDetailVisible.value = true
    } catch (error: any) {
      Message.error(error.message || '加载执行详情失败')
    }
  }

  const openExecutionReport = (record: AppExecution) => {
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

  const duplicateSuite = async (record: AppTestSuite) => {
    try {
      await AppAutomationService.createTestSuite({
        project_id: record.project_id,
        name: `${record.name}-副本`,
        description: record.description,
        test_case_ids: record.suite_cases.map(item => item.test_case_id),
      })
      Message.success('测试套件副本已创建')
      await loadData()
    } catch (error: any) {
      Message.error(error.message || '复制测试套件失败')
    }
  }

  const remove = (id: number) => {
    Modal.confirm({
      title: '删除测试套件',
      content: '确认删除该测试套件吗？',
      onOk: async () => {
        await AppAutomationService.deleteTestSuite(id)
        Message.success('测试套件已删除')
        await loadData()
      },
    })
  }

  watch(
    () => projectStore.currentProjectId,
    () => {
      resetForm()
      filters.status = ''
      void loadData()
    },
    { immediate: true },
  )

  return {
    projectStore,
    loading,
    visible,
    runVisible,
    detailVisible,
    historyVisible,
    historyLoading,
    executionDetailVisible,
    suites,
    testCases,
    history,
    selectedSuite,
    currentExecution,
    filters,
    form,
    runForm,
    availableDevices,
    selectedCases,
    getSuiteStatusMeta,
    getSuiteHealthRate,
    getExecutionStatusMeta,
    canOpenReport,
    formatDateTime,
    formatRate,
    formatDuration,
    getLogLevelColor,
    filteredSuites,
    suiteStats,
    executionArtifacts,
    loadData,
    resetFilters,
    openCreate,
    openEdit,
    saveSuite,
    moveCase,
    openRun,
    runSuite,
    openDetail,
    openHistory,
    openExecutionDetail,
    openExecutionReport,
    openExecutionWorkspace,
    openExecutionArtifact,
    duplicateSuite,
    remove,
    currentSuiteId,
  }
}
