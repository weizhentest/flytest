import type { AppDevice, AppExecution, AppTestCase, AppTestSuite } from '../../types'

export interface SuiteFilters {
  search: string
  status: string
}

export interface SuiteFormModel {
  id: number
  name: string
  description: string
  test_case_ids: number[]
}

export interface SuiteRunFormModel {
  device_id: number | undefined
}

export interface SuiteStatusMeta {
  label: string
  color: string
}

export interface SuiteExecutionArtifact {
  key: string
  relativePath: string
  message: string
  level: string
}

export interface SuiteStats {
  total: number
  running: number
  passed: number
  stopped: number
  health: number
}

export interface SuitesStatsGridProps {
  statistics: SuiteStats
}

export interface SuiteDetailDialogProps {
  selectedSuite: AppTestSuite | null
  formatDateTime: (value?: string | null) => string
  getSuiteStatusMeta: (record: AppTestSuite) => SuiteStatusMeta
  getSuiteHealthRate: (record: AppTestSuite) => number
}

export interface SuiteEditorDialogProps {
  form: SuiteFormModel
  testCases: AppTestCase[]
  selectedCases: AppTestCase[]
}

export interface SuiteExecutionDetailDialogProps {
  currentExecution: AppExecution | null
  selectedSuiteId: number | null
  executionArtifacts: SuiteExecutionArtifact[]
  formatDateTime: (value?: string | null) => string
  formatRate: (value?: number | null) => number
  formatDuration: (value?: number | null) => string
  getExecutionStatusMeta: (record: AppExecution) => SuiteStatusMeta
  canOpenReport: (record: AppExecution) => boolean
  getLogLevelColor: (value?: string) => string
}

export interface SuiteHistoryDialogProps {
  selectedSuite: AppTestSuite | null
  history: AppExecution[]
  loading: boolean
  formatDateTime: (value?: string | null) => string
  formatRate: (value?: number | null) => number
  formatDuration: (value?: number | null) => string
  getExecutionStatusMeta: (record: AppExecution) => SuiteStatusMeta
  canOpenReport: (record: AppExecution) => boolean
}

export interface SuiteRunDialogProps {
  runForm: SuiteRunFormModel
  availableDevices: AppDevice[]
}

export interface SuitesTableCardProps {
  loading: boolean
  suites: AppTestSuite[]
  formatDateTime: (value?: string | null) => string
  getSuiteStatusMeta: (record: AppTestSuite) => SuiteStatusMeta
  getSuiteHealthRate: (record: AppTestSuite) => number
}
