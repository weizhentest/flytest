export interface ApiCollection {
  id: number
  project: number
  name: string
  parent: number | null
  order: number
  creator: number | null
  creator_name?: string
  request_count?: number
  children?: ApiCollection[]
  created_at: string
  updated_at: string
}

export interface ApiResponse<T> {
  success: boolean
  data: T
  total?: number
  message: string
}

export interface ApiCollectionForm {
  project: number
  name: string
  parent: number | null
  order?: number
}

export interface ApiRequest {
  id: number
  collection: number
  collection_name?: string
  project_id?: number
  name: string
  description?: string | null
  method: string
  url: string
  headers: Record<string, any>
  params: Record<string, any>
  body_type: 'none' | 'json' | 'form' | 'raw'
  body: any
  assertions: Array<Record<string, any>>
  generated_script?: Record<string, any>
  test_case_count?: number
  timeout_ms: number
  order: number
  created_by: number | null
  creator_name?: string
  created_at: string
  updated_at: string
}

export interface ApiRequestForm {
  collection: number
  name: string
  description?: string | null
  method: string
  url: string
  headers?: Record<string, any>
  params?: Record<string, any>
  body_type: 'none' | 'json' | 'form' | 'raw'
  body?: any
  assertions?: Array<Record<string, any>>
  timeout_ms?: number
  order?: number
}

export interface ApiAutomationSelection {
  type: 'collection' | 'request' | null
  collection: ApiCollection | null
  request: ApiRequest | null
}

export interface ApiEnvironment {
  id: number
  project: number
  name: string
  base_url: string
  common_headers: Record<string, any>
  variables: Record<string, any>
  timeout_ms: number
  is_default: boolean
  creator: number | null
  creator_name?: string
  created_at: string
  updated_at: string
}

export interface ApiEnvironmentForm {
  project: number
  name: string
  base_url: string
  common_headers?: Record<string, any>
  variables?: Record<string, any>
  timeout_ms?: number
  is_default?: boolean
}

export interface ApiExecutionRecord {
  id: number
  project: number
  request: number | null
  test_case?: number | null
  environment: number | null
  run_id?: string
  run_name?: string
  request_name: string
  method: string
  url: string
  status: 'success' | 'failed' | 'error'
  passed: boolean
  status_code: number | null
  response_time: number | null
  request_snapshot: Record<string, any>
  response_snapshot: Record<string, any>
  assertions_results: Array<Record<string, any>>
  error_message?: string | null
  executor: number | null
  project_name?: string
  executor_name?: string
  environment_name?: string
  interface_name?: string | null
  test_case_name?: string | null
  collection_id?: number | null
  collection_name?: string | null
  request_collection_name?: string
  created_at: string
}

export interface ApiExecutionReportSummary {
  total_count: number
  success_count: number
  failed_count: number
  error_count: number
  passed_count: number
  pass_rate: number
  avg_response_time: number | null
  latest_executed_at: string | null
}

export interface ApiExecutionReportMethodItem {
  method: string
  total: number
  passed: number
  failed: number
  error: number
  avg_response_time: number | null
}

export interface ApiExecutionReportCollectionItem {
  request__collection__name: string | null
  total: number
  passed: number
  failed: number
  error: number
}

export interface ApiExecutionReportFailingItem {
  request_id: number | null
  request_name: string
  request__collection__name: string | null
  total: number
  latest_executed_at: string | null
  latest_status_code: number | null
}

export interface ApiExecutionReportTrendItem {
  day: string
  total: number
  passed: number
  failed: number
  error: number
}

export interface ApiExecutionReportCaseGroup {
  test_case_id: number | null
  test_case_name: string
  is_direct_request: boolean
  total_count: number
  passed_count: number
  failed_count: number
  error_count: number
  pass_rate: number
  latest_executed_at: string | null
  latest_status_code: number | null
  latest_error_message?: string | null
  records: ApiExecutionRecord[]
  failed_records: ApiExecutionRecord[]
}

export interface ApiExecutionReportInterfaceGroup {
  request_id: number | null
  interface_name: string
  collection_id?: number | null
  collection_name?: string | null
  method?: string
  url?: string
  total_count: number
  passed_count: number
  failed_count: number
  error_count: number
  pass_rate: number
  latest_executed_at: string | null
  latest_status_code: number | null
  failed_test_case_count: number
  test_cases: ApiExecutionReportCaseGroup[]
  failed_test_cases: ApiExecutionReportCaseGroup[]
}

