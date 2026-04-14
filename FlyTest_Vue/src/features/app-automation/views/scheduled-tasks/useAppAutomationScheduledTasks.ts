import { computed, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import type {
  AppDevice,
  AppNotificationLog,
  AppPackage,
  AppScheduledTask,
  AppScheduledTaskRunResult,
  AppTestCase,
  AppTestSuite,
} from '../../types'
import type {
  ScheduledTaskFilters,
  ScheduledTaskFormModel,
  ScheduledTaskPagination,
  ScheduledTaskResultMeta,
  ScheduledTaskStatistics,
} from './scheduledTaskViewModels'

export function useAppAutomationScheduledTasks() {
  const authStore = useAuthStore()
  const projectStore = useProjectStore()
  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const visible = ref(false)
  const detailVisible = ref(false)
  const detailLoading = ref(false)
  const taskNotificationsLoading = ref(false)
  const notifyEmailsText = ref('')
  const tasks = ref<AppScheduledTask[]>([])
  const suites = ref<AppTestSuite[]>([])
  const testCases = ref<AppTestCase[]>([])
  const devices = ref<AppDevice[]>([])
  const packages = ref<AppPackage[]>([])
  const currentTask = ref<AppScheduledTask | null>(null)
  const taskNotifications = ref<AppNotificationLog[]>([])

  const actionLoading = reactive<Record<string, boolean>>({})

  const filters = reactive<ScheduledTaskFilters>({
    search: '',
    status: '',
    task_type: '',
    trigger_type: '',
  })

  const pagination = reactive<ScheduledTaskPagination>({
    current: 1,
    pageSize: 10,
  })

  const form = reactive<ScheduledTaskFormModel>({
    id: 0,
    name: '',
    description: '',
    task_type: 'TEST_SUITE',
    trigger_type: 'CRON',
    cron_expression: '0 0 * * *',
    interval_seconds: 3600,
    execute_at: '',
    device_id: undefined,
    package_id: undefined,
    test_suite_id: undefined,
    test_case_id: undefined,
    notify_on_success: false,
    notify_on_failure: true,
    notification_type: 'email',
    status: 'ACTIVE',
  })

  const notificationsEnabled = computed(() => form.notify_on_success || form.notify_on_failure)
  const needsEmailRecipients = computed(
    () => notificationsEnabled.value && ['email', 'both'].includes(form.notification_type),
  )
  const recentTaskNotifications = computed(() => taskNotifications.value.slice(0, 6))

  const filteredTasks = computed(() => {
    const keyword = filters.search.trim().toLowerCase()

    return tasks.value.filter(task => {
      if (filters.status && task.status !== filters.status) return false
      if (filters.task_type && task.task_type !== filters.task_type) return false
      if (filters.trigger_type && task.trigger_type !== filters.trigger_type) return false
      if (!keyword) return true

      return [
        task.name,
        task.description,
        task.test_suite_name,
        task.test_case_name,
        task.device_name,
        task.notification_type,
      ]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    })
  })

  const pagedTasks = computed(() => {
    const start = (pagination.current - 1) * pagination.pageSize
    return filteredTasks.value.slice(start, start + pagination.pageSize)
  })

  const statistics = computed<ScheduledTaskStatistics>(() => {
    const totalRuns = filteredTasks.value.reduce((sum, task) => sum + Number(task.total_runs || 0), 0)
    const successfulRuns = filteredTasks.value.reduce(
      (sum, task) => sum + Number(task.successful_runs || 0),
      0,
    )
    const active = filteredTasks.value.filter(task => task.status === 'ACTIVE').length
    const paused = filteredTasks.value.filter(task => task.status === 'PAUSED').length
    const successRate = totalRuns ? Math.round((successfulRuns / totalRuns) * 1000) / 10 : 0

    return {
      total: filteredTasks.value.length,
      active,
      paused,
      totalRuns,
      successfulRuns,
      successRate,
    }
  })

  const getActionKey = (action: string, id: number) => `${action}-${id}`
  const isActionLoading = (action: string, id: number) =>
    Boolean(actionLoading[getActionKey(action, id)])
  const setActionLoading = (action: string, id: number, value: boolean) => {
    actionLoading[getActionKey(action, id)] = value
  }

  const formatDateTime = (value?: string | null) => {
    if (!value) return '-'
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
  }

  const formatInterval = (seconds?: number | null) => {
    const totalSeconds = Number(seconds || 0)
    if (!totalSeconds) return '-'
    if (totalSeconds < 3600) return `${Math.round(totalSeconds / 60)} 分钟`
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.round((totalSeconds % 3600) / 60)
    return minutes ? `${hours} 小时 ${minutes} 分钟` : `${hours} 小时`
  }

  const getTaskTypeLabel = (value: string) =>
    value === 'TEST_SUITE' ? '测试套件' : '测试用例'

  const getTriggerTypeLabel = (value: string) =>
    value === 'CRON'
      ? 'Cron'
      : value === 'INTERVAL'
        ? '固定间隔'
        : value === 'ONCE'
          ? '单次执行'
          : value || '-'

  const getNotificationLabel = (value: string) => {
    if (value === 'email') return '邮件'
    if (value === 'webhook') return 'Webhook'
    if (value === 'both') return '邮件 + Webhook'
    return value || '未开启'
  }

  const getNotificationColor = (value: string) =>
    value === 'email'
      ? 'arcoblue'
      : value === 'webhook'
        ? 'green'
        : value === 'both'
          ? 'orange'
          : 'gray'

  const getStatusColor = (value: string) =>
    value === 'ACTIVE'
      ? 'green'
      : value === 'PAUSED'
        ? 'orange'
        : value === 'FAILED'
          ? 'red'
          : value === 'COMPLETED'
            ? 'arcoblue'
            : 'gray'

  const getNotificationStatusColor = (value: string) =>
    value === 'success'
      ? 'green'
      : value === 'failed'
        ? 'red'
        : value === 'pending'
          ? 'orange'
          : 'gray'

  const getTaskTarget = (task: AppScheduledTask) =>
    task.test_suite_name || task.test_case_name || '-'

  const getPackageLabel = (task: AppScheduledTask) =>
    `应用包：${task.app_package_name || '未指定'}`

  const getTriggerSummary = (task: AppScheduledTask) => {
    if (task.trigger_type === 'CRON') return task.cron_expression || '-'
    if (task.trigger_type === 'INTERVAL') return `每 ${formatInterval(task.interval_seconds)} 执行一次`
    return formatDateTime(task.execute_at)
  }

  const getNotificationSummary = (task: AppScheduledTask) => {
    if (!task.notification_type) return '未开启通知'
    if (!task.notify_emails.length) return '未填写接收人'
    return task.notify_emails.join(', ')
  }

  const getExecutionIds = (task: AppScheduledTask) => {
    const ids = task.last_result.execution_ids || []
    return ids.filter((item): item is number => Number.isFinite(Number(item)))
  }

  const getPrimaryExecutionId = (task: AppScheduledTask) =>
    task.last_result.execution_id || getExecutionIds(task)[0] || undefined

  const hasExecutionResult = (task: AppScheduledTask) =>
    Boolean(getPrimaryExecutionId(task) || (task.task_type === 'TEST_SUITE' && task.test_suite_id))

  const hasLatestReport = (task: AppScheduledTask) => Boolean(getPrimaryExecutionId(task))

  const getTaskSuccessRate = (task: AppScheduledTask) => {
    const totalRuns = Number(task.total_runs || 0)
    return totalRuns
      ? Math.round((Number(task.successful_runs || 0) / totalRuns) * 1000) / 10
      : 0
  }

  const getLastResultMeta = (task: AppScheduledTask): ScheduledTaskResultMeta => {
    if (task.error_message) return { label: '触发失败', color: 'red' }
    if (task.last_result.status === 'triggered') return { label: '已触发', color: 'arcoblue' }
    if (task.total_runs > 0) return { label: '已执行', color: 'green' }
    return { label: '暂无记录', color: 'gray' }
  }

  const getLastResultSummary = (task: AppScheduledTask) => {
    if (task.error_message) return task.error_message
    if (task.last_result.execution_id) {
      return `最近已触发执行 #${task.last_result.execution_id}`
    }
    if (getExecutionIds(task).length) {
      return `最近一次触发了 ${getExecutionIds(task).length} 条套件执行记录`
    }
    if (task.total_runs) {
      return `累计触发 ${task.total_runs} 次，成功 ${task.successful_runs} 次`
    }
    return '暂无最近结果'
  }

  const getNotificationDetail = (item: AppNotificationLog) => {
    if (typeof item.response_info.detail === 'string' && item.response_info.detail) {
      return item.response_info.detail
    }
    if (item.notification_content) {
      return item.notification_content.slice(0, 120)
    }
    return '暂无详细通知内容'
  }

  const getPrimaryExecutionIdFromLog = (item: AppNotificationLog) =>
    item.response_info.execution_id || item.response_info.execution_ids?.[0] || undefined

  const resetForm = () => {
    form.id = 0
    form.name = ''
    form.description = ''
    form.task_type = 'TEST_SUITE'
    form.trigger_type = 'CRON'
    form.cron_expression = '0 0 * * *'
    form.interval_seconds = 3600
    form.execute_at = ''
    form.device_id = devices.value[0]?.id
    form.package_id = undefined
    form.test_suite_id = undefined
    form.test_case_id = undefined
    form.notify_on_success = false
    form.notify_on_failure = true
    form.notification_type = 'email'
    form.status = 'ACTIVE'
    notifyEmailsText.value = ''
  }

  const resetFilters = () => {
    filters.search = ''
    filters.status = ''
    filters.task_type = ''
    filters.trigger_type = ''
    pagination.current = 1
    void loadData()
  }

  const handleSearch = () => {
    pagination.current = 1
    void loadData()
  }

  const parseNotifyEmails = () =>
    notifyEmailsText.value
      .split(/[\n,;]+/)
      .map(item => item.trim())
      .filter(Boolean)

  const syncTaskFromList = (taskId: number) => {
    const matched = tasks.value.find(item => item.id === taskId)
    if (matched) {
      currentTask.value = matched
    }
  }

  const loadData = async () => {
    if (!projectStore.currentProjectId) {
      tasks.value = []
      currentTask.value = null
      taskNotifications.value = []
      return
    }

    loading.value = true
    try {
      const [taskList, suiteList, caseList, deviceList, packageList] = await Promise.all([
        AppAutomationService.getScheduledTasks(projectStore.currentProjectId, {
          search: filters.search || undefined,
          status: filters.status || undefined,
          task_type: filters.task_type || undefined,
          trigger_type: filters.trigger_type || undefined,
        }),
        AppAutomationService.getTestSuites(projectStore.currentProjectId),
        AppAutomationService.getTestCases(projectStore.currentProjectId),
        AppAutomationService.getDevices(),
        AppAutomationService.getPackages(projectStore.currentProjectId),
      ])

      tasks.value = taskList
      suites.value = suiteList
      testCases.value = caseList
      devices.value = deviceList
      packages.value = packageList

      if (currentTask.value?.id) {
        syncTaskFromList(currentTask.value.id)
      }
    } catch (error: any) {
      Message.error(error.message || '加载定时任务失败')
    } finally {
      loading.value = false
    }
  }

  const updateRouteQuery = (queryPatch: Record<string, string | undefined>) =>
    router.replace({
      path: '/app-automation',
      query: {
        ...route.query,
        ...queryPatch,
      },
    })

  const loadTaskDetail = async (taskId: number, options: { syncRoute?: boolean } = {}) => {
    detailLoading.value = true
    taskNotificationsLoading.value = true

    try {
      const [task, notifications] = await Promise.all([
        AppAutomationService.getScheduledTask(taskId),
        AppAutomationService.getNotificationLogs({ task_id: taskId }),
      ])
      currentTask.value = task
      taskNotifications.value = notifications
      detailVisible.value = true

      if (options.syncRoute !== false) {
        await updateRouteQuery({ tab: 'scheduled-tasks', taskId: String(taskId) })
      }
    } catch (error: any) {
      Message.error(error.message || '加载任务详情失败')
    } finally {
      detailLoading.value = false
      taskNotificationsLoading.value = false
    }
  }

  const refreshCurrentTaskIfNeeded = async (taskId: number) => {
    if (detailVisible.value && currentTask.value?.id === taskId) {
      await loadTaskDetail(taskId, { syncRoute: false })
    }
  }

  const openCreate = () => {
    resetForm()
    visible.value = true
  }

  const openDetail = (record: AppScheduledTask) => {
    void loadTaskDetail(record.id)
  }

  const openEdit = (record: AppScheduledTask) => {
    form.id = record.id
    form.name = record.name
    form.description = record.description
    form.task_type = record.task_type
    form.trigger_type = record.trigger_type
    form.cron_expression = record.cron_expression || '0 0 * * *'
    form.interval_seconds = record.interval_seconds || 3600
    form.execute_at = record.execute_at || ''
    form.device_id = record.device_id ?? undefined
    form.package_id = record.package_id ?? undefined
    form.test_suite_id = record.test_suite_id ?? undefined
    form.test_case_id = record.test_case_id ?? undefined
    form.notify_on_success = record.notify_on_success
    form.notify_on_failure = record.notify_on_failure
    form.notification_type =
      record.notification_type ||
      (record.notify_on_success || record.notify_on_failure ? 'email' : '')
    form.status = ['ACTIVE', 'PAUSED'].includes(record.status) ? record.status : 'ACTIVE'
    notifyEmailsText.value = record.notify_emails.join(', ')
    visible.value = true
  }

  const validateForm = () => {
    if (!form.name.trim()) {
      Message.warning('请输入任务名称')
      return false
    }
    if (!form.device_id) {
      Message.warning('请选择执行设备')
      return false
    }
    if (form.task_type === 'TEST_SUITE' && !form.test_suite_id) {
      Message.warning('请选择测试套件')
      return false
    }
    if (form.task_type === 'TEST_CASE' && !form.test_case_id) {
      Message.warning('请选择测试用例')
      return false
    }
    if (form.trigger_type === 'CRON' && !form.cron_expression.trim()) {
      Message.warning('请输入 Cron 表达式')
      return false
    }
    if (form.trigger_type === 'INTERVAL' && !form.interval_seconds) {
      Message.warning('请输入间隔秒数')
      return false
    }
    if (form.trigger_type === 'ONCE' && !form.execute_at) {
      Message.warning('请选择一次性执行时间')
      return false
    }
    if (notificationsEnabled.value && !form.notification_type) {
      Message.warning('请选择通知类型')
      return false
    }
    if (needsEmailRecipients.value && !parseNotifyEmails().length) {
      Message.warning('请至少填写一个通知邮箱')
      return false
    }
    return true
  }

  const buildPayload = () => ({
    project_id: projectStore.currentProjectId || 0,
    name: form.name.trim(),
    description: form.description.trim(),
    task_type: form.task_type,
    trigger_type: form.trigger_type,
    cron_expression: form.trigger_type === 'CRON' ? form.cron_expression.trim() : '',
    interval_seconds: form.trigger_type === 'INTERVAL' ? form.interval_seconds : null,
    execute_at: form.trigger_type === 'ONCE' ? form.execute_at || null : null,
    device_id: form.device_id ?? null,
    package_id: form.package_id ?? null,
    test_suite_id: form.task_type === 'TEST_SUITE' ? form.test_suite_id ?? null : null,
    test_case_id: form.task_type === 'TEST_CASE' ? form.test_case_id ?? null : null,
    notify_on_success: form.notify_on_success,
    notify_on_failure: form.notify_on_failure,
    notification_type: notificationsEnabled.value ? form.notification_type || '' : '',
    notify_emails: needsEmailRecipients.value ? parseNotifyEmails() : [],
    status: form.status,
    created_by: authStore.currentUser?.username || 'FlyTest',
  })

  const saveTask = async () => {
    if (!projectStore.currentProjectId || !validateForm()) {
      return false
    }

    try {
      const payload = buildPayload()
      if (form.id) {
        await AppAutomationService.updateScheduledTask(form.id, payload)
        Message.success('定时任务已更新')
      } else {
        await AppAutomationService.createScheduledTask(payload)
        Message.success('定时任务已创建')
      }
      await loadData()
      if (form.id) {
        await refreshCurrentTaskIfNeeded(form.id)
      }
      return true
    } catch (error: any) {
      Message.error(error.message || '保存定时任务失败')
      return false
    }
  }

  const handleBeforeOk = (done: (closed: boolean) => void) => {
    void (async () => {
      const success = await saveTask()
      done(success)
    })()
  }

  const goToExecutionContext = async (executionId?: number, suiteId?: number | null) => {
    await router.replace({
      path: '/app-automation',
      query: {
        ...route.query,
        tab: 'executions',
        taskId: undefined,
        executionId: executionId ? String(executionId) : undefined,
        suiteId: suiteId ? String(suiteId) : undefined,
      },
    })
  }

  const openLatestExecution = (task: AppScheduledTask) => {
    const executionId = getPrimaryExecutionId(task)
    if (executionId) {
      void goToExecutionContext(executionId, task.last_result.test_suite_id || task.test_suite_id)
      return
    }
    if (task.task_type === 'TEST_SUITE' && task.test_suite_id) {
      void goToExecutionContext(undefined, task.test_suite_id)
      return
    }
    Message.warning('当前任务还没有可查看的执行记录')
  }

  const openLatestReport = (task: AppScheduledTask) => {
    const executionId = getPrimaryExecutionId(task)
    if (!executionId) {
      Message.warning('当前任务还没有可打开的报告')
      return
    }
    window.open(AppAutomationService.getExecutionReportUrl(executionId), '_blank', 'noopener')
  }

  const openTaskNotifications = async (task: AppScheduledTask) => {
    await router.replace({
      path: '/app-automation',
      query: {
        ...route.query,
        tab: 'notifications',
        taskId: String(task.id),
        executionId: undefined,
        suiteId: undefined,
      },
    })
  }

  const openNotificationExecution = (item: AppNotificationLog) => {
    const executionId = getPrimaryExecutionIdFromLog(item)
    if (!executionId) {
      Message.warning('该通知暂时没有关联执行记录')
      return
    }
    void goToExecutionContext(executionId, item.response_info.test_suite_id)
  }

  const runNow = async (id: number) => {
    setActionLoading('run', id, true)
    try {
      const result = (await AppAutomationService.runScheduledTaskNow(
        id,
        authStore.currentUser?.username || 'FlyTest',
      )) as AppScheduledTaskRunResult

      const createdCount =
        result.trigger_payload?.execution_ids?.length ||
        (result.trigger_payload?.execution_id ? 1 : 0)
      Message.success(
        createdCount > 1
          ? `任务已触发，已创建 ${createdCount} 条执行记录`
          : '定时任务已触发执行',
      )
      await loadData()
      await refreshCurrentTaskIfNeeded(id)
    } catch (error: any) {
      Message.error(error.message || '执行定时任务失败')
    } finally {
      setActionLoading('run', id, false)
    }
  }

  const pause = async (id: number) => {
    setActionLoading('pause', id, true)
    try {
      await AppAutomationService.pauseScheduledTask(id)
      Message.success('任务已暂停')
      await loadData()
      await refreshCurrentTaskIfNeeded(id)
    } catch (error: any) {
      Message.error(error.message || '暂停任务失败')
    } finally {
      setActionLoading('pause', id, false)
    }
  }

  const resume = async (id: number) => {
    setActionLoading('resume', id, true)
    try {
      await AppAutomationService.resumeScheduledTask(id)
      Message.success('任务已恢复')
      await loadData()
      await refreshCurrentTaskIfNeeded(id)
    } catch (error: any) {
      Message.error(error.message || '恢复任务失败')
    } finally {
      setActionLoading('resume', id, false)
    }
  }

  const remove = (id: number) => {
    Modal.confirm({
      title: '删除定时任务',
      content: '确认删除该定时任务吗？',
      onOk: async () => {
        setActionLoading('delete', id, true)
        try {
          await AppAutomationService.deleteScheduledTask(id)
          Message.success('定时任务已删除')
          if (currentTask.value?.id === id) {
            detailVisible.value = false
            currentTask.value = null
            taskNotifications.value = []
          }
          await loadData()
        } catch (error: any) {
          Message.error(error.message || '删除定时任务失败')
        } finally {
          setActionLoading('delete', id, false)
        }
      },
    })
  }

  const syncFromRoute = async () => {
    if (route.query.tab !== 'scheduled-tasks' || !projectStore.currentProjectId) {
      return
    }
    const taskId = Number(route.query.taskId || 0)
    if (!taskId || currentTask.value?.id === taskId) {
      return
    }
    await loadTaskDetail(taskId, { syncRoute: false })
  }

  watch(
    () => filteredTasks.value.length,
    total => {
      const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize))
      if (pagination.current > maxPage) {
        pagination.current = maxPage
      }
    },
  )

  watch(
    () => detailVisible.value,
    value => {
      if (!value && route.query.tab === 'scheduled-tasks' && route.query.taskId) {
        void updateRouteQuery({ taskId: undefined })
      }
    },
  )

  watch(
    () => form.task_type,
    value => {
      if (value === 'TEST_SUITE') {
        form.test_case_id = undefined
      } else {
        form.test_suite_id = undefined
      }
    },
  )

  watch(
    () => form.trigger_type,
    value => {
      if (value !== 'CRON') {
        form.cron_expression = '0 0 * * *'
      }
      if (value !== 'INTERVAL') {
        form.interval_seconds = 3600
      }
      if (value !== 'ONCE') {
        form.execute_at = ''
      }
    },
  )

  watch(notificationsEnabled, enabled => {
    if (!enabled) {
      form.notification_type = ''
      notifyEmailsText.value = ''
    } else if (!form.notification_type) {
      form.notification_type = 'email'
    }
  })

  watch(
    () => [route.query.tab, route.query.taskId, projectStore.currentProjectId],
    () => {
      void syncFromRoute()
    },
    { immediate: true },
  )

  watch(
    () => projectStore.currentProjectId,
    () => {
      pagination.current = 1
      detailVisible.value = false
      currentTask.value = null
      taskNotifications.value = []
      void loadData()
    },
    { immediate: true },
  )

  return {
    projectStore,
    loading,
    visible,
    detailVisible,
    detailLoading,
    taskNotificationsLoading,
    notifyEmailsText,
    suites,
    testCases,
    devices,
    packages,
    currentTask,
    filters,
    pagination,
    form,
    notificationsEnabled,
    needsEmailRecipients,
    recentTaskNotifications,
    filteredTasks,
    pagedTasks,
    statistics,
    isActionLoading,
    formatDateTime,
    getTaskTypeLabel,
    getTriggerTypeLabel,
    getNotificationLabel,
    getNotificationColor,
    getStatusColor,
    getNotificationStatusColor,
    getTaskTarget,
    getPackageLabel,
    getTriggerSummary,
    getNotificationSummary,
    hasExecutionResult,
    hasLatestReport,
    getTaskSuccessRate,
    getLastResultMeta,
    getLastResultSummary,
    getNotificationDetail,
    getPrimaryExecutionIdFromLog,
    loadData,
    openCreate,
    openDetail,
    openEdit,
    handleSearch,
    resetFilters,
    handleBeforeOk,
    openLatestExecution,
    openLatestReport,
    openTaskNotifications,
    openNotificationExecution,
    runNow,
    pause,
    resume,
    remove,
  }
}
