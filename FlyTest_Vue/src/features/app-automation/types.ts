export type AppAutomationTab =
  | 'overview'
  | 'devices'
  | 'packages'
  | 'elements'
  | 'scene-builder'
  | 'test-cases'
  | 'suites'
  | 'executions'
  | 'scheduled-tasks'
  | 'notifications'
  | 'reports'
  | 'settings'

export interface AppDevice {
  id: number
  device_id: string
  name: string
  status: string
  android_version: string
  connection_type: string
  ip_address: string
  port: number
  locked_by: string
  locked_at: string | null
  description: string
  location: string
  device_specs?: Record<string, unknown>
  created_at?: string
  last_seen_at?: string | null
  updated_at: string
  is_locked: boolean
}

export interface AppDeviceScreenshot {
  filename: string
  content: string
  device_id: string
  timestamp: number
}

export interface AppPackage {
  id: number
  project_id: number
  name: string
  package_name: string
  activity_name: string
  platform: string
  description: string
  created_at?: string
  updated_at: string
}

export interface AppElement {
  id: number
  project_id: number
  name: string
  element_type: string
  selector_type: string
  selector_value: string
  description: string
  tags: string[]
  config: Record<string, unknown>
  image_path: string
  is_active: boolean
  created_at?: string
  updated_at: string
}

export interface AppImageCategory {
  name: string
  count: number
  path: string
}

export interface AppSceneStep {
  id?: string | number
  name: string
  kind?: 'base' | 'custom'
  action?: string
  type?: string
  component_type?: string
  config?: Record<string, unknown>
  steps?: AppSceneStep[]
  then_steps?: AppSceneStep[]
  try_steps?: AppSceneStep[]
  else_steps?: AppSceneStep[]
  catch_steps?: AppSceneStep[]
  finally_steps?: AppSceneStep[]
  _expanded?: boolean
  selector_type?: string
  selector?: string
  [key: string]: unknown
}

export interface AppSceneVariable {
  name: string
  scope?: string
  type?: string
  value?: unknown
  description?: string
}

export interface AppLlmConfigSnapshot {
  config_name?: string
  provider?: string
  name: string
  api_url: string
  api_key?: string
  system_prompt?: string
  supports_vision?: boolean
}

export interface AppScenePlanRequest {
  project_id: number
  prompt: string
  package_id?: number | null
  current_case_name?: string
  current_description?: string
  current_steps?: AppSceneStep[]
  current_variables?: Array<Record<string, unknown>>
  llm_config?: AppLlmConfigSnapshot | null
}

export interface AppScenePlanResponse {
  name: string
  description: string
  package_id: number | null
  variables: Array<Record<string, unknown>>
  steps: AppSceneStep[]
  summary: string
  warnings: string[]
  mode: 'llm' | 'fallback'
  provider: string
  model: string
}

export interface AppStepSuggestionRequest {
  project_id: number
  prompt: string
  package_id?: number | null
  current_case_name?: string
  current_description?: string
  current_step?: AppSceneStep | null
  current_steps?: AppSceneStep[]
  current_variables?: Array<Record<string, unknown>>
  llm_config?: AppLlmConfigSnapshot | null
}

export interface AppStepSuggestionResponse {
  step: AppSceneStep
  variables: Array<Record<string, unknown>>
  summary: string
  warnings: string[]
  mode: 'llm' | 'fallback'
  provider: string
  model: string
}

export interface AppTestCase {
  id: number
  project_id: number
  name: string
  description: string
  package_id: number | null
  package_display_name?: string
  package_name?: string
  ui_flow: {
    steps?: AppSceneStep[]
    [key: string]: unknown
  }
  variables: Array<Record<string, unknown>>
  tags: string[]
  timeout: number
  retry_count: number
  last_result: string
  last_run_at: string | null
  updated_at: string
}

export interface AppExecutionLog {
  timestamp: string
  level: string
  message: string
  artifact?: string
}

export interface AppExecution {
  id: number
  project_id: number
  test_case_id: number
  test_suite_id?: number | null
  device_id: number
  case_name?: string
  device_name?: string
  device_serial?: string
  status: string
  result: string
  progress: number
  trigger_mode: string
  triggered_by: string
  logs: AppExecutionLog[]
  report_summary: string
  report_path: string
  error_message: string
  total_steps: number
  passed_steps: number
  failed_steps: number
  pass_rate: number
  started_at: string | null
  finished_at: string | null
  duration: number
  created_at: string
}

export interface AppAutomationSettings {
  adb_path: string
  default_timeout: number
  workspace_root: string
  auto_discover_on_open: boolean
  notes: string
}

export interface AppAdbDiagnostics {
  configured_path: string
  resolved_path: string
  executable_found: boolean
  version: string
  device_count: number
  devices: AppDevice[]
  error: string
  checked_at: string
}

export interface AppAdbDetectionResult {
  settings: AppAutomationSettings
  diagnostics: AppAdbDiagnostics
}

export interface AppRuntimeDependency {
  name: string
  module_name: string
  installed: boolean
  version: string
}

export interface AppRuntimeCapability {
  key: string
  label: string
  ready: boolean
  dependencies: string[]
  missing: string[]
  message: string
}

export interface AppRuntimeCapabilities {
  checked_at: string
  python_version: string
  install_command: string
  dependencies: AppRuntimeDependency[]
  capabilities: AppRuntimeCapability[]
}

export interface AppSchedulerHealth {
  running: boolean
  running_tasks: number
  poll_interval_seconds: number
}

