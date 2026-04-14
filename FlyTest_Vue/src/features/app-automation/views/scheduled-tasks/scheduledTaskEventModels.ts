import type { AppNotificationLog, AppScheduledTask } from '../../types'

export interface ScheduledTaskHeaderBarEmits {
  refresh: []
  create: []
}

export interface ScheduledTaskFilterCardEmits {
  search: []
  reset: []
}

export interface ScheduledTaskFormDialogEmits {
  'before-ok': [done: (closed: boolean) => void]
}

export interface ScheduledTaskTableCardEmits {
  'open-detail': [task: AppScheduledTask]
  'run-now': [id: number]
  'open-latest-execution': [task: AppScheduledTask]
  'open-edit': [task: AppScheduledTask]
  'pause': [id: number]
  'resume': [id: number]
  'remove': [id: number]
}

export interface ScheduledTaskDetailDialogEmits {
  'open-latest-execution': [task: AppScheduledTask]
  'open-latest-report': [task: AppScheduledTask]
  'open-task-notifications': [task: AppScheduledTask]
  'open-notification-execution': [item: AppNotificationLog]
}
