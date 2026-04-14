import type {
  AppDevice,
  AppNotificationLog,
  AppPackage,
  AppScheduledTask,
  AppTestCase,
  AppTestSuite,
} from '../../types'

export interface ScheduledTaskFilters {
  search: string
  status: string
  task_type: string
  trigger_type: string
}

export interface ScheduledTaskPagination {
  current: number
  pageSize: number
}

export interface ScheduledTaskFormModel {
  id: number
  name: string
  description: string
  task_type: string
  trigger_type: string
  cron_expression: string
  interval_seconds: number
  execute_at: string
  device_id: number | undefined
  package_id: number | undefined
  test_suite_id: number | undefined
  test_case_id: number | undefined
  notify_on_success: boolean
  notify_on_failure: boolean
  notification_type: string
  status: string
}

export interface ScheduledTaskStatistics {
  total: number
  active: number
  paused: number
  successRate: number
  successfulRuns: number
  totalRuns: number
}

export interface ScheduledTaskResultMeta {
  label: string
  color: string
}

export interface ScheduledTaskHeaderBarProps {
  loading: boolean
}

export interface ScheduledTaskFilterCardProps {
  filters: ScheduledTaskFilters
}

export interface ScheduledTaskStatsGridProps {
  statistics: ScheduledTaskStatistics
}

export interface ScheduledTaskFormDialogProps {
  form: ScheduledTaskFormModel
  devices: AppDevice[]
  suites: AppTestSuite[]
  testCases: AppTestCase[]
  packages: AppPackage[]
  notificationsEnabled: boolean
  needsEmailRecipients: boolean
}

export interface ScheduledTasksTableCardProps {
  loading: boolean
  tasks: AppScheduledTask[]
  total: number
  formatDateTime: (value?: string | null) => string
  getTaskTypeLabel: (value: string) => string
  getTriggerTypeLabel: (value: string) => string
  getNotificationLabel: (value: string) => string
  getNotificationColor: (value: string) => string
  getStatusColor: (value: string) => string
  getTaskTarget: (task: AppScheduledTask) => string
  getPackageLabel: (task: AppScheduledTask) => string
  getTriggerSummary: (task: AppScheduledTask) => string
  getNotificationSummary: (task: AppScheduledTask) => string
  getLastResultMeta: (task: AppScheduledTask) => ScheduledTaskResultMeta
  getTaskSuccessRate: (task: AppScheduledTask) => number
  getLastResultSummary: (task: AppScheduledTask) => string
  hasExecutionResult: (task: AppScheduledTask) => boolean
  isActionLoading: (action: string, id: number) => boolean
}

export interface ScheduledTaskDetailDialogProps {
  detailLoading: boolean
  taskNotificationsLoading: boolean
  currentTask: AppScheduledTask | null
  recentTaskNotifications: AppNotificationLog[]
  formatDateTime: (value?: string | null) => string
  getTaskTypeLabel: (value: string) => string
  getTaskTarget: (task: AppScheduledTask) => string
  getNotificationLabel: (value: string) => string
  getNotificationColor: (value: string) => string
  getNotificationStatusColor: (value: string) => string
  getLastResultMeta: (task: AppScheduledTask) => ScheduledTaskResultMeta
  getTaskSuccessRate: (task: AppScheduledTask) => number
  getLastResultSummary: (task: AppScheduledTask) => string
  getNotificationDetail: (item: AppNotificationLog) => string
  getPrimaryExecutionIdFromLog: (item: AppNotificationLog) => number | undefined
  getTriggerSummary: (task: AppScheduledTask) => string
  getNotificationSummary: (task: AppScheduledTask) => string
  hasExecutionResult: (task: AppScheduledTask) => boolean
  hasLatestReport: (task: AppScheduledTask) => boolean
}
