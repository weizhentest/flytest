import type { AppNotificationLog } from '../../types'

export interface NotificationsHeaderBarEmits {
  refresh: []
}

export interface NotificationsTaskContextAlertEmits {
  'open-task-detail': [taskId: number]
  'clear-task-context': []
}

export interface NotificationsFilterCardEmits {
  search: []
  reset: []
}

export interface NotificationsTableCardEmits {
  'view-detail': [record: AppNotificationLog]
  'open-task-detail': [taskId: number]
  'open-execution': [record: AppNotificationLog]
}

export interface NotificationDetailDialogEmits {
  'open-task-detail': [taskId: number]
  'open-execution': [record: AppNotificationLog]
}
