/**
 * UI 自动化类型定义
 */

/** 基础时间戳字段 */
export interface TimeStampFields {
  created_at: string
  updated_at: string
}

/** 模块 */
export interface UiModule extends TimeStampFields {
  id: number
  project: number
  name: string
  parent: number | null
  level: number
  children?: UiModule[]
  creator: number | null
  creator_name?: string
}

/** 页面 */
export interface UiPage extends TimeStampFields {
  id: number
  project: number
  module: number
  module_name?: string
  name: string
  url?: string
  description?: string
  element_count?: number
  creator: number | null
  creator_name?: string
}

/** 页面详情（含元素） */
export interface UiPageDetail extends UiPage {
  elements: UiElement[]
}

/** 定位类型 */
export type LocatorType = 'css' | 'xpath' | 'text' | 'role' | 'label' | 'placeholder' | 'test_id' | 'id' | 'name'

/** 元素 */
export interface UiElement extends TimeStampFields {
  id: number
  page: number
  name: string
  locator_type: LocatorType
  locator_value: string
  locator_index?: number
  locator_type_2?: LocatorType
  locator_value_2?: string
  locator_index_2?: number
  locator_type_3?: LocatorType
  locator_value_3?: string
  locator_index_3?: number
  wait_time: number
  is_iframe: boolean
  iframe_locator?: string
  description?: string
  creator: number | null
  creator_name?: string
}

/** 执行状态 */
export type ExecutionStatus = 0 | 1 | 2 | 3  // 未执行 | 执行中 | 成功 | 失败

/** 步骤类型 */
export type StepType = 0 | 1 | 2 | 3 | 4  // 元素操作 | 断言 | SQL | 自定义变量 | 条件判断

export const STEP_TYPE_LABELS: Record<StepType, string> = {
  0: '元素操作',
  1: '断言操作',
  2: 'SQL操作',
  3: '自定义变量',
  4: '条件判断',
}

export const STATUS_LABELS: Record<ExecutionStatus, string> = {
  0: '未执行',
  1: '执行中',
  2: '成功',
  3: '失败',
}

/** 页面步骤 */
export interface UiPageSteps extends TimeStampFields {
  id: number
  project: number
  page: number
  page_name?: string
  module: number
  module_name?: string
  name: string
  description?: string
  run_flow?: string
  flow_data: Record<string, unknown>
  status: ExecutionStatus
  result_data?: Record<string, unknown>
  step_count?: number
  creator: number | null
  creator_name?: string
}

/** 页面步骤详情（含步骤列表） */
export interface UiPageStepsDetail extends UiPageSteps {
  step_details: UiPageStepsDetailed[]
}

/** 步骤详情 */
export interface UiPageStepsDetailed {
  id?: number
  page_step: number
  step_type: StepType
  element?: number | null
  element_name?: string
  step_sort: number
  ope_key?: string
  ope_value?: Record<string, unknown>
  sql_execute?: Record<string, unknown>
  custom?: Record<string, unknown>
  condition_value?: Record<string, unknown>
  func?: string
  description?: string
  created_at?: string
  updated_at?: string
}

/** 用例等级 */
export type CaseLevel = 'P0' | 'P1' | 'P2' | 'P3'

/** 测试用例 */
export interface UiTestCase extends TimeStampFields {
  id: number
  project: number
  module: number
  module_name?: string
  name: string
  description?: string
  level: CaseLevel
  status: ExecutionStatus
  front_custom: unknown[]
  front_sql: unknown[]
  posterior_sql: unknown[]
  parametrize: unknown[]
  case_flow?: string
  result_data?: Record<string, unknown>
  error_message?: string
  step_count?: number
  creator: number | null
  creator_name?: string
}

/** 测试用例详情（含步骤列表） */
export interface UiTestCaseDetail extends UiTestCase {
  case_steps: UiCaseStepsDetailed[]
}

