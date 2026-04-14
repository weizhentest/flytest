import type { AppExecution, AppTestSuite } from '../../types'

export interface ReportsHeaderBarEmits {
  refresh: []
}

export interface ReportsSuitePanelEmits {
  search: []
  reset: []
  'open-detail': [suite: AppTestSuite]
  'open-executions': [suite: AppTestSuite]
  'open-report': [suite: AppTestSuite]
}

export interface ReportsExecutionPanelEmits {
  search: []
  reset: []
  'open-detail': [id: number]
  'open-report': [record: AppExecution]
}

export interface ReportsSuiteExecutionsDialogEmits {
  'open-detail': [id: number]
  'open-report': [record: AppExecution]
}

export interface ReportsExecutionDetailDialogEmits {
  'open-report': [record: AppExecution]
  'open-artifact': [record: AppExecution, relativePath: string]
}
