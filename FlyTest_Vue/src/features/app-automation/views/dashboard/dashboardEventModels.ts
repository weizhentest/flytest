import type { AppAutomationTab, AppExecution, AppScheduledTask } from '../../types'

export interface DashboardHeaderBarEmits {
  'refresh-ai-status': []
  'refresh-dashboard': []
}

export interface DashboardAiOverviewCardEmits {
  'open-scene-builder': []
  'open-llm-config': []
}

export interface DashboardTaskSnapshotCardEmits {
  'open-all': []
  'open-task': [task: AppScheduledTask]
  'run-task': [task: AppScheduledTask]
  'resume-task': [task: AppScheduledTask]
  'open-latest-execution': [task: AppScheduledTask]
}

export interface DashboardRecentExecutionsCardEmits {
  'open-all': []
  'open-execution': [executionId: number]
  'open-report': [executionId: number]
}

export interface DashboardQuickActionsCardEmits {
  'open-tab': [tab: AppAutomationTab]
}
