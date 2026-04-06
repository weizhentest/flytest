export type DataFactoryCategoryKey =
  | 'string'
  | 'encoding'
  | 'random'
  | 'encryption'
  | 'test_data'
  | 'json'
  | 'crontab'

export type DataFactoryScenarioKey =
  | 'data_generation'
  | 'format_conversion'
  | 'data_validation'
  | 'encryption_decryption'

export type DataFactoryFieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'select'
  | 'multi-select'
  | 'switch'
  | 'json'
  | 'upload-base64'

export interface DataFactoryFieldOption {
  label: string
  value: string | number | boolean
}

export interface DataFactoryToolField {
  name: string
  label: string
  type: DataFactoryFieldType
  required: boolean
  default: any
  placeholder?: string
  options?: DataFactoryFieldOption[]
  rows?: number
  min?: number
  max?: number
  help_text?: string
}

export interface DataFactoryTool {
  name: string
  display_name: string
  description: string
  category: DataFactoryCategoryKey
  scenario: DataFactoryScenarioKey
  icon: string
  result_kind: 'json' | 'image' | 'json-tree'
  fields: DataFactoryToolField[]
}

export interface DataFactoryCategory {
  category: DataFactoryCategoryKey
  name: string
  description: string
  icon: string
  tools: DataFactoryTool[]
}

export interface DataFactoryScenario {
  scenario: DataFactoryScenarioKey
  name: string
  description: string
  tool_count: number
}

export interface DataFactoryCatalog {
  categories: DataFactoryCategory[]
  scenarios: DataFactoryScenario[]
  tools: DataFactoryTool[]
}

export interface DataFactoryTag {
  id: number
  project: number
  name: string
  code: string
  description: string
  color: string
  creator?: number | null
  creator_name?: string
  record_count?: number
  latest_preview?: string
  created_at: string
  updated_at: string
}

export interface DataFactoryTagOption {
  id: number
  name: string
  code: string
  color: string
  description: string
}

export interface DataFactoryRecord {
  id: number
  project: number
  tool_name: string
  tool_display_name: string
  tool_category: DataFactoryCategoryKey
  category_display: string
  tool_scenario: DataFactoryScenarioKey
  scenario_display: string
  input_data: Record<string, any>
  output_data: {
    success: boolean
    tool_name: string
    result: any
    summary: string
    metadata: Record<string, any>
  }
  is_saved: boolean
  tags: DataFactoryTagOption[]
  preview: string
  reference_placeholder_api: string
  reference_placeholder_ui: string
  creator_name?: string
  created_at: string
  updated_at: string
}

export interface DataFactoryExecuteResult {
  tool: DataFactoryTool
  output_data: DataFactoryRecord['output_data']
  saved: boolean
  record?: DataFactoryRecord
}

export interface DataFactoryStatistics {
  total_records: number
  saved_records: number
  category_stats: Array<{ tool_category: string; total: number }>
  scenario_stats: Array<{ tool_scenario: string; total: number }>
  tag_stats: Array<{ id: number; name: string; code: string; color: string; total: number }>
  recent_records: DataFactoryRecord[]
}

export interface DataFactoryReferenceTag {
  id: number
  name: string
  code: string
  color: string
  description: string
  preview: string
  value: any
  placeholder: string
}

export interface DataFactoryReferenceRecord {
  id: number
  tool_name: string
  tool_category: string
  created_at: string
  preview: string
  value: any
  tag_codes: string[]
  placeholder: string
}

export interface DataFactoryReferencePayload {
  mode: 'api' | 'ui'
  tree: Record<string, any>
  tags: DataFactoryReferenceTag[]
  records: DataFactoryReferenceRecord[]
}

export type DataFactoryReferenceMode = 'api' | 'ui'

export interface DataFactoryPagination<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export const DATA_FACTORY_SCENARIO_LABELS: Record<DataFactoryScenarioKey, string> = {
  data_generation: '数据生成',
  format_conversion: '格式转换',
  data_validation: '数据验证',
  encryption_decryption: '加密解密',
}

export function buildDataFactoryPlaceholder(
  keyType: 'tag' | 'record',
  value: string | number,
  mode: DataFactoryReferenceMode = 'api'
) {
  const expression = `df.${keyType}.${value}`
  return mode === 'ui' ? `\${{${expression}}}` : `{{${expression}}}`
}

export function extractDataFactoryData<T>(response: any): T {
  return response?.data?.data ?? response?.data
}