export interface AppServiceHealth {
  service: string
  status: string
  version: string
  checked_at: string
  scheduler: AppSchedulerHealth
}

export interface AppDashboardStatistics {
  devices: {
    total: number
    online: number
    locked: number
  }
  packages: {
    total: number
  }
  elements: {
    total: number
  }
  test_cases: {
    total: number
  }
  executions: {
    total: number
    running: number
    passed: number
    failed: number
    pass_rate: number
  }
  recent_executions: AppExecution[]
}

export interface AppComponent {
  id: number
  name: string
  type: string
  category: string
  description: string
  schema: Record<string, unknown>
  default_config: Record<string, unknown>
  enabled: boolean
  sort_order: number
  updated_at: string
}

export interface AppCustomComponent {
  id: number
  name: string
  type: string
  description: string
  schema: Record<string, unknown>
  default_config: Record<string, unknown>
  steps: AppSceneStep[]
  enabled: boolean
  sort_order: number
  updated_at: string
}

export interface AppComponentPackage {
  id: number
  name: string
  version: string
  description: string
  author: string
  source: string
  manifest: Record<string, unknown>
  updated_at: string
}

export interface AppComponentPackageImportResult {
  package: AppComponentPackage
  counts: {
    base_created: number
    base_updated: number
    base_skipped: number
    custom_created: number
    custom_updated: number
    custom_skipped: number
  }
}

export interface AppComponentPackageExportPayload {
  filename: string
  content: string
  content_type: string
  export_format: 'json' | 'yaml'
  component_count: number
  custom_component_count: number
}

export interface AppSuiteCase {
  id: number
  test_case_id: number
  order: number
  test_case: {
    id: number
    name: string
    description: string
    package_name: string
    updated_at: string
  }
}

export interface AppTestSuite {
  id: number
  project_id: number
  name: string
  description: string
  execution_status: string
  execution_result: string
  passed_count: number
  failed_count: number
  stopped_count?: number
  last_run_at: string | null
  created_by: string
  created_at: string
  updated_at: string
  test_case_count: number
  suite_cases: AppSuiteCase[]
}

export interface AppTaskLastResult {
  task_id?: number
  task_type?: string
  status?: string
  execution_id?: number
  execution_ids?: number[]
  test_case_count?: number
  triggered_by?: string
  triggered_at?: string
  test_suite_id?: number | null
  test_case_id?: number | null
}

export interface AppScheduledTaskTriggerPayload {
  task_id: number
  execution_id?: number
  execution_ids?: number[]
  test_case_count?: number
}

export type AppScheduledTaskType = 'TEST_SUITE' | 'TEST_CASE'
export type AppScheduledTaskTriggerType = 'CRON' | 'INTERVAL' | 'ONCE'
export type AppScheduledTaskNotificationType = '' | 'email' | 'webhook' | 'both'
export type AppScheduledTaskStatus = 'ACTIVE' | 'PAUSED' | 'FAILED' | 'COMPLETED'

export interface AppScheduledTaskMutationPayload {
  project_id: number
  name: string
  description: string
  task_type: AppScheduledTaskType
  trigger_type: AppScheduledTaskTriggerType
  cron_expression: string
  interval_seconds: number | null
  execute_at: string | null
  device_id: number | null
  package_id: number | null
  test_suite_id: number | null
  test_case_id: number | null
  notify_on_success: boolean
  notify_on_failure: boolean
  notification_type: AppScheduledTaskNotificationType
  notify_emails: string[]
  status?: AppScheduledTaskStatus
  created_by?: string
}

export interface AppScheduledTask {
  id: number
  project_id: number
  name: string
  description: string
  task_type: AppScheduledTaskType
  trigger_type: AppScheduledTaskTriggerType
  cron_expression: string
  interval_seconds: number | null
  execute_at: string | null
  device_id: number | null
  package_id: number | null
  test_suite_id: number | null
  test_case_id: number | null
  device_name?: string
  app_package_name?: string
  test_suite_name?: string
  test_case_name?: string
  notify_on_success: boolean
  notify_on_failure: boolean
  notification_type: AppScheduledTaskNotificationType
  notify_emails: string[]
  status: AppScheduledTaskStatus
  last_run_time: string | null
  next_run_time: string | null
  total_runs: number
  successful_runs: number
  failed_runs: number
  last_result: AppTaskLastResult
  error_message: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface AppScheduledTaskRunResult extends AppScheduledTask {
  trigger_payload?: AppScheduledTaskTriggerPayload
}

export interface AppNotificationRecipient {
  email?: string
  name?: string
}

export interface AppNotificationResponseInfo {
  delivery_status?: string
  detail?: string
  task_id?: number | null
  task_type?: string
  execution_id?: number
  execution_ids?: number[]
  test_case_count?: number
  test_suite_id?: number | null
  test_case_id?: number | null
  triggered_by?: string
  triggered_at?: string
  retry_status?: string
  retry_count?: number
  retried_at?: string
  [key: string]: unknown
}

export interface AppNotificationLog {
  id: number
  task_id: number | null
  task_name: string
  task_type: string
  notification_type: string
  actual_notification_type: string
  sender_name: string
  sender_email: string
  recipient_info: AppNotificationRecipient[]
  webhook_bot_info: Record<string, unknown>
  notification_content: string
  status: string
  error_message: string
  response_info: AppNotificationResponseInfo
  created_at: string
  sent_at: string | null
  retry_count: number
  is_retried: boolean
}
