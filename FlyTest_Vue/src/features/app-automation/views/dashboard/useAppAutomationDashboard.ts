import { Message } from '@arco-design/web-vue'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getActiveLlmConfig, getLlmConfigDetails } from '@/features/langgraph/services/llmConfigService'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import {
  openExecutionReportWindow,
  pushAppAutomationExecutions,
  pushAppAutomationScheduledTasks,
  pushAppAutomationTab,
} from '../appAutomationNavigation'
import type {
  AppAutomationTab,
  AppDashboardStatistics,
  AppExecution,
  AppLlmConfigSnapshot,
  AppScheduledTask,
  AppServiceHealth,
} from '../../types'

interface AiRuntimeStatus {
  hasConfig: boolean
  ready: boolean
  configName: string
  provider: string
  model: string
  apiUrl: string
  supportsVision: boolean
  checkedAt: string
  error: string
}

const createEmptyStatistics = (): AppDashboardStatistics => ({
  devices: { total: 0, online: 0, locked: 0 },
  packages: { total: 0 },
  elements: { total: 0 },
  test_cases: { total: 0 },
  executions: { total: 0, running: 0, passed: 0, failed: 0, pass_rate: 0 },
  recent_executions: [],
})

const createAiStatusState = (): AiRuntimeStatus => ({
  hasConfig: false,
  ready: false,
  configName: '',
  provider: '',
  model: '',
  apiUrl: '',
  supportsVision: false,
  checkedAt: '',
  error: '',
})

const createServiceHealthState = (): AppServiceHealth => ({
  service: '',
  status: '',
  version: '',
  checked_at: '',
  scheduler: {
    running: false,
    running_tasks: 0,
    poll_interval_seconds: 0,
  },
})

const statusConfig = {
  pending: { label: '等待执行', color: 'gold' },
  running: { label: '执行中', color: 'arcoblue' },
  passed: { label: '执行通过', color: 'green' },
  failed: { label: '执行失败', color: 'red' },
  stopped: { label: '已停止', color: 'orange' },
  completed: { label: '已完成', color: 'cyan' },
  unknown: { label: '未知', color: 'gray' },
} as const

