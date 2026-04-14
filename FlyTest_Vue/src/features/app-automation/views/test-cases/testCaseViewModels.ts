import type { AppDevice, AppExecution, AppPackage, AppTestCase } from '../../types'

export interface TestCaseFormModel {
  id: number
  name: string
  description: string
  package_id: number | undefined
  timeout: number
  retry_count: number
  variablesText: string
  uiFlowText: string
}

export interface TestCaseExecuteFormModel {
  device_id: number | undefined
}

export interface TestCaseStats {
  total: number
  passed: number
  failed: number
  pending: number
}

export interface TestCasesHeaderBarProps {
  packages: AppPackage[]
}

export interface TestCasesStatsGridProps {
  statistics: TestCaseStats
}

export interface TestCasesBatchBarProps {
  selectedCount: number
}

export interface TestCasesTableCardProps {
  cases: AppTestCase[]
  loading: boolean
  formatDateTime: (value?: string | null) => string
  getStepCount: (record: AppTestCase) => number
  getResultLabel: (result?: string) => string
  getResultColor: (result?: string) => string
}

export interface TestCasesRecentExecutionsCardProps {
  executions: AppExecution[]
  loading: boolean
  formatDateTime: (value?: string | null) => string
  getResultColor: (result?: string) => string
  getExecutionResultLabel: (record: AppExecution) => string
  formatProgress: (value?: number | null) => number
  formatRate: (value?: number | null) => number
  canOpenExecutionReport: (record: AppExecution) => boolean
}

export interface TestCaseEditorDialogProps {
  form: TestCaseFormModel
  packages: AppPackage[]
}

export interface TestCaseExecuteDialogProps {
  mode: 'single' | 'batch'
  executeForm: TestCaseExecuteFormModel
  availableDevices: AppDevice[]
}
