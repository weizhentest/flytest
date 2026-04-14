import type { AppExecution, AppTestSuite } from '../../types'

export interface SuitesHeaderBarEmits {
  search: []
  reset: []
  refresh: []
  create: []
}

export interface SuiteEditorDialogEmits {
  save: []
  'move-case': [index: number, delta: -1 | 1]
}

export interface SuiteExecutionDetailDialogEmits {
  'open-report': [record: AppExecution]
  'open-workspace': [executionId?: number, suiteId?: number | null]
  'open-artifact': [record: AppExecution, relativePath: string]
}

export interface SuiteHistoryDialogEmits {
  'open-execution-detail': [id: number]
  'open-workspace': [executionId?: number, suiteId?: number | null]
  'open-report': [record: AppExecution]
}

export interface SuiteRunDialogEmits {
  run: []
}

export interface SuitesTableCardEmits {
  'open-run': [record: AppTestSuite]
  'open-detail': [record: AppTestSuite]
  'open-history': [record: AppTestSuite]
  'duplicate-suite': [record: AppTestSuite]
  'open-edit': [record: AppTestSuite]
  remove: [id: number]
}