export const useAppAutomationDashboard = () => {
  const projectStore = useProjectStore()
  const authStore = useAuthStore()
  const router = useRouter()
  const currentProjectId = computed(() => projectStore.currentProjectId)

  const statistics = reactive<AppDashboardStatistics>(createEmptyStatistics())
  const scheduledTasks = ref<AppScheduledTask[]>([])
  const loading = ref(false)
  const aiStatusLoading = ref(false)
  const lastUpdatedAt = ref<string | null>(null)
  const aiStatus = reactive<AiRuntimeStatus>(createAiStatusState())
  const serviceHealth = reactive<AppServiceHealth>(createServiceHealthState())
  const taskActionLoading = reactive<Record<string, boolean>>({})

  const resetAiStatus = () => {
    Object.assign(aiStatus, createAiStatusState())
  }

  const resetDashboardState = () => {
    Object.assign(statistics, createEmptyStatistics())
    scheduledTasks.value = []
    lastUpdatedAt.value = null
    Object.assign(serviceHealth, createServiceHealthState())
  }

  const normalizeErrorMessage = (error: unknown, fallback: string) => {
    if (typeof error === 'object' && error) {
      const normalized = error as { message?: string; error?: string }
      if (normalized.message || normalized.error) {
        return normalized.message || normalized.error || fallback
      }
    }
    return fallback
  }

  const formatDateTime = (value?: string | null) => {
    if (!value) return '-'
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return '-'
    return parsed.toLocaleString('zh-CN', { hour12: false })
  }

  const formatProgress = (value?: number | null) => {
    const progress = Number(value || 0)
    return Math.max(0, Math.min(100, Math.round(progress)))
  }

  const formatInterval = (seconds?: number | null) => {
    const totalSeconds = Number(seconds || 0)
    if (!totalSeconds) return '-'
    if (totalSeconds < 3600) return `${Math.round(totalSeconds / 60)} 分钟`

    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.round((totalSeconds % 3600) / 60)
    return minutes ? `${hours} 小时 ${minutes} 分钟` : `${hours} 小时`
  }

  const formatProviderLabel = (provider?: string) => {
    const value = String(provider || '').trim().toLowerCase()
    const mapping: Record<string, string> = {
      openai: 'OpenAI',
      anthropic: 'Anthropic',
      gemini: 'Google Gemini',
      google: 'Google Gemini',
      deepseek: 'DeepSeek',
      siliconflow: '硅基流动',
      azure_openai: 'Azure OpenAI',
    }

    if (!value) return '未识别供应方'
    return mapping[value] || value.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase())
  }

  const formatEndpointDisplay = (url?: string) => {
    if (!url) return '未配置接口地址'

    try {
      const parsed = new URL(url)
      return `${parsed.origin}${parsed.pathname === '/' ? '' : parsed.pathname}`
    } catch {
      return url
    }
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

  const getExecutionStatusColor = (record: AppExecution) => statusConfig[getExecutionState(record)].color
  const getExecutionStatusLabel = (record: AppExecution) => statusConfig[getExecutionState(record)].label

  const canOpenReport = (record: AppExecution) =>
    Boolean(record.report_path) ||
    ['completed', 'failed', 'stopped'].includes(record.status) ||
    ['passed', 'failed', 'stopped'].includes(record.result)

  const recentExecutions = computed(() =>
    [...(statistics.recent_executions || [])]
      .sort((left, right) => {
        const leftTime = new Date(left.started_at || left.created_at).getTime()
        const rightTime = new Date(right.started_at || right.created_at).getTime()
        return rightTime - leftTime
      })
      .slice(0, 8),
  )

  const activeTaskCount = computed(() => scheduledTasks.value.filter(task => task.status === 'ACTIVE').length)
  const pausedTaskCount = computed(() => scheduledTasks.value.filter(task => task.status === 'PAUSED').length)
  const failedTaskCount = computed(() => scheduledTasks.value.filter(task => task.status === 'FAILED').length)

  const taskSnapshot = computed(() =>
    [...scheduledTasks.value]
      .sort((left, right) => {
        const leftTime = left.next_run_time ? new Date(left.next_run_time).getTime() : Number.MAX_SAFE_INTEGER
        const rightTime = right.next_run_time ? new Date(right.next_run_time).getTime() : Number.MAX_SAFE_INTEGER
        if (leftTime !== rightTime) {
          return leftTime - rightTime
        }
        return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
      })
      .slice(0, 5),
  )

  const lastUpdatedText = computed(() => (lastUpdatedAt.value ? formatDateTime(lastUpdatedAt.value) : '-'))
  const serviceStatusTagColor = computed(() => {
    if (serviceHealth.status !== 'ok') return 'red'
    return serviceHealth.scheduler.running ? 'green' : 'orange'
  })
  const serviceStatusTagText = computed(() => {
    if (serviceHealth.status !== 'ok') return '服务异常'
    if (serviceHealth.scheduler.running) {
      return `调度器运行中 · ${serviceHealth.scheduler.running_tasks} 个在途任务`
    }
    return '调度器未运行'
  })

  const aiConfigDisplay = computed(() => aiStatus.configName || '未激活 LLM 配置')
  const aiProviderDisplay = computed(() => formatProviderLabel(aiStatus.provider))
  const aiModelDisplay = computed(() => aiStatus.model || '未配置模型名称')
  const aiEndpointDisplay = computed(() => formatEndpointDisplay(aiStatus.apiUrl))
  const aiCapabilityDisplay = computed(() => {
    if (!aiStatus.hasConfig) return '规则规划兜底'
    return aiStatus.supportsVision ? '视觉 + 文本智能' : '文本智能'
  })
  const aiStatusTitle = computed(() => {
    if (aiStatus.ready) {
      return `${aiConfigDisplay.value} 已接入 APP 智能编排`
    }
    if (aiStatus.hasConfig) {
      return '已检测到模型配置，但当前会优先回退到规则规划'
    }
    return '当前未启用 LLM，系统会自动使用规则规划'
  })
  const aiStatusDescription = computed(() => {
    if (aiStatus.ready) {
      return 'AI 场景生成、步骤补全和智能调度会优先走激活模型，失败时自动回退到规则规划，保证流程不中断。'
    }
    if (aiStatus.error) {
      return aiStatus.error
    }
    if (aiStatus.hasConfig) {
      return '已存在激活配置，但模型名称或接口地址不完整，当前生成链路仍可继续使用规则规划。'
    }
    return '建议先配置并激活一个 LLM 模型，这样 APP 自动化编排、智能补全和回归执行会更稳定高效。'
  })
  const aiStatusTagColor = computed(() => {
    if (aiStatus.ready) return 'green'
    if (aiStatus.hasConfig) return 'orange'
    return 'gray'
  })
  const aiStatusTagText = computed(() => {
    if (aiStatus.ready) return 'LLM 已启用'
    if (aiStatus.hasConfig) return '规则回退'
    return '未配置'
  })

  const getTaskActionKey = (action: string, taskId: number) => `${action}:${taskId}`
  const isTaskActionLoading = (action: string, taskId: number) => Boolean(taskActionLoading[getTaskActionKey(action, taskId)])
  const setTaskActionLoading = (action: string, taskId: number, state: boolean) => {
    taskActionLoading[getTaskActionKey(action, taskId)] = state
  }

  const getTaskTypeLabel = (value: string) => (value === 'TEST_SUITE' ? '测试套件' : '测试用例')
  const getTaskTarget = (task: AppScheduledTask) => task.test_suite_name || task.test_case_name || '未绑定目标'
  const getTaskStatusColor = (value: string) =>
    value === 'ACTIVE' ? 'green' : value === 'PAUSED' ? 'orange' : value === 'FAILED' ? 'red' : value === 'COMPLETED' ? 'arcoblue' : 'gray'

  const getTriggerSummary = (task: AppScheduledTask) => {
    if (task.trigger_type === 'CRON') return task.cron_expression || '-'
    if (task.trigger_type === 'INTERVAL') return `每 ${formatInterval(task.interval_seconds)} 执行一次`
    return formatDateTime(task.execute_at)
  }

  const getExecutionIds = (task: AppScheduledTask) => {
    const ids = task.last_result.execution_ids || []
    return ids.filter((item): item is number => Number.isFinite(Number(item)))
  }

  const getPrimaryExecutionId = (task: AppScheduledTask) =>
    task.last_result.execution_id || getExecutionIds(task)[0] || undefined

  const refreshAiStatus = async (showMessage = false): Promise<AppLlmConfigSnapshot | null> => {
    aiStatusLoading.value = true
    try {
      const activeResponse = await getActiveLlmConfig()
      const activeConfig = activeResponse.data

      if (!activeConfig?.id) {
        resetAiStatus()
        aiStatus.checkedAt = new Date().toISOString()
        if (showMessage) {
          Message.info('当前没有激活的 LLM 配置，APP AI 会回退到规则规划')
        }
        return null
      }

      const detailResponse = await getLlmConfigDetails(activeConfig.id)
      const detail = detailResponse.data || activeConfig
      const snapshot: AppLlmConfigSnapshot | null =
        detail?.name && detail?.api_url
          ? {
              config_name: detail.config_name,
              provider: detail.provider,
              name: detail.name,
              api_url: detail.api_url,
              api_key: detail.api_key,
              system_prompt: detail.system_prompt,
              supports_vision: detail.supports_vision,
            }
          : null

      Object.assign(aiStatus, {
        hasConfig: true,
        ready: Boolean(snapshot),
        configName: detail?.config_name || '',
        provider: detail?.provider || '',
        model: detail?.name || '',
        apiUrl: detail?.api_url || '',
        supportsVision: Boolean(detail?.supports_vision),
        checkedAt: new Date().toISOString(),
        error: snapshot ? '' : '激活的 LLM 配置缺少模型名称或接口地址，当前会回退到规则规划。',
      })

      if (!snapshot && showMessage) {
        Message.warning(aiStatus.error || 'AI 状态已刷新')
      }

      if (snapshot && showMessage) {
        Message.success('AI 模型状态已刷新')
      }

      return snapshot
    } catch (error: unknown) {
      resetAiStatus()
      aiStatus.checkedAt = new Date().toISOString()
      aiStatus.error = normalizeErrorMessage(error, '加载激活 LLM 配置失败，当前会回退到规则规划。')
      if (showMessage) {
        Message.error(aiStatus.error)
      }
      return null
    } finally {
      aiStatusLoading.value = false
    }
  }

  const loadDashboardState = async (options: { includeAi?: boolean; silent?: boolean } = {}) => {
    if (!currentProjectId.value) {
      resetDashboardState()
      return
    }

    const { includeAi = true, silent = false } = options

    if (!silent) {
      loading.value = true
    }

    try {
      const [dashboardData, taskList, healthData] = await Promise.all([
        AppAutomationService.getDashboardStatistics(currentProjectId.value),
        AppAutomationService.getScheduledTasks(currentProjectId.value),
        AppAutomationService.getHealthStatus().catch(() => null),
      ])

      Object.assign(statistics, createEmptyStatistics(), dashboardData, {
        recent_executions: dashboardData.recent_executions || [],
      })
      scheduledTasks.value = taskList
      if (healthData) {
        Object.assign(serviceHealth, createServiceHealthState(), healthData)
      }

      if (includeAi) {
        await refreshAiStatus()
      }

      lastUpdatedAt.value = new Date().toISOString()
    } catch (error: unknown) {
      Message.error(normalizeErrorMessage(error, '加载 APP 自动化总览失败'))
    } finally {
      if (!silent) {
        loading.value = false
      }
    }
  }

  const loadDashboard = async () => {
    await loadDashboardState({ includeAi: true })
  }

  const openTab = async (tab: AppAutomationTab) => {
    await pushAppAutomationTab(router, tab)
  }

  const openExecution = async (executionId: number) => {
    await pushAppAutomationExecutions(router, { executionId })
  }

  const openLatestExecution = async (task: AppScheduledTask) => {
    const executionId = getPrimaryExecutionId(task)
    if (!executionId) {
      Message.warning('当前任务还没有可查看的执行记录')
      return
    }
    await openExecution(executionId)
  }

  const openScheduledTask = async (task: AppScheduledTask) => {
    await pushAppAutomationScheduledTasks(router, { taskId: task.id })
  }

  const openReport = (executionId: number) => {
    openExecutionReportWindow(executionId)
  }

  const openLlmConfigManagement = async () => {
    await router.push({ name: 'LlmConfigManagement' })
  }

  const runTaskNow = async (task: AppScheduledTask) => {
    setTaskActionLoading('run', task.id, true)
    try {
      const result = await AppAutomationService.runScheduledTaskNow(task.id, authStore.currentUser?.username || 'FlyTest')
      const createdCount = result.trigger_payload?.execution_ids?.length || (result.trigger_payload?.execution_id ? 1 : 0)
      Message.success(createdCount > 1 ? `任务已触发，已创建 ${createdCount} 条执行记录` : '定时任务已触发执行')
      await loadDashboardState({ includeAi: false })
    } catch (error: unknown) {
      Message.error(normalizeErrorMessage(error, '执行定时任务失败'))
    } finally {
      setTaskActionLoading('run', task.id, false)
    }
  }

  const resumeTask = async (task: AppScheduledTask) => {
    setTaskActionLoading('resume', task.id, true)
    try {
      await AppAutomationService.resumeScheduledTask(task.id)
      Message.success('任务已恢复')
      await loadDashboardState({ includeAi: false })
    } catch (error: unknown) {
      Message.error(normalizeErrorMessage(error, '恢复任务失败'))
    } finally {
      setTaskActionLoading('resume', task.id, false)
    }
  }

  let timer: number | null = null
  let polling = false

  watch(
    () => projectStore.currentProjectId,
    projectId => {
      Object.keys(taskActionLoading).forEach(key => {
        delete taskActionLoading[key]
      })

      if (!projectId) {
        resetDashboardState()
        resetAiStatus()
        return
      }

      void loadDashboardState({ includeAi: true })
    },
    { immediate: true },
  )

  onMounted(() => {
    timer = window.setInterval(() => {
      if (polling || !currentProjectId.value) {
        return
      }

      polling = true
      void loadDashboardState({ includeAi: false, silent: true }).finally(() => {
        polling = false
      })
    }, 15000)
  })

  onUnmounted(() => {
    if (timer) {
      window.clearInterval(timer)
    }
  })

  return {
    currentProjectId,
    statistics,
    loading,
    aiStatusLoading,
    aiStatus,
    recentExecutions,
    activeTaskCount,
    pausedTaskCount,
    failedTaskCount,
    taskSnapshot,
    lastUpdatedText,
    serviceStatusTagColor,
    serviceStatusTagText,
    aiConfigDisplay,
    aiProviderDisplay,
    aiModelDisplay,
    aiEndpointDisplay,
    aiCapabilityDisplay,
    aiStatusTitle,
    aiStatusDescription,
    aiStatusTagColor,
    aiStatusTagText,
    getExecutionStatusColor,
    getExecutionStatusLabel,
    formatProgress,
    formatDateTime,
    canOpenReport,
    getTaskTypeLabel,
    getTaskTarget,
    getTaskStatusColor,
    getTriggerSummary,
    getPrimaryExecutionId,
    isTaskActionLoading,
    refreshAiStatus,
    loadDashboard,
    openTab,
    openExecution,
    openLatestExecution,
    openScheduledTask,
    openReport,
    openLlmConfigManagement,
    runTaskNow,
    resumeTask,
  }
}
