import type { AppExecution, AppNotificationLog, AppTestSuite } from '../../types'

export interface ReportsHeaderBarProps {
  loading: boolean
  lastUpdatedText: string
}

export interface ReportStatusMeta {
  label: string
  color: string
}

export interface ReportSuiteFilters {
  search: string
  status: string
}

export interface ReportCaseFilters {
  search: string
  status: string
  source: string
}

export interface ReportPaginationState {
  current: number
  pageSize: number
}

export interface ReportSuiteStats {
  total: number
  running: number
  passed: number
  health: number
}

export interface ReportCaseStats {
  total: number
  passed: number
  failed: number
  passRate: number
}

export interface ReportExecutionArtifact {
  key: string
  relativePath: string
  message: string
  level: string
}

export interface ReportsSuitePanelProps {
  loading: boolean
  filters: ReportSuiteFilters
  pagination: ReportPaginationState
  statistics: ReportSuiteStats
  suites: AppTestSuite[]
  total: number
  formatDateTime: (value?: string | null) => string
  getSuiteStatus: (suite: AppTestSuite) => ReportStatusMeta
  getSuiteHealthRate: (suite: AppTestSuite) => number
}

export interface ReportsExecutionPanelProps {
  loading: boolean
  filters: ReportCaseFilters
  pagination: ReportPaginationState
  statistics: ReportCaseStats
  executions: AppExecution[]
  total: number
  formatDateTime: (value?: string | null) => string
  formatRate: (value?: number | null) => number
  formatDuration: (value?: number | null) => string
  getExecutionSource: (record: AppExecution) => string
  getExecutionStatus: (record: AppExecution) => ReportStatusMeta
  canOpenReport: (record: AppExecution) => boolean
}

export interface ReportsSuiteDetailDialogProps {
  selectedSuite: AppTestSuite | null
  formatDateTime: (value?: string | null) => string
  getSuiteStatus: (suite: AppTestSuite) => ReportStatusMeta
  getSuiteHealthRate: (suite: AppTestSuite) => number
}

export interface ReportsSuiteExecutionsDialogProps {
  selectedSuite: AppTestSuite | null
  suiteExecutions: AppExecution[]
  loading: boolean
  formatRate: (value?: number | null) => number
  getExecutionStatus: (record: AppExecution) => ReportStatusMeta
  canOpenReport: (record: AppExecution) => boolean
}

export interface ReportsExecutionDetailDialogProps {
  currentExecution: AppExecution | null
  executionArtifacts: ReportExecutionArtifact[]
  executionLogText: string
  formatDateTime: (value?: string | null) => string
  formatRate: (value?: number | null) => number
  formatDuration: (value?: number | null) => string
  getExecutionStatus: (record: AppExecution) => ReportStatusMeta
  getExecutionSource: (record: AppExecution) => string
  canOpenReport: (record: AppExecution) => boolean
}
