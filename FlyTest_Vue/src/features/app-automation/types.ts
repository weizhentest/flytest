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
  last_run_at: string | null
  created_by: string
  created_at: string
  updated_at: string
  test_case_count: number
  suite_cases: AppSuiteCase[]
}

export interface AppScheduledTask {
  id: number
  project_id: number
  name: string
  description: string
  task_type: string
  trigger_type: string
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
  notification_type: string
  notify_emails: string[]
  status: string
  last_run_time: string | null
  next_run_time: string | null
  total_runs: number
  successful_runs: number
  failed_runs: number
  last_result: Record<string, unknown>
  error_message: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface AppNotificationRecipient {
  email?: string
  name?: string
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
  response_info: Record<string, unknown>
  created_at: string
  sent_at: string | null
  retry_count: number
  is_retried: boolean
}