/** 用例步骤详情 */
export interface UiCaseStepsDetailed {
  id?: number
  test_case: number
  page_step: number
  page_step_name?: string
  case_sort: number
  case_data?: Record<string, unknown>
  case_cache_data?: Record<string, unknown>
  case_cache_ass?: Record<string, unknown>
  switch_step_open_url: boolean
  error_retry: number
  status: ExecutionStatus
  error_message?: string
  result_data?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

/** 触发类型 */
export type TriggerType = 'manual' | 'scheduled' | 'api'

/** 执行记录 */
export interface UiExecutionRecord {
  id: number
  batch?: number
  test_case: number
  test_case_name?: string
  executor: number | null
  executor_name?: string
  status: ExecutionStatus | 4  // 含取消状态
  trigger_type: TriggerType
  environment?: Record<string, unknown>
  step_results: unknown[]
  screenshots: string[]
  video_path?: string
  trace_path?: string           // Trace 文件路径
  trace_data?: TraceData | null // 解析后的 Trace 数据
  log?: string
  error_message?: string
  start_time?: string
  end_time?: string
  duration?: number
  created_at: string
}

/** AI 执行模式 */
export type UiAIExecutionMode = 'text' | 'vision'

/** AI 执行状态 */
export type UiAIExecutionStatus = 'pending' | 'running' | 'passed' | 'failed' | 'stopped'

/** AI 执行后端 */
export type UiAIExecutionBackend = 'planning' | 'browser_use'

/** AI 报告类型 */
export type UiAIReportType = 'summary' | 'detailed' | 'performance'

export const AI_MODE_LABELS: Record<UiAIExecutionMode, string> = {
  text: '文本模式',
  vision: '视觉模式',
}

export const AI_STATUS_LABELS: Record<UiAIExecutionStatus, string> = {
  pending: '等待中',
  running: '执行中',
  passed: '成功',
  failed: '失败',
  stopped: '已停止',
}

export const AI_BACKEND_LABELS: Record<UiAIExecutionBackend, string> = {
  planning: 'AI 规划',
  browser_use: 'Browser Use',
}

/** AI 用例 */
export interface UiAICase extends TimeStampFields {
  id: number
  project: number
  name: string
  description?: string
  task_description: string
  default_execution_mode: UiAIExecutionMode
  enable_gif: boolean
  creator: number | null
  creator_name?: string
}

/** AI 任务计划 */
export interface UiAITaskPlan {
  id: number
  title: string
  description: string
  expected_result?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'in_progress' | 'skipped' | 'stopped'
  started_at?: string
  completed_at?: string
  result?: string
  error_message?: string
}

/** AI 已完成步骤 */
export interface UiAIExecutionStep {
  step: number
  title: string
  description: string
  expected_result?: string
  status: 'passed' | 'failed' | 'stopped'
  message: string
  execution_mode: UiAIExecutionMode
  execution_backend: UiAIExecutionBackend
  completed_at: string
  duration?: number
  browser_step_count?: number
  screenshots?: string[]
}

/** AI 执行记录 */
export interface UiAIExecutionRecord {
  id: number
  project: number
  ai_case?: number | null
  ai_case_name?: string
  case_name: string
  task_description: string
  execution_mode: UiAIExecutionMode
  execution_backend: UiAIExecutionBackend
  status: UiAIExecutionStatus
  enable_gif: boolean
  start_time: string
  end_time?: string
  duration?: number
  logs?: string
  steps_completed?: UiAIExecutionStep[]
  planned_tasks?: UiAITaskPlan[]
  screenshots_sequence?: string[]
  gif_path?: string
  error_message?: string
  model_config_name?: string
  executed_by: number | null
  executed_by_name?: string
  planned_task_count?: number
  completed_task_count?: number
}

export interface UiAIReportOverview {
  status: string
  status_color: string
  duration: number
  duration_formatted: string
  avg_step_time: number
  total_steps: number
  total_actions: number
  completion_rate: number
}

export interface UiAIReportStatistics {
  total: number
  completed: number
  pending: number
  failed: number
  skipped: number
  in_progress: number
  stopped: number
  completion_rate: number
  success_rate: number
}

export interface UiAIReportTimelineItem {
  id: number
  title: string
  description: string
  status: string
  status_display: string
  expected_result?: string
}

export interface UiAIReportDetailedStep {
  step_number: number
  title: string
  status: string
  action: string
  description: string
  expected_result?: string
  thinking?: string
  element?: string
  message?: string
  completed_at?: string
  duration?: number
  browser_step_count?: number
  screenshots?: string[]
}

export interface UiAIReportError {
  type: 'error' | 'warning'
  message: string
  step_number?: number
}

export interface UiAIReportMetrics {
  total_steps: number
  passed_steps: number
  failed_steps: number
  pass_rate: number
  total_duration: number
  avg_step_duration: number
  max_step_duration: number
  min_step_duration: number
}

export interface UiAIReportActionDistributionItem {
  action: string
  count: number
}

export interface UiAIReportBottleneck {
  step_number: number
  action: string
  duration: number
  slower_than_avg_by: number
}

export interface UiAIExecutionReport {
  id: number
  report_type: UiAIReportType
  case_name: string
  status: UiAIExecutionStatus
  status_display?: string
  execution_mode: UiAIExecutionMode
  execution_mode_display?: string
  execution_backend: UiAIExecutionBackend
  execution_backend_display?: string
  model_config_name?: string
  task_description: string
  planned_task_count: number
  completed_task_count: number
  failed_task_count: number
  step_count: number
  passed_step_count: number
  failed_step_count: number
  steps_completed: UiAIExecutionStep[]
  planned_tasks: UiAITaskPlan[]
  screenshots_sequence: string[]
  gif_path?: string
  logs: string
  error_message?: string
  start_time: string
  end_time?: string
  duration?: number
  overview?: UiAIReportOverview
  statistics?: UiAIReportStatistics
  timeline?: UiAIReportTimelineItem[]
  detailed_steps?: UiAIReportDetailedStep[]
  errors?: UiAIReportError[]
  metrics?: UiAIReportMetrics
  action_distribution?: UiAIReportActionDistributionItem[]
  bottlenecks?: UiAIReportBottleneck[]
  recommendations?: string[]
}

export interface UiAIRuntimeEnvironment {
  id: number
  name: string
  base_url?: string
  browser: BrowserType
  headless: boolean
  is_default: boolean
}

export interface UiAIRuntimeCapabilities {
  execution_backend: UiAIExecutionBackend
  browser_use_available: boolean
  playwright_available: boolean
  browser_executable_found: boolean
  llm_configured: boolean
  text_mode_ready: boolean
  vision_mode_ready: boolean
  supports_vision: boolean
  summary: string
  issues: string[]
  recommendations: string[]
  default_environment?: UiAIRuntimeEnvironment | null
  model_config_name?: string | null
  model_provider?: string | null
  model_name?: string | null
}

/** 批量执行记录状态 */
export type BatchExecutionStatus = 0 | 1 | 2 | 3 | 4  // 待执行 | 执行中 | 全部成功 | 部分失败 | 全部失败

export const BATCH_STATUS_LABELS: Record<BatchExecutionStatus, string> = {
  0: '待执行',
  1: '执行中',
  2: '全部成功',
  3: '部分失败',
  4: '全部失败',
}

/** 批量执行记录 */
export interface UiBatchExecutionRecord {
  id: number
  name: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  status: BatchExecutionStatus
  trigger_type: TriggerType
  executor?: number
  executor_name?: string
  start_time?: string
  end_time?: string
  duration?: number
  created_at: string
  success_rate?: number
  execution_records?: UiExecutionRecord[]
}

/** Trace 操作记录 */
export interface TraceAction {
  action_id: string
  type: string
  selector?: string
  value?: string
  url?: string
  start_time: number
  end_time: number
  duration: number
  page_id: string
  error?: string
}

/** Trace 网络请求 */
export interface TraceNetworkRequest {
  request_id: string
  url: string
  method: string
  resource_type: string
  mime_type?: string
  status: number
  status_text: string
  start_time: number
  end_time: number
  duration: number
  request_headers: Record<string, string>
  response_headers: Record<string, string>
  response_size: number
  request_body?: string
  response_body?: string
}

/** Trace 控制台消息 */
export interface TraceConsoleMessage {
  type: string
  text: string
  timestamp: number
  location?: {
    url?: string
    lineNumber?: number
    columnNumber?: number
  }
}

/** Trace 快照 */
export interface TraceSnapshot {
  snapshot_id: string
  timestamp: number
  screenshot?: string
}

/** Trace 解析数据 */
export interface TraceData {
  title: string
  start_time: number
  end_time: number
  duration: number
  page_url: string
  actions: TraceAction[]
  network_requests: TraceNetworkRequest[]
  console_messages: TraceConsoleMessage[]
  snapshots: TraceSnapshot[]
  summary: {
    total_actions: number
    total_requests: number
    total_console: number
    total_snapshots: number
    duration_ms: number
    network: {
      total: number
      by_type: Record<string, number>
      by_status: Record<string, number>
      total_size: number
    }
    metadata: Record<string, unknown>
  }
}

/** 公共数据类型 */
export type PublicDataType = 0 | 1 | 2 | 3  // 字符串 | 整数 | 列表 | 字典

export const PUBLIC_DATA_TYPE_LABELS: Record<PublicDataType, string> = {
  0: '字符串',
  1: '整数',
  2: '列表',
  3: '字典',
}

/** 公共数据 */
export interface UiPublicData extends TimeStampFields {
  id: number
  project: number
  type: PublicDataType
  key: string
  value: string
  description?: string
  is_enabled: boolean
  creator: number | null
  creator_name?: string
}

/** 浏览器类型 */
export type BrowserType = 'chromium' | 'firefox' | 'webkit'

/** 环境配置 */
export interface UiEnvironmentConfig extends TimeStampFields {
  id: number
  project: number
  name: string
  base_url?: string
  browser: BrowserType
  headless: boolean
  viewport_width: number
  viewport_height: number
  timeout: number
  db_c_status: boolean
  db_rud_status: boolean
  mysql_config?: Record<string, unknown>
  extra_config?: Record<string, unknown>
  is_default: boolean
  creator: number | null
  creator_name?: string
}

/** API 分页响应 */
export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/** 响应拦截器包装格式 */
export interface ApiResponse<T> {
  success: boolean
  data: T
  message: string
}

/**
 * 提取 API 响应中的原始数据
 * 处理响应拦截器的多层嵌套包装:
 * - 一层: res.data = <actual_data>
 * - 两层: res.data = { data: <actual_data> }
 * - 三层: res.data = { data: { data: <actual_data> } }
 */
export function extractResponseData<T>(res: any): T | undefined {
  // 先获取响应拦截器返回的 data
  let data = res.data
  // 如果 data 有 data 属性且不是数组，继续解包
  while (data && typeof data === 'object' && !Array.isArray(data) && 'data' in data) {
    data = data.data
  }
  return data
}

/**
 * 提取 API 响应中的数据列表
 * 处理响应拦截器的嵌套包装和分页/数组格式
 */
export function extractListData<T>(res: any): T[] {
  // 响应拦截器包装: res.data = { success, data, message }
  const wrapped = res.data?.data ?? res.data
  // 分页格式: { count, results } 或直接数组
  return wrapped?.results ?? (Array.isArray(wrapped) ? wrapped : [])
}

/**
 * 提取 API 响应中的分页信息
 */
export function extractPaginationData(res: any): { items: any[]; count: number } {
  const wrapped = res.data?.data ?? res.data
  if (wrapped?.results) {
    return { items: wrapped.results, count: wrapped.count ?? 0 }
  }
  const items = Array.isArray(wrapped) ? wrapped : []
  return { items, count: items.length }
}

/** 表单类型定义 */
export type UiModuleForm = Omit<UiModule, 'id' | 'level' | 'children' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>
export type UiPageForm = Omit<UiPage, 'id' | 'module_name' | 'element_count' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>
export type UiElementForm = Omit<UiElement, 'id' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>
export type UiPageStepsForm = Omit<UiPageSteps, 'id' | 'page_name' | 'module_name' | 'status' | 'result_data' | 'step_count' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>
export type UiTestCaseForm = Omit<UiTestCase, 'id' | 'module_name' | 'status' | 'result_data' | 'error_message' | 'step_count' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>
export type UiAICaseForm = Omit<UiAICase, 'id' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>
export type UiPublicDataForm = Omit<UiPublicData, 'id' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>
export type UiEnvironmentConfigForm = Omit<UiEnvironmentConfig, 'id' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>

export interface UiAIAdhocRunForm {
  project: number
  case_name?: string
  task_description: string
  execution_mode: UiAIExecutionMode
  enable_gif: boolean
}
