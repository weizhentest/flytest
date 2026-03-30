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

export interface ApiImportResult {
  created_count: number
  generated_script_count: number
  created_testcase_count: number
  source_type: string
  marker_used: boolean
  note: string
  items: ApiRequest[]
  generated_scripts: ApiGeneratedScript[]
  test_cases: ApiTestCase[]
}