export interface ApiExecutionReportRunGroup {
  run_id: string
  run_name: string
  run_type: 'request' | 'test_case' | 'mixed'
  total_count: number
  passed_count: number
  failed_count: number
  error_count: number
  pass_rate: number
  latest_executed_at: string | null
  environment_names: string[]
  interface_count: number
  failed_interface_count: number
  test_case_count: number
  failed_test_case_count: number
  interfaces: ApiExecutionReportInterfaceGroup[]
}

export interface ApiExecutionHierarchySummary {
  run_count: number
  interface_count: number
  failed_interface_count: number
  test_case_count: number
  failed_test_case_count: number
}

export interface ApiExecutionReport {
  summary: ApiExecutionReportSummary
  method_breakdown: ApiExecutionReportMethodItem[]
  collection_breakdown: ApiExecutionReportCollectionItem[]
  failing_requests: ApiExecutionReportFailingItem[]
  trend: ApiExecutionReportTrendItem[]
  recent_records: ApiExecutionRecord[]
  run_groups: ApiExecutionReportRunGroup[]
  hierarchy_summary?: ApiExecutionHierarchySummary
}

export interface ApiExecutionBatchResult {
  run_id?: string | null
  run_name?: string | null
  run_type?: 'request' | 'test_case' | 'mixed'
  total_count: number
  success_count: number
  failed_count: number
  error_count: number
  items: ApiExecutionRecord[]
}

export interface ApiGeneratedScript {
  request_id: number
  request_name: string
  collection_name?: string
  script: Record<string, any>
}

export interface ApiTestCase {
  id: number
  project: number
  request: number
  request_name?: string
  request_method?: string
  request_url?: string
  collection_id?: number
  collection_name?: string
  name: string
  description?: string | null
  status: 'draft' | 'ready' | 'disabled'
  tags: string[]
  script: Record<string, any>
  assertions: Array<Record<string, any>>
  creator: number | null
  creator_name?: string
  created_at: string
  updated_at: string
}

export interface ApiTestCaseForm {
  project: number
  request: number
  name: string
  description?: string | null
  status: 'draft' | 'ready' | 'disabled'
  tags?: string[]
  script?: Record<string, any>
  assertions?: Array<Record<string, any>>
}

export interface ApiTestCaseGenerationItem {
  request_id: number
  request_name: string
  request_method: string
  request_url: string
  mode: 'generate' | 'append' | 'regenerate'
  skipped?: boolean
  skipped_reason?: string
  created_count: number
  ai_used: boolean
  note?: string
  prompt_name?: string | null
  prompt_source?: string | null
  model_name?: string | null
  items: ApiTestCase[]
}

export interface ApiTestCaseGenerationResult {
  scope: 'selected' | 'collection' | 'project'
  mode: 'generate' | 'append' | 'regenerate'
  total_requests: number
  processed_requests: number
  skipped_requests: number
  created_testcase_count: number
  ai_used_count: number
  note?: string
  items: ApiTestCaseGenerationItem[]
}

export interface ApiImportResult {
  created_count: number
  generated_script_count: number
  created_testcase_count: number
  source_type: string
  marker_used: boolean
  note: string
  ai_requested?: boolean
  ai_used?: boolean
  ai_note?: string
  ai_prompt_source?: string | null
  ai_prompt_name?: string | null
  ai_model_name?: string | null
  environment_draft?: Partial<ApiEnvironmentForm> | null
  environment_items?: Partial<ApiEnvironmentForm>[]
  environment_auto_saved?: boolean
  environment_auto_saved_count?: number
  environment_id?: number | null
  environment_name?: string | null
  items: ApiRequest[]
  generated_scripts: ApiGeneratedScript[]
  test_cases: ApiTestCase[]
}

export interface ApiImportJob {
  id: number
  project: number
  collection: number
  collection_name?: string
  creator: number | null
  creator_name?: string
  source_name: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'canceled'
  progress_percent: number
  progress_stage?: string
  progress_message?: string
  cancel_requested?: boolean
  generate_test_cases: boolean
  enable_ai_parse: boolean
  result_payload?: ApiImportResult | null
  error_message?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}
