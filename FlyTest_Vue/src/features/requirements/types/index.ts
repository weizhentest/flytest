
export interface ApiResponse<T = any> {
  status: 'success' | 'error';
  code: number;
  message: string;
  data: T | null;
  errors?: Record<string, any> | null;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type DocumentStatus =
  | 'uploaded'
  | 'processing'
  | 'module_split'
  | 'user_reviewing'
  | 'ready_for_review'
  | 'reviewing'
  | 'review_completed'
  | 'failed';

export type DocumentType = 'pdf' | 'doc' | 'docx' | 'txt' | 'md';

export interface RequirementDocument {
  id: string;
  title: string;
  description: string | null;
  document_type: DocumentType;
  file?: string;
  content?: string | null;
  status: DocumentStatus;
  version: string;
  is_latest: boolean;
  parent_document?: string | null;
  uploader: number;
  uploader_name: string;
  project: string;
  project_name: string;
  uploaded_at: string;
  updated_at: string;
  word_count: number;
  page_count: number;
  modules_count: number;
  has_images: boolean;
  image_count: number;
}

export interface CreateDocumentRequest {
  title: string;
  description?: string;
  document_type: DocumentType;
  project: string;
  file?: File;
  content?: string;
}

export interface DocumentModule {
  id: string;
  title: string;
  content: string;
  start_page?: number;
  end_page?: number;
  start_position?: number;
  end_position?: number;
  order: number;
  parent_module?: string | null;
  is_auto_generated?: boolean;
  confidence_score?: number;
  ai_suggested_title?: string;
  created_at?: string;
  updated_at?: string;
  issues_count?: number;
}

export type ModuleOperationType = 'merge' | 'split' | 'rename' | 'reorder' | 'delete' | 'create' | 'update' | 'adjust_boundary';

export interface ModuleOperationRequest {
  operation: ModuleOperationType;
  target_modules: string[];
  merge_title?: string;
  merge_order?: number;
  split_points?: number[];
  split_titles?: string[];
  new_module_data?: Partial<DocumentModule>;
  new_orders?: Record<string, number>;
  new_boundary?: {
    start_position: number;
    end_position: number;
  };
}

export interface BatchModuleOperationRequest {
  operations: ModuleOperationRequest[];
}

export type SplitLevel = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'auto';

export interface SplitModulesRequest {
  split_level: SplitLevel;
  include_context?: boolean;
  chunk_size?: number;
}

export interface SplitModulesResponse {
  split_options: SplitModulesRequest;
  modules: DocumentModule[];
  status: DocumentStatus;
  total_modules: number;
  suggestions: string[];
}

export type ContextSuggestion = 'OK' | 'SPLIT_RECOMMENDED' | 'SPLIT_REQUIRED';

export interface ContextAnalysis {
  model_name: string;
  token_count: number;
  context_limit: number;
  available_tokens: number;
  reserved_tokens: number;
  exceeds_limit: boolean;
  usage_percentage: number;
  remaining_tokens?: number;
  suggestion: ContextSuggestion;
  message: string;
  optimal_chunk_size?: number;
}

export interface DocumentInfo {
  title: string;
  content_length: number;
  word_count: number;
  page_count: number;
}

export interface ContextCheckResponse {
  document_info: DocumentInfo;
  context_analysis: ContextAnalysis;
  recommendations: string[];
}

export interface DocumentStructure {
  h1_titles: string[];
  h2_titles: string[];
  h3_titles: string[];
  h4_titles: string[];
  h5_titles: string[];
  h6_titles: string[];
}

export interface SplitRecommendation {
  level: SplitLevel;
  modules_count: number;
  description: string;
  suitable_for: string;
  recommended?: boolean;
}

export interface DocumentStructureResponse {
  document_info: DocumentInfo;
  structure_analysis: DocumentStructure;
  split_recommendations: SplitRecommendation[];
}

export type AnalysisType = 'comprehensive' | 'quick' | 'custom';

export interface StartReviewRequest {
  analysis_type: AnalysisType;
  parallel_processing?: boolean;
  priority_modules?: string[];
  custom_requirements?: string;
  direct_review?: boolean;
  max_workers?: number;
  prompt_ids?: {
    completeness_analysis?: number;
    consistency_analysis?: number;
    testability_analysis?: number;
    feasibility_analysis?: number;
    clarity_analysis?: number;
    logic_analysis?: number;
  };
}

export interface ReviewProgress {
  task_id: string;
  overall_progress: number;
  status: string;
  current_step: string;
  modules_progress: ModuleProgress[];
}

export interface ModuleProgress {
  module_name: string;
  status: string;
  progress: number;
  issues_found: number;
}

export type Rating =
  | 'excellent'
  | 'good'
  | 'average'
  | 'needs_improvement'
  | 'fair'
  | 'poor';

export type ReviewReportStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export type IssueType = 'specification' | 'clarity' | 'completeness' | 'consistency' | 'feasibility' | 'logic';

export type IssuePriority = 'high' | 'medium' | 'low';

export interface ReviewIssue {
  id: string;
  issue_type: IssueType;
  issue_type_display: string;
  priority: IssuePriority;
  priority_display: string;
  title: string;
  description: string;
  suggestion: string;
  location: string;
  page_number?: number | null;
  section: string;
  module?: string | null;
  module_name?: string;
  is_resolved: boolean;
  resolution_note: string;
  created_at: string;
  updated_at: string;
}

export interface ModuleReviewResult {
  id: string;
  module: string;
  module_name: string;
  module_rating: Rating;
  module_rating_display: string;
  issues_count: number;
  severity_score: number;
  analysis_content?: string;
  strengths?: string;
  weaknesses?: string;
  recommendations?: string;
}

export interface SpecializedReviewIssue {
  id?: string;
  title?: string;
  description?: string;
  priority?: IssuePriority;
  severity?: IssuePriority;
  category?: string;
  suggestion?: string;
  location?: string;
  source?: string;
}

export interface SpecializedAnalysis {
  overall_score: number;
  summary: string;
  issues: SpecializedReviewIssue[];
  strengths: string[];
  recommendations: string[];
}

export interface ReviewScores {
  completeness: number;
  consistency: number;
  testability: number;
  feasibility: number;
  clarity: number;
  logic: number;
}

export interface ReviewReport {
  id: string;
  document: string;
  document_title: string;
  review_date: string;
  reviewer: string;
  status: ReviewReportStatus;
  status_display: string;
  overall_rating: Rating;
  overall_rating_display: string;
  completion_score: number;
  overall_score?: number;
  total_issues: number;
  high_priority_issues: number;
  medium_priority_issues: number;
  low_priority_issues: number;
  summary: string;
  recommendations: string;
  issues: ReviewIssue[];
  module_results: ModuleReviewResult[];
  scores?: ReviewScores;
  specialized_analyses?: Record<string, SpecializedAnalysis>;
  progress?: number;
  current_step?: string;
  completed_steps?: string[];
}

export interface DocumentDetail extends RequirementDocument {
  modules: DocumentModule[];
  review_reports: ReviewReport[];
  latest_review?: ReviewReport;
}

export interface DocumentListParams {
  project: string;
  status?: DocumentStatus;
  document_type?: DocumentType;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface ReportListParams {
  document?: string;
  status?: string;
  overall_rating?: Rating;
  page?: number;
  page_size?: number;
}

export interface IssueListParams {
  report?: string;
  module?: string;
  issue_type?: IssueType;
  priority?: IssuePriority;
  is_resolved?: boolean;
  page?: number;
  page_size?: number;
}

export interface UpdateIssueRequest {
  is_resolved?: boolean;
  resolution_note?: string;
}

export const DocumentStatusDisplay: Record<DocumentStatus, string> = {
  uploaded: '已上传',
  processing: '处理中',
  module_split: '模块拆分中',
  user_reviewing: '用户调整中',
  ready_for_review: '待评审',
  reviewing: '评审中',
  review_completed: '评审完成',
  failed: '处理失败'
};

export const DocumentTypeDisplay: Record<DocumentType, string> = {
  pdf: 'PDF',
  doc: 'Word文档',
  docx: 'Word文档',
  txt: '文本文档',
  md: 'Markdown'
};

export const RatingDisplay: Record<Rating, string> = {
  excellent: '\u4f18\u79c0',
  good: '\u826f\u597d',
  average: '\u4e00\u822c',
  needs_improvement: '\u9700\u6539\u8fdb',
  fair: '\u4e00\u822c',
  poor: '\u8f83\u5dee'
};

export const IssueTypeDisplay: Record<IssueType, string> = {
  specification: '规范性',
  clarity: '清晰度',
  completeness: '完整性',
  consistency: '一致性',
  feasibility: '可行性',
  logic: '逻辑性'
};

export const IssuePriorityDisplay: Record<IssuePriority, string> = {
  high: '高',
  medium: '中',
  low: '低'
};


