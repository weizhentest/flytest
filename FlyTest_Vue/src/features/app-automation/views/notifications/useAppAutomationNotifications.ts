import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { AppAutomationService } from '../../services/appAutomationService'
import { replaceAppAutomationQuery } from '../appAutomationNavigation'
import type { AppNotificationLog, AppScheduledTask } from '../../types'
import type {
  NotificationFilters,
  NotificationPaginationState,
  NotificationParsedContentItem,
  NotificationStatistics,
} from './notificationViewModels'

export function useAppAutomationNotifications() {
  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const retryingId = ref<number | null>(null)
  const detailVisible = ref(false)
  const currentLog = ref<AppNotificationLog | null>(null)
  const logs = ref<AppNotificationLog[]>([])
  const taskContext = ref<AppScheduledTask | null>(null)

  const filters = reactive<NotificationFilters>({
    search: '',
    status: '',
    notification_type: '',
    start_date: '',
    end_date: '',
  })

  const pagination = reactive<NotificationPaginationState>({
    current: 1,
    pageSize: 10,
  })

  const currentTaskId = computed(() => {
    const value = Number(route.query.taskId || 0)
    return value > 0 ? value : null
  })

  const recipientSummary = (record: AppNotificationLog) =>
    record.recipient_info
      .map(item => item.email || item.name || '')
      .filter(Boolean)
      .join(', ') || '-'

  const filteredLogs = computed(() => {
    const keyword = filters.search.trim().toLowerCase()

    return logs.value.filter(log => {
      if (filters.status && log.status !== filters.status) return false

      const notificationType = String(log.actual_notification_type || log.notification_type || '')
      if (filters.notification_type && notificationType !== filters.notification_type) return false

      if (!keyword) return true

      return [
        log.task_name,
        log.notification_content,
        notificationType,
        recipientSummary(log),
        log.error_message,
        JSON.stringify(log.response_info || {}),
      ]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    })
  })

  const pagedLogs = computed(() => {
    const start = (pagination.current - 1) * pagination.pageSize
    return filteredLogs.value.slice(start, start + pagination.pageSize)
  })

  const statistics = computed<NotificationStatistics>(() => ({
    total: filteredLogs.value.length,
    success: filteredLogs.value.filter(item => item.status === 'success').length,
    failed: filteredLogs.value.filter(item => item.status === 'failed').length,
    retried: filteredLogs.value.filter(item => item.is_retried).length,
  }))

  const parsedContent = computed<NotificationParsedContentItem[]>(() => {
    const content = currentLog.value?.notification_content
    if (!content) return []

    try {
      const payload = JSON.parse(content)
      const rawText =
        payload.markdown?.content ||
        payload.markdown?.text ||
        payload.card?.elements?.[0]?.text?.content ||
        ''

      if (!rawText) {
        return []
      }

      return rawText
        .split('\n')
        .map(item => item.trim())
        .filter(item => item && !item.includes('**'))
        .map(item => {
          const index = item.indexOf(':')
          return index > 0
            ? { label: item.slice(0, index).trim(), value: item.slice(index + 1).trim() }
            : null
        })
        .filter(Boolean) as NotificationParsedContentItem[]
    } catch {
      return content
        .split('\n')
        .map(item => item.trim())
        .filter(Boolean)
        .map(item => {
          const index = item.indexOf(':')
          return index > 0
            ? { label: item.slice(0, index).trim(), value: item.slice(index + 1).trim() }
            : null
        })
        .filter(Boolean) as NotificationParsedContentItem[]
    }
  })

  const formatDateTime = (value?: string | null) => {
    if (!value) return '-'
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
  }

  const getTaskTypeLabel = (value: string) => {
    if (value === 'TEST_SUITE') return '测试套件'
    if (value === 'TEST_CASE') return '测试用例'
    return value || '-'
  }

  const getNotificationTypeLabel = (value: string) => {
    if (value === 'email') return '邮件'
    if (value === 'webhook') return 'Webhook'
    if (value === 'both') return '邮件 + Webhook'
    return value || '-'
  }

  const getNotificationTypeColor = (value: string) => {
    if (value === 'email') return 'arcoblue'
    if (value === 'webhook') return 'green'
    if (value === 'both') return 'orange'
    return 'gray'
  }

  const getStatusColor = (value: string) => {
    if (value === 'success') return 'green'
    if (value === 'failed') return 'red'
    if (value === 'pending') return 'orange'
    return 'gray'
  }

  const getPrimaryExecutionId = (record: AppNotificationLog) =>
    record.response_info.execution_id || record.response_info.execution_ids?.[0] || undefined

  const getDeliverySummary = (record: AppNotificationLog) => {
    if (record.error_message) return record.error_message
    if (record.response_info.retry_status)
      return `重试状态：${String(record.response_info.retry_status)}`
    if (record.response_info.detail) return String(record.response_info.detail)
    return `重试 ${record.retry_count || 0} 次`
  }

  const loadTaskContext = async () => {
    if (!currentTaskId.value) {
      taskContext.value = null
      return
    }

    try {
      taskContext.value = await AppAutomationService.getScheduledTask(currentTaskId.value)
    } catch {
      taskContext.value = null
    }
  }

  const loadData = async () => {
    loading.value = true
    try {
      logs.value = await AppAutomationService.getNotificationLogs({
        search: filters.search || undefined,
        status: filters.status || undefined,
        notification_type: filters.notification_type || undefined,
        task_id: currentTaskId.value || undefined,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
      })
    } catch (error: any) {
      Message.error(error.message || '加载通知日志失败')
    } finally {
      loading.value = false
    }
  }

  const handleSearch = () => {
    pagination.current = 1
    void loadData()
  }

  const resetFilters = () => {
    filters.search = ''
    filters.status = ''
    filters.notification_type = ''
    filters.start_date = ''
    filters.end_date = ''
    pagination.current = 1
    void loadData()
  }

  const openTaskDetail = async (taskId: number) => {
    await replaceAppAutomationQuery(route, router, {
      tab: 'scheduled-tasks',
      taskId: String(taskId),
      executionId: undefined,
      suiteId: undefined,
    })
  }

  const clearTaskContext = async () => {
    await replaceAppAutomationQuery(route, router, {
      taskId: undefined,
    })
  }

  const openExecution = (record: AppNotificationLog) => {
    const executionId = getPrimaryExecutionId(record)
    if (!executionId) {
      Message.warning('该通知没有关联执行记录')
      return
    }

    void replaceAppAutomationQuery(route, router, {
      tab: 'executions',
      taskId: undefined,
      executionId: String(executionId),
      suiteId: record.response_info.test_suite_id
        ? String(record.response_info.test_suite_id)
        : undefined,
    })
  }

  const retry = async (id: number) => {
    retryingId.value = id
    try {
      const updated = await AppAutomationService.retryNotification(id)
      Message.success('通知已重试')
      logs.value = logs.value.map(item => (item.id === updated.id ? updated : item))
      if (currentLog.value?.id === updated.id) {
        currentLog.value = updated
      }
      await loadData()
    } catch (error: any) {
      Message.error(error.message || '重试通知失败')
    } finally {
      retryingId.value = null
    }
  }

  const viewDetail = (record: AppNotificationLog) => {
    currentLog.value = record
    detailVisible.value = true
  }

  watch(
    () => route.query.tab,
    tab => {
      if (tab === 'notifications') {
        return
      }
      detailVisible.value = false
    },
  )

  watch(
    () => detailVisible.value,
    value => {
      if (!value) {
        currentLog.value = null
      }
    },
  )

  watch(
    () => filteredLogs.value.length,
    total => {
      const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize))
      if (pagination.current > maxPage) {
        pagination.current = maxPage
      }
    },
  )

  watch(
    () => route.query.taskId,
    () => {
      pagination.current = 1
      void Promise.all([loadTaskContext(), loadData()])
    },
    { immediate: true },
  )

  return {
    loading,
    retryingId,
    detailVisible,
    currentLog,
    taskContext,
    filters,
    pagination,
    filteredLogs,
    pagedLogs,
    statistics,
    parsedContent,
    formatDateTime,
    getTaskTypeLabel,
    getNotificationTypeLabel,
    getNotificationTypeColor,
    getStatusColor,
    getPrimaryExecutionId,
    getDeliverySummary,
    recipientSummary,
    loadData,
    handleSearch,
    resetFilters,
    openTaskDetail,
    clearTaskContext,
    openExecution,
    retry,
    viewDetail,
  }
}
