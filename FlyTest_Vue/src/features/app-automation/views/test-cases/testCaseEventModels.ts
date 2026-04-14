import type { AppAutomationTab, AppExecution, AppTestCase } from '../../types'

export interface TestCasesHeaderBarEmits {
  search: []
  reset: []
  'quick-create': []
  'open-scene-builder-draft': []
}

export interface TestCasesBatchBarEmits {
  'open-batch-execute': []
  'clear-selection': []
}

export interface TestCasesTableCardEmits {
  'open-execute': [record: AppTestCase]
  'open-scene-builder': [record: AppTestCase]
  'open-edit': [record: AppTestCase]
  'duplicate-case': [record: AppTestCase]
  remove: [id: number]
}

export interface TestCasesRecentExecutionsCardEmits {
  'open-execution-workspace': [executionId: number]
  'open-execution-report': [executionId: number]
}

export interface TestCaseEditorDialogEmits {
  submit: []
}

export interface TestCaseExecuteDialogEmits {
  execute: []
}
