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

export type ApiBodyMode = 'none' | 'json' | 'form' | 'urlencoded' | 'multipart' | 'raw' | 'xml' | 'graphql' | 'binary'

export interface ApiNamedValueSpec {
  id?: number
  name: string
  value: any
  enabled?: boolean
  order?: number
}

export interface ApiEnvironmentVariableSpec extends ApiNamedValueSpec {
  is_secret?: boolean
}

export interface ApiEnvironmentCookieSpec extends ApiNamedValueSpec {
  domain?: string
  path?: string
}

export interface ApiEnvironmentSpecPayload {
  variables: ApiEnvironmentVariableSpec[]
  headers: ApiNamedValueSpec[]
  cookies: ApiEnvironmentCookieSpec[]
}

export interface ApiEnvironmentEditorModel extends ApiEnvironmentSpecPayload {}

export interface ApiFileSpec {
  id?: number
  field_name: string
  source_type: 'path' | 'base64' | 'placeholder'
  file_path: string
  file_name: string
  content_type: string
  base64_content: string
  enabled?: boolean
  order?: number
}

export interface ApiAuthSpec {
  auth_type: '' | 'none' | 'basic' | 'bearer' | 'api_key' | 'cookie' | 'bootstrap_request'
  username: string
  password: string
  token_value: string
  token_variable: string
  header_name: string
  bearer_prefix: string
  api_key_name: string
  api_key_in: '' | 'header' | 'query' | 'cookie'
  api_key_value: string
  cookie_name: string
  bootstrap_request_id: number | null
  bootstrap_request_name: string
  bootstrap_token_path: string
}

export interface ApiTransportSpec {
  verify_ssl: boolean | null
  proxy_url: string
  client_cert: string
  client_key: string
  follow_redirects: boolean | null
  retry_count: number | null
  retry_interval_ms: number | null
}

export type ApiAssertionExpectedValueKind = 'text' | 'number' | 'json'

export interface ApiAssertionSpec {
  id?: number
  enabled?: boolean
  order?: number
  assertion_type:
    | 'status_code'
    | 'status_range'
    | 'body_contains'
    | 'body_not_contains'
    | 'json_path'
    | 'header'
    | 'cookie'
    | 'regex'
    | 'exists'
    | 'not_exists'
    | 'array_length'
    | 'response_time'
    | 'json_schema'
    | 'openapi_contract'
  target?: string
  selector?: string
  operator?: string
  expected_value_kind?: ApiAssertionExpectedValueKind
  expected_text?: string
  expected_number?: number | null
  expected_json?: Record<string, any> | any[]
  expected_json_text?: string
  min_value?: number | null
  max_value?: number | null
  schema_text?: string
}

export interface ApiExtractorSpec {
  id?: number
  enabled?: boolean
  order?: number
  source: 'json_path' | 'header' | 'cookie' | 'regex' | 'status_code' | 'response_time'
  selector?: string
  variable_name: string
  default_value?: string
  required?: boolean
}

export interface ApiRequestSpecPayload {
  id?: number
  replace_fields?: string[]
  method: string
  url: string
  body_mode: ApiBodyMode
  body_json?: Record<string, any> | any[]
  raw_text: string
  xml_text: string
  binary_base64: string
  graphql_query: string
  graphql_operation_name: string
  graphql_variables?: Record<string, any>
  timeout_ms: number
  headers: ApiNamedValueSpec[]
  query: ApiNamedValueSpec[]
  cookies: ApiNamedValueSpec[]
  form_fields: ApiNamedValueSpec[]
  multipart_parts: ApiNamedValueSpec[]
  files: ApiFileSpec[]
  auth: ApiAuthSpec
  transport: ApiTransportSpec
}

export type ApiTestCaseOverrideSpecPayload = ApiRequestSpecPayload

export interface ApiHttpEditorModel {
  method: string
  url: string
  body_mode: ApiBodyMode
  timeout_ms: number
  headers: ApiNamedValueSpec[]
  query: ApiNamedValueSpec[]
  cookies: ApiNamedValueSpec[]
  form_fields: ApiNamedValueSpec[]
  multipart_parts: ApiNamedValueSpec[]
  files: ApiFileSpec[]
  auth: ApiAuthSpec
  transport: ApiTransportSpec
  assertions: ApiAssertionSpec[]
  extractors: ApiExtractorSpec[]
  body_json_text: string
  raw_text: string
  xml_text: string
  binary_base64: string
  graphql_query: string
  graphql_operation_name: string
  graphql_variables_text: string
}

export type ApiTestCaseWorkflowStage = 'prepare' | 'request' | 'teardown'

