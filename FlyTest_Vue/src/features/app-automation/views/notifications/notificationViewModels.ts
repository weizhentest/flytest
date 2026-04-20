import type { AppNotificationLog, AppScheduledTask } from '../../types'

export interface NotificationFilters {
  search: string
  status: string
  notification_type: string
  start_date: string
  end_date: string
}

export interface NotificationPaginationState {
  current: number
  pageSize: number
}

export interface NotificationParsedContentItem {
  label: string
  value: string
}

export interface NotificationStatistics {
  total: number
  success: number
  failed: number
  retried: number
}

export interface NotificationsHeaderBarProps {
  loading: boolean
}

export interface NotificationsTaskContextAlertProps {
  taskContext: AppScheduledTask | null
}

export interface NotificationsFilterCardProps {
  filters: NotificationFilters
}

export interface NotificationsStatsGridProps {
  statistics: NotificationStatistics
}

export interface NotificationsTableCardProps {
  loading: boolean
  logs: AppNotificationLog[]
  total: number
  formatDateTime: (value?: string | null) => string
  getTaskTypeLabel: (value: string) => string
  getNotificationTypeLabel: (value: string) => string
  getNotificationTypeColor: (value: string) => string
  getStatusColor: (value: string) => string
  recipientSummary: (record: AppNotificationLog) => string
  getDeliverySummary: (record: AppNotificationLog) => string
  getPrimaryExecutionId: (record: AppNotificationLog) => number | undefined
}

export interface NotificationDetailDialogProps {
  currentLog: AppNotificationLog | null
  parsedContent: NotificationParsedContentItem[]
  formatDateTime: (value?: string | null) => string
  getTaskTypeLabel: (value: string) => string
  getNotificationTypeLabel: (value: string) => string
  recipientSummary: (record: AppNotificationLog) => string
  getPrimaryExecutionId: (record: AppNotificationLog) => number | undefined
}
