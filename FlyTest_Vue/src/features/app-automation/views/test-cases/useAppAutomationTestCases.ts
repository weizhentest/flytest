import { computed, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import {
  openExecutionReportWindow,
  pushAppAutomationTab,
  pushAppAutomationExecutions,
  pushAppAutomationSceneBuilder,
} from '../appAutomationNavigation'
import type { AppDevice, AppExecution, AppPackage, AppTestCase } from '../../types'
import type {
  TestCaseExecuteFormModel,
  TestCaseFormModel,
  TestCaseStats,
} from './testCaseViewModels'

export function useAppAutomationTestCases() {
  const authStore = useAuthStore()
  const projectStore = useProjectStore()
  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const visible = ref(false)
  const executeVisible = ref(false)
  const executeMode = ref<'single' | 'batch'>('single')
  const search = ref('')
  const packageFilter = ref<number | ''>('')
  const testCases = ref<AppTestCase[]>([])
  const packages = ref<AppPackage[]>([])
  const devices = ref<AppDevice[]>([])
  const recentExecutionList = ref<AppExecution[]>([])
  const currentExecutionCaseId = ref<number | null>(null)
  const selectedCaseIds = ref<number[]>([])

  const form = reactive<TestCaseFormModel>({
    id: 0,
    name: '',
    description: '',
    package_id: undefined,
    timeout: 300,
    retry_count: 0,
    variablesText: '[]',
    uiFlowText: '{\n  "steps": []\n}',
  })

  const executeForm = reactive<TestCaseExecuteFormModel>({
    device_id: undefined,
    package_id: undefined,
  })

  const availableDevices = computed(() =>
    devices.value.filter(device => device.status === 'available' || device.status === 'online'),
  )

  const selectedCases = computed(
    () =>
      selectedCaseIds.value
        .map(
          id =>
            filteredCases.value.find(item => item.id === id) ||
            testCases.value.find(item => item.id === id),
        )
        .filter(Boolean) as AppTestCase[],
  )

  const recentExecutions = computed(() =>
    [...recentExecutionList.value]
      .sort(
        (left, right) =>
          new Date(right.started_at || right.created_at).getTime() -
          new Date(left.started_at || left.created_at).getTime(),
      )
      .slice(0, 5),
  )

  const filteredCases = computed(() => {
    if (!packageFilter.value) return testCases.value
    return testCases.value.filter(item => item.package_id === packageFilter.value)
  })

  const caseStats = computed<TestCaseStats>(() => {
    const total = filteredCases.value.length
    const passed = filteredCases.value.filter(item => item.last_result === 'passed').length
    const failed = filteredCases.value.filter(item => item.last_result === 'failed').length
    const pending = filteredCases.value.filter(item => !item.last_result).length
    return { total, passed, failed, pending }
  })

  const formatDateTime = (value?: string | null) => {
    if (!value) return '-'
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
  }

  const getStepCount = (record: AppTestCase) => {
    const steps = record.ui_flow?.steps
    return Array.isArray(steps) ? steps.length : 0
  }

  const getResultLabel = (result?: string) => {
    if (result === 'passed') return '通过'
    if (result === 'failed') return '失败'
    if (result === 'stopped') return '已停止'
    return '未执行'
  }

  const getResultColor = (result?: string) => {
    if (result === 'passed') return 'green'
    if (result === 'failed') return 'red'
    if (result === 'stopped') return 'orange'
    if (result === 'running' || result === 'pending') return 'arcoblue'
    return 'gray'
  }

  const getExecutionResultLabel = (record: AppExecution) => {
    if (record.result === 'passed') return '通过'
    if (record.result === 'failed') return '失败'
    if (record.result === 'stopped') return '已停止'
    if (record.status === 'running') return '执行中'
    if (record.status === 'pending') return '等待中'
    return record.result || record.status || '未知'
  }

  const formatRate = (value?: number | null) => Math.round(Number(value || 0) * 10) / 10
  const formatProgress = (value?: number | null) =>
    Math.max(0, Math.min(100, Math.round(Number(value || 0))))

  const canOpenExecutionReport = (record: AppExecution) =>
    Boolean(record.report_path) ||
    ['completed', 'failed', 'stopped'].includes(record.status) ||
    ['passed', 'failed', 'stopped'].includes(record.result)

  const resetForm = () => {
    form.id = 0
    form.name = ''
    form.description = ''
    form.package_id = undefined
    form.timeout = 300
    form.retry_count = 0
    form.variablesText = '[]'
    form.uiFlowText = '{\n  "steps": []\n}'
  }

  const loadData = async () => {
    if (!projectStore.currentProjectId) {
      testCases.value = []
      packages.value = []
      devices.value = []
      recentExecutionList.value = []
      loading.value = false
      return
    }

    loading.value = true
    try {
      const [caseList, packageList, deviceList, executionList] = await Promise.all([
        AppAutomationService.getTestCases(
          projectStore.currentProjectId,
          search.value.trim() || undefined,
        ),
        AppAutomationService.getPackages(projectStore.currentProjectId),
        AppAutomationService.getDevices(),
        AppAutomationService.getExecutions(projectStore.currentProjectId),
      ])
      testCases.value = caseList
      packages.value = packageList
      devices.value = deviceList
      recentExecutionList.value = executionList
    } catch (error: any) {
      Message.error(error.message || '加载测试用例失败')
    } finally {
      loading.value = false
    }
  }

  const resetFilters = async () => {
    search.value = ''
    packageFilter.value = ''
    await loadData()
  }

  const openCreate = () => {
    resetForm()
    visible.value = true
  }

  const openSceneBuilderDraft = () => {
    void pushAppAutomationSceneBuilder(router)
  }

  const openEdit = (record: AppTestCase) => {
    form.id = record.id
    form.name = record.name
    form.description = record.description
    form.package_id = record.package_id || undefined
    form.timeout = record.timeout
    form.retry_count = record.retry_count
    form.variablesText = JSON.stringify(record.variables, null, 2)
    form.uiFlowText = JSON.stringify(record.ui_flow, null, 2)
    visible.value = true
  }

  const submit = async () => {
    try {
      const payload = {
        project_id: projectStore.currentProjectId || 0,
        name: form.name,
        description: form.description,
        package_id: form.package_id ?? null,
        ui_flow: JSON.parse(form.uiFlowText || '{}'),
        variables: JSON.parse(form.variablesText || '[]'),
        tags: [],
        timeout: form.timeout,
        retry_count: form.retry_count,
      }

      if (form.id) {
        await AppAutomationService.updateTestCase(form.id, payload)
        Message.success('测试用例已更新')
      } else {
        await AppAutomationService.createTestCase(payload)
        Message.success('测试用例已创建')
      }

      visible.value = false
      await loadData()
    } catch (error: any) {
      Message.error(error.message || '保存测试用例失败，请检查 JSON')
    }
  }

  const duplicateCase = async (record: AppTestCase) => {
    try {
      await AppAutomationService.createTestCase({
        project_id: record.project_id,
        name: `${record.name}-副本`,
        description: record.description,
        package_id: record.package_id ?? null,
        ui_flow: record.ui_flow || { steps: [] },
        variables: record.variables || [],
        tags: record.tags || [],
        timeout: record.timeout,
        retry_count: record.retry_count,
      })
      Message.success('测试用例副本已创建')
      await loadData()
    } catch (error: any) {
      Message.error(error.message || '复制测试用例失败')
    }
  }

  const openExecute = (record: AppTestCase) => {
    executeMode.value = 'single'
    currentExecutionCaseId.value = record.id
    executeForm.device_id = availableDevices.value[0]?.id
    executeForm.package_id = record.package_id || undefined
    executeVisible.value = true
  }

  const openSceneBuilder = (record: AppTestCase) => {
    void pushAppAutomationSceneBuilder(router, { caseId: record.id })
  }

  const openExecutionWorkspace = async (executionId: number) => {
    await pushAppAutomationExecutions(router, { executionId })
  }

  const openExecutionReport = (executionId: number) => {
    openExecutionReportWindow(executionId)
  }

  const openBatchExecute = () => {
    if (!selectedCaseIds.value.length) {
      Message.warning('请至少选择一个测试用例')
      return
    }

    if (selectedCaseIds.value.length > 1) {
      Message.warning('多条用例请先加入测试套件后再执行，避免同一设备上的锁竞争')
      void pushAppAutomationTab(router, 'suites')
      return
    }

    executeMode.value = 'single'
    currentExecutionCaseId.value = selectedCaseIds.value[0] || null
    executeForm.device_id = availableDevices.value[0]?.id
    executeForm.package_id =
      selectedCases.value[0]?.package_id ??
      testCases.value.find(item => item.id === currentExecutionCaseId.value)?.package_id ??
      undefined
    executeVisible.value = true
  }

  const clearSelection = () => {
    selectedCaseIds.value = []
  }

  const resetExecuteState = () => {
    executeMode.value = 'single'
    executeForm.device_id = undefined
    executeForm.package_id = undefined
    currentExecutionCaseId.value = null
  }

  const executeCase = async () => {
    if (!executeForm.device_id) {
      Message.warning('请选择执行设备')
      return
    }

    try {
      if (executeMode.value === 'batch') {
        if (!selectedCases.value.length) {
          Message.warning('请至少选择一个测试用例')
          return
        }

        if (selectedCases.value.length > 1) {
          executeVisible.value = false
          Message.warning('当前不支持在同一设备上直接批量启动多条用例，请改用测试套件执行')
          void pushAppAutomationTab(router, 'suites')
          return
        }

        const submittedCases = [...selectedCases.value]
        const results: PromiseSettledResult<AppExecution>[] = []
        for (const item of submittedCases) {
          try {
            const execution = await AppAutomationService.executeTestCase(item.id, {
              device_id: executeForm.device_id as number,
              package_id: executeForm.package_id ?? null,
              trigger_mode: 'manual',
              triggered_by: authStore.currentUser?.username || 'FlyTest',
            })
            results.push({ status: 'fulfilled', value: execution })
          } catch (error) {
            results.push({ status: 'rejected', reason: error })
            break
          }
        }

        const executions = results
          .filter((item): item is PromiseFulfilledResult<AppExecution> => item.status === 'fulfilled')
          .map(item => item.value)
        const failedCases = results
          .map((item, index) =>
            item.status === 'rejected'
              ? {
                  record: submittedCases[index],
                  message:
                    (item.reason as { message?: string; error?: string } | undefined)?.message ||
                    (item.reason as { message?: string; error?: string } | undefined)?.error ||
                    '未知错误',
                }
              : null,
          )
          .filter(
            (item): item is { record: AppTestCase; message: string } =>
              Boolean(item?.record),
          )
        if (results.length < submittedCases.length) {
          failedCases.push(
            ...submittedCases.slice(results.length).map(record => ({
              record,
              message: '前序用例启动失败后未继续提交',
            })),
          )
        }

        if (!executions.length) {
          const failedSummary = failedCases
            .slice(0, 3)
            .map(item => `${item.record.name}: ${item.message}`)
            .join('；')
          Message.error(
            failedSummary ? `批量执行启动失败：${failedSummary}` : '批量执行启动失败',
          )
          return
        }

        executeVisible.value = false
        if (failedCases.length === 0) {
          Message.success(`已成功启动 ${executions.length} 条执行任务`)
          clearSelection()
        } else {
          selectedCaseIds.value = failedCases.map(item => item.record.id)
          const failedNames = failedCases
            .slice(0, 3)
            .map(item => item.record.name)
            .join('、')
          const suffix = failedCases.length > 3 ? ' 等用例未成功启动' : ' 未成功启动'
          Message.warning(
            `已启动 ${executions.length}/${submittedCases.length} 条执行任务，${failedNames}${suffix}`,
          )
        }
        await openExecutionWorkspace(executions[0].id)
        return
      }

      if (!currentExecutionCaseId.value) {
        Message.warning('请先选择要执行的测试用例')
        return
      }

      const execution = await AppAutomationService.executeTestCase(currentExecutionCaseId.value, {
        device_id: executeForm.device_id,
        package_id: executeForm.package_id ?? null,
        trigger_mode: 'manual',
        triggered_by: authStore.currentUser?.username || 'FlyTest',
      })
      executeVisible.value = false
      Message.success('执行任务已启动，正在跳转到执行记录')
      await openExecutionWorkspace(execution.id)
    } catch (error: any) {
      Message.error(error.message || '启动执行失败')
    }
  }

  const remove = (id: number) => {
    Modal.confirm({
      title: '删除测试用例',
      content: '确认删除该测试用例吗？',
      onOk: async () => {
        await AppAutomationService.deleteTestCase(id)
        if (form.id === id) {
          visible.value = false
          resetForm()
        }
        if (currentExecutionCaseId.value === id) {
          executeVisible.value = false
          resetExecuteState()
        }
        selectedCaseIds.value = selectedCaseIds.value.filter(item => item !== id)
        Message.success('测试用例已删除')
        await loadData()
      },
    })
  }

  watch(
    () => route.query.tab,
    tab => {
      if (tab === 'test-cases') {
        return
      }
      visible.value = false
      executeVisible.value = false
    },
  )

  watch(
    () => visible.value,
    value => {
      if (!value) {
        resetForm()
      }
    },
  )

  watch(
    () => executeVisible.value,
    value => {
      if (!value) {
        resetExecuteState()
      }
    },
  )

  watch(
    () => projectStore.currentProjectId,
    () => {
      visible.value = false
      executeVisible.value = false
      resetForm()
      resetExecuteState()
      packageFilter.value = ''
      selectedCaseIds.value = []
      recentExecutionList.value = []
      void loadData()
    },
    { immediate: true },
  )

  return {
    projectStore,
    loading,
    visible,
    executeVisible,
    executeMode,
    search,
    packageFilter,
    testCases,
    packages,
    recentExecutions,
    selectedCaseIds,
    form,
    executeForm,
    availableDevices,
    selectedCases,
    filteredCases,
    caseStats,
    formatDateTime,
    getStepCount,
    getResultLabel,
    getResultColor,
    getExecutionResultLabel,
    formatRate,
    formatProgress,
    canOpenExecutionReport,
    loadData,
    resetFilters,
    openCreate,
    openSceneBuilderDraft,
    openEdit,
    submit,
    duplicateCase,
    openExecute,
    openSceneBuilder,
    openExecutionWorkspace,
    openExecutionReport,
    openBatchExecute,
    clearSelection,
    executeCase,
    remove,
  }
}