export interface ApiTestCaseWorkflowStep {
  name: string
  stage: ApiTestCaseWorkflowStage
  enabled?: boolean
  request_id?: number | null
  request_name?: string
  continue_on_failure?: boolean
  request_overrides?: ApiTestCaseOverrideSpecPayload
  assertion_specs?: ApiAssertionSpec[]
  extractor_specs?: ApiExtractorSpec[]
}

export interface ApiTestCaseWorkflowEditorStep {
  key: string
  name: string
  stage: ApiTestCaseWorkflowStage
  enabled: boolean
  request_id: number | null
  request_name: string
  continue_on_failure: boolean
  editor: ApiHttpEditorModel
}

export interface ApiExecutionWorkflowStepResult {
  kind?: 'workflow_step' | 'main_request'
  index?: number
  name?: string
  stage?: ApiTestCaseWorkflowStage | 'request'
  continue_on_failure?: boolean
  request_id?: number | null
  request_name?: string
  status?: 'success' | 'failed' | 'error'
  passed?: boolean | null
  status_code?: number | null
  response_time?: number | null
  error_message?: string
  record_id?: number | null
  record_request_name?: string
  request_snapshot?: Record<string, any>
  response_snapshot?: Record<string, any>
  assertions_results?: Array<Record<string, any>>
}

export interface ApiExecutionWorkflowSummary {
  enabled: boolean
  configured_step_count: number
  executed_step_count: number
  failure_count: number
  has_failure: boolean
  main_request_executed: boolean
  main_record_id?: number | null
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
  request_spec?: ApiRequestSpecPayload
  assertion_specs?: ApiAssertionSpec[]
  extractor_specs?: ApiExtractorSpec[]
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
  request_spec?: ApiRequestSpecPayload
  assertion_specs?: ApiAssertionSpec[]
  extractor_specs?: ApiExtractorSpec[]
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
  environment_specs?: ApiEnvironmentSpecPayload
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
  environment_specs?: ApiEnvironmentSpecPayload
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
  workflow_summary?: ApiExecutionWorkflowSummary | null
  workflow_steps?: ApiExecutionWorkflowStepResult[]
  main_request_blocked?: boolean
  created_at: string
}

export interface ApiExecutionFailureAnalysisCause {
  title: string
  detail: string
  confidence?: number | null
}

export interface ApiExecutionFailureAnalysisAction {
  title: string
  detail: string
  priority: 'high' | 'medium' | 'low'
}

export interface ApiExecutionFailureAnalysisEvidence {
  label: string
  detail: string
}

export interface ApiExecutionFailureAnalysisRelatedRecord {
  id: number
  status: 'success' | 'failed' | 'error' | string
  status_code: number | null
  response_time: number | null
  error_message?: string | null
  created_at: string | null
}

export interface ApiExecutionFailureAnalysis {
  used_ai: boolean
  note: string
  summary: string
  failure_mode: string
  likely_root_causes: ApiExecutionFailureAnalysisCause[]
  recommended_actions: ApiExecutionFailureAnalysisAction[]
  evidence: ApiExecutionFailureAnalysisEvidence[]
  recent_failures: ApiExecutionFailureAnalysisRelatedRecord[]
  prompt_name?: string | null
  prompt_source?: string | null
  model_name?: string | null
  cache_hit?: boolean
  cache_key?: string | null
  duration_ms?: number | null
  lock_wait_ms?: number | null
}

export interface ApiExecutionReportSummaryRisk {
  title: string
  detail: string
}

export interface ApiExecutionReportSummaryAction {
  title: string
  detail: string
  priority: 'high' | 'medium' | 'low'
}

export interface ApiExecutionReportSummaryEvidence {
  label: string
  detail: string
}

export interface ApiExecutionReportAISummary {
  used_ai: boolean
  note: string
  summary: string
  top_risks: ApiExecutionReportSummaryRisk[]
  recommended_actions: ApiExecutionReportSummaryAction[]
  evidence: ApiExecutionReportSummaryEvidence[]
  prompt_name?: string | null
  prompt_source?: string | null
  model_name?: string | null
  cache_hit?: boolean
  cache_key?: string | null
  duration_ms?: number | null
  lock_wait_ms?: number | null
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
  request_override_spec?: ApiTestCaseOverrideSpecPayload
  assertion_specs?: ApiAssertionSpec[]
  extractor_specs?: ApiExtractorSpec[]
  workflow_steps?: ApiTestCaseWorkflowStep[]
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
  request_override_spec?: ApiTestCaseOverrideSpecPayload
  assertion_specs?: ApiAssertionSpec[]
  extractor_specs?: ApiExtractorSpec[]
  workflow_steps?: ApiTestCaseWorkflowStep[]
}

