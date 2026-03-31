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
  environment: number | null
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
  executor_name?: string
  environment_name?: string
  created_at: string
}

export interface ApiExecutionBatchResult {
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
  status: 'pending' | 'running' | 'success' | 'failed'
  progress_percent: number
  progress_stage?: string
  progress_message?: string
  generate_test_cases: boolean
  enable_ai_parse: boolean
  result_payload?: ApiImportResult | null
  error_message?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}
