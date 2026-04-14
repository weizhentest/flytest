import type {
  AppAutomationTab,
  AppDashboardStatistics,
  AppExecution,
  AppScheduledTask,
} from '../../types'

export interface DashboardHeaderBarProps {
  serviceStatusTagColor: string
  serviceStatusTagText: string
  lastUpdatedText: string
  aiStatusLoading: boolean
  loading: boolean
}

export interface DashboardStatsGridProps {
  statistics: AppDashboardStatistics
  activeTaskCount: number
  pausedTaskCount: number
  failedTaskCount: number
  aiReady: boolean
  aiHasConfig: boolean
  aiCapabilityDisplay: string
}

export interface DashboardExecutionSummaryCardProps {
  statistics: AppDashboardStatistics
}

export interface DashboardAiOverviewCardProps {
  aiStatusTitle: string
  aiStatusDescription: string
  aiStatusTagColor: string
  aiStatusTagText: string
  aiConfigDisplay: string
  aiProviderDisplay: string
  aiModelDisplay: string
  aiCapabilityDisplay: string
  aiEndpointDisplay: string
}

export interface DashboardTaskSnapshotCardProps {
  tasks: AppScheduledTask[]
  getTaskTypeLabel: (value: string) => string
  getTriggerSummary: (task: AppScheduledTask) => string
  getTaskTarget: (task: AppScheduledTask) => string
  formatDateTime: (value?: string | null) => string
  getTaskStatusColor: (value: string) => string
  getPrimaryExecutionId: (task: AppScheduledTask) => number | undefined
  isTaskActionLoading: (action: string, taskId: number) => boolean
}

export interface DashboardRecentExecutionsCardProps {
  executions: AppExecution[]
  getExecutionStatusColor: (record: AppExecution) => string
  getExecutionStatusLabel: (record: AppExecution) => string
  formatProgress: (value?: number | null) => number
  formatDateTime: (value?: string | null) => string
  canOpenReport: (record: AppExecution) => boolean
}

export interface DashboardQuickActionItem {
  tab: AppAutomationTab
  title: string
  description: string
}