export interface ApiTestCaseGenerationItem {
  request_id: number
  request_name: string
  request_method: string
  request_url: string
  mode: 'generate' | 'append' | 'regenerate'
  skipped?: boolean
  skipped_reason?: string
  preview_only?: boolean
  requires_confirmation?: boolean
  created_count: number
  ai_used: boolean
  ai_cache_hit?: boolean
  ai_cache_key?: string | null
  ai_duration_ms?: number | null
  ai_lock_wait_ms?: number | null
  note?: string
  prompt_name?: string | null
  prompt_source?: string | null
  model_name?: string | null
  case_summaries?: Array<{
    name: string
    status: string
    tags: string[]
    assertion_count: number
    extractor_count: number
    assertion_types: string[]
    extractor_variables: string[]
    override_sections: string[]
    body_mode: string
  }>
  existing_case_summaries?: Array<{
    name: string
    status: string
    tags: string[]
    assertion_count: number
    extractor_count: number
    assertion_types: string[]
    extractor_variables: string[]
    override_sections: string[]
    body_mode: string
  }>
  proposed_case_summaries?: Array<{
    name: string
    status: string
    tags: string[]
    assertion_count: number
    extractor_count: number
    assertion_types: string[]
    extractor_variables: string[]
    override_sections: string[]
    body_mode: string
  }>
  replacement_summary?: {
    existing_count: number
    proposed_count: number
    will_remove_count: number
    will_create_count: number
    removed_case_names: string[]
    added_case_names: string[]
    unchanged_case_names: string[]
  } | null
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
  ai_cache_hit_count?: number
  preview_only?: boolean
  requires_confirmation?: boolean
  preview_request_count?: number
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
  ai_cache_hit?: boolean
  ai_cache_key?: string | null
  ai_duration_ms?: number | null
  ai_lock_wait_ms?: number | null
  environment_draft?: Partial<ApiEnvironmentForm> | null
  environment_items?: Partial<ApiEnvironmentForm>[]
  environment_auto_saved?: boolean
  environment_auto_saved_count?: number
  environment_id?: number | null
  environment_name?: string | null
  environment_suggestions?: ApiEnvironmentSuggestions | null
  items: ApiRequest[]
  generated_scripts: ApiGeneratedScript[]
  test_cases: ApiTestCase[]
}

export interface ApiEnvironmentSuggestionBaseUrl {
  name: string
  base_url: string
  environment_id?: number | null
  selected?: boolean
}

export interface ApiEnvironmentSuggestionVariable {
  name: string
  request_count?: number
  category: 'auth' | 'business'
  is_secret?: boolean
  example_requests?: string[]
  suggested_value?: string
}

export interface ApiEnvironmentAuthSuggestion {
  request_id: number
  request_name: string
  collection_name?: string
  method: string
  url: string
  token_variable: string
  token_path: string
  token_path_candidates: string[]
  confidence: 'high' | 'medium'
  reason: string
}

export interface ApiEnvironmentSuggestionPatchVariable {
  name: string
  value: string
  is_secret?: boolean
  reason?: string
}

export interface ApiEnvironmentSuggestionPatch {
  base_url?: string
  variables: ApiEnvironmentSuggestionPatchVariable[]
}

export interface ApiEnvironmentSuggestions {
  recommended_environment_id?: number | null
  recommended_environment_name?: string | null
  base_url_candidates: ApiEnvironmentSuggestionBaseUrl[]
  variable_suggestions: ApiEnvironmentSuggestionVariable[]
  auth_suggestions: ApiEnvironmentAuthSuggestion[]
  environment_patch: ApiEnvironmentSuggestionPatch
}

export interface ApiImportJob {
  id: number
  project: number
  collection: number
  collection_name?: string
  creator: number | null
  creator_name?: string
  source_name: string
  source_file?: string | null
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

export interface ApiCaseGenerationJob {
  id: number
  project: number
  collection: number | null
  collection_name?: string
  creator: number | null
  creator_name?: string
  scope: 'selected' | 'collection' | 'project'
  mode: 'generate' | 'append' | 'regenerate'
  status: 'pending' | 'running' | 'preview_ready' | 'applying' | 'success' | 'failed' | 'canceled'
  count_per_request: number
  request_ids: number[]
  progress_percent: number
  progress_stage?: string
  progress_message?: string
  cancel_requested?: boolean
  result_payload?: ApiTestCaseGenerationResult | null
  draft_payload?: Record<string, any> | null
  error_message?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}
