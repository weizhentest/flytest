// 测试用例服务
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';
import { request } from '@/utils/request';

// 测试用例步骤接口
export interface TestCaseStep {
  id?: number;
  step_number: number;
  description: string;
  expected_result: string;
}

// 审核状态类型
export type ReviewStatus =
  | 'pending_review'
  | 'approved'
  | 'needs_optimization'
  | 'optimization_pending_review'
  | 'unavailable';

export type ExecutionStatus =
  | 'not_executed'
  | 'passed'
  | 'failed'
  | 'not_applicable';

// 截图接口
export interface TestCaseScreenshot {
  id: number;
  test_case: number;
  screenshot: string; // 截图URL
  screenshot_url: string; // 截图URL（备用）
  title?: string;
  description?: string;
  step_number?: number;
  mcp_session_id?: string;
  page_url?: string;
  created_at: string; // 创建时间
  uploader: number;
  uploader_detail: {
    id: number;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    is_staff: boolean;
    is_active: boolean;
    groups: any[];
  };
  // 兼容字段
  url?: string;
  filename?: string;
  uploaded_at?: string;
}

// 测试用例接口
export interface TestCase {
  id: number;
  project: number;
  module_id?: number;
  module_detail?: string;
  name: string;
  precondition: string;
  level: string; // P0, P1, P2, P3
  test_type?: string; // smoke, functional, boundary, exception, permission, security, compatibility
  related_bug_count?: number;
  execution_status?: ExecutionStatus;
  steps: TestCaseStep[];
  notes?: string; // 备注字段
  screenshot?: string; // 兼容旧的单个截图字段
  screenshots?: TestCaseScreenshot[]; // 新的多截图字段
  review_status?: ReviewStatus; // 审核状态
  creator: number;
  creator_detail: {
    id: number;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    is_staff: boolean;
    is_active: boolean;
    groups: any[];
  };
  assignment_created_at?: string | null;
  executed_at?: string | null;
  created_at: string;
  updated_at: string;
}

// 创建测试用例请求参数
export interface CreateTestCaseRequest {
  name: string;
  precondition: string;
  level: string; // P0, P1, P2, P3
  test_type?: string; // smoke, functional, boundary, exception, permission, security, compatibility
  execution_status?: ExecutionStatus;
  module_id?: number | null; // 所属模块ID
  steps: Omit<TestCaseStep, 'id'>[];
  notes?: string; // 新增备注字段
}

// 更新测试用例请求参数
export interface UpdateTestCaseRequest {
  name?: string;
  precondition?: string;
  level?: string;
  test_type?: string; // smoke, functional, boundary, exception, permission, security, compatibility
  execution_status?: ExecutionStatus;
  module_id?: number | null; // 所属模块ID
  steps?: TestCaseStep[];
  notes?: string; // 新增备注字段
  review_status?: ReviewStatus; // 审核状态
}

// 分页参数接口
export interface PaginationParams {
  page: number;
  pageSize: number;
  search?: string;
  module_id?: number; // 添加可选的模块ID用于筛选
  suite_id?: number; // 添加可选的套件ID用于筛选
  level?: string; // 添加可选的优先级用于筛选
  review_status?: ReviewStatus; // 添加可选的审核状态用于筛选（单个）
  review_status_in?: ReviewStatus[]; // 多个审核状态筛选
  test_type?: string; // 单个测试类型筛选
  test_type_in?: string[]; // 多个测试类型筛选
  assignee_id?: number; // 单个执行人筛选
  assignee_id_in?: number[]; // 多个执行人筛选
}

// 测试用例列表响应接口
export interface TestCaseListResponse {
  success: boolean;
  data?: TestCase[];
  total?: number;
  error?: string;
  statusCode?: number;
}

// 单个测试用例响应接口
export interface TestCaseResponse {
  success: boolean;
  data?: TestCase;
  error?: string;
  statusCode?: number;
  message?: string;
}

// 操作响应接口
export interface OperationResponse {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
}

export interface GenerateTestCasesFromRequirementRequest {
  requirement_document_id?: string;
  requirement_module_id?: string;
  test_case_module_id: number;
  prompt_id?: number;
  generate_mode: 'full' | 'title_only';
  test_types: string[];
  extra_prompt?: string;
  append_to_existing?: boolean;
  auto_infer_requirement?: boolean;
}

export interface GenerateTestCasesFromRequirementResponse {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
  jobId?: string;
  status?: string;
  progressPercent?: number;
  generatedCount?: number;
  gaps?: string[];
  summary?: string;
  data?: TestCase[];
}

export interface TestCaseGenerationResultPayload {
  message?: string;
  generated_count?: number;
  gaps?: string[];
  summary?: string;
  data?: TestCase[];
  review_completed?: boolean;
  coverage_complete?: boolean;
  coverage_score?: number | null;
  review_rounds?: number;
  review_history?: Array<{
    round: number;
    generated_count: number;
    summary?: string;
    coverage_score?: number | null;
    coverage_complete?: boolean;
    missing_coverages?: string[];
    duplicate_case_names?: string[];
  }>;
  missing_coverage_points?: string[];
  duplicate_case_names?: string[];
  skipped_duplicate_names?: string[];
  skipped_duplicate_count?: number;
  next_generation_guidance?: string;
}

export interface TestCaseGenerationJobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  progress_percent: number;
  progress_stage: string;
  progress_message: string;
  error_message: string;
  generated_count: number;
  summary: string;
  gaps: string[];
  result_payload?: TestCaseGenerationResultPayload | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface TestCaseGenerationJobStatusResponse {
  success: boolean;
  data?: TestCaseGenerationJobStatus;
  error?: string;
  statusCode?: number;
}

const normalizeGenerationResultPayload = (payload: any): TestCaseGenerationResultPayload | null => {
  if (!payload) {
    return null;
  }

  const normalizedData = Array.isArray(payload?.data) ? payload.data : [];
  const normalizedGeneratedCount =
    payload?.generated_count ??
    payload?.generatedCount ??
    normalizedData.length ??
    0;

  return {
    message: payload?.message,
    generated_count: normalizedGeneratedCount,
    gaps: payload?.gaps || [],
    summary: payload?.summary || '',
    data: normalizedData,
    review_completed: payload?.review_completed,
    coverage_complete: payload?.coverage_complete,
    coverage_score: payload?.coverage_score ?? null,
    review_rounds: payload?.review_rounds,
    review_history: payload?.review_history || [],
    missing_coverage_points: payload?.missing_coverage_points || [],
    duplicate_case_names: payload?.duplicate_case_names || [],
    skipped_duplicate_names: payload?.skipped_duplicate_names || [],
    skipped_duplicate_count: payload?.skipped_duplicate_count ?? 0,
    next_generation_guidance: payload?.next_generation_guidance || '',
  };
};

// 截图上传请求参数
export interface UploadScreenshotsRequest {
  screenshots?: File[]; // 多个图片文件，最多10张
  screenshot?: File; // 单个图片文件（兼容字段）
  title?: string;
  description?: string;
  step_number?: number;
  mcp_session_id?: string;
  page_url?: string;
}

// 截图上传响应接口
export interface ScreenshotUploadResponse {
  success: boolean;
  data?: TestCaseScreenshot[]; // 返回上传的截图列表
  message?: string;
  error?: string;
  statusCode?: number;
}

/**
 * 获取项目下的测试用例列表
 * @param projectId 项目ID
 * @param params 分页和搜索参数
 * @returns 返回一个Promise，解析为包含测试用例列表的响应对象
 */
export const getTestCaseList = async (projectId: number, params?: PaginationParams): Promise<TestCaseListResponse> => {
  try {
    const response = await request<TestCase[] | { results?: TestCase[]; count?: number; total?: number }>({
      url: `/projects/${projectId}/testcases/`,
      method: 'GET',
      params: params
        ? {
        page: params.page,
        page_size: params.pageSize,
        search: params.search || '',
        module_id: params.module_id,
        suite_id: params.suite_id,
        level: params.level,
        review_status: params.review_status,
        review_status_in: params.review_status_in?.join(','),
        test_type: params.test_type,
        test_type_in: params.test_type_in?.join(','),
        assignee_id: params.assignee_id,
        assignee_id_in: params.assignee_id_in?.join(','),
      }
        : undefined,
    });

    if (!response.success) {
      return {
        success: false,
        error: response.error || '获取测试用例列表失败',
        statusCode: (response as any).status,
      };
    }

    const payload = response.data;
    if (Array.isArray(payload)) {
      return {
        success: true,
        data: payload,
        total: response.total ?? payload.length,
        statusCode: 200,
      };
    }

    if (payload && typeof payload === 'object') {
      const items = Array.isArray(payload.results) ? payload.results : [];
      const total = payload.count ?? payload.total ?? response.total ?? items.length;
      return {
        success: true,
        data: items,
        total,
        statusCode: 200,
      };
    }

    return {
      success: false,
      error: '获取测试用例列表失败：响应数据格式不正确',
      statusCode: 500,
    };
  } catch (error: any) {
    console.error('获取测试用例列表出错:', error);
    return {
      success: false,
      error: error?.error || error.response?.data?.message || error.message || '获取测试用例列表时发生错误',
      statusCode: error?.status || error.response?.status,
    };
  }
};

/**
 * 创建新测试用例
 * @param projectId 项目ID
 * @param testCaseData 测试用例数据
 * @returns 返回一个Promise，解析为创建结果
 */
export const createTestCase = async (projectId: number, testCaseData: CreateTestCaseRequest): Promise<TestCaseResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/projects/${projectId}/testcases/`, testCaseData, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设创建测试用例API返回的格式为 { status: 'success', code: 201, message: '测试用例创建成功', data: {...测试用例对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '创建测试用例失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('创建测试用例出错:', error);
    
    // 处理验证错误，提供更友好的错误信息
    let errorMessage = '创建测试用例时发生错误';
    if (error.response?.data) {
      if (error.response.data.message) {
        errorMessage = error.response.data.message;
      } else if (error.response.data.errors) {
        // 处理字段验证错误
        const fieldErrors = error.response.data.errors;
        const errorMessages = [];
        for (const field in fieldErrors) {
          if (fieldErrors[field] && Array.isArray(fieldErrors[field])) {
            errorMessages.push(`${fieldErrors[field].join(', ')}`);
          }
        }
        if (errorMessages.length > 0) {
          errorMessage = errorMessages.join('; ');
        }
      } else if (error.response.data.error) {
        errorMessage = error.response.data.error;
      }
    } else if (error.message) {
      errorMessage = error.message;
    }
    
    return {
      success: false,
      error: errorMessage,
      statusCode: error.response?.status,
    };
  }
};

export const generateTestCasesFromRequirement = async (
  projectId: number,
  payload: GenerateTestCasesFromRequirementRequest
): Promise<GenerateTestCasesFromRequirementResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/generate-from-requirement/`,
      payload,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    const rawPayload = response.data?.data ?? response.data ?? {};
    const resultPayload = normalizeGenerationResultPayload(
      rawPayload?.result_payload ?? rawPayload?.data ?? rawPayload
    );

    return {
      success: true,
      message: response.data?.message || '测试用例生成任务已提交',
      statusCode: response.status,
      jobId: rawPayload?.job_id || rawPayload?.jobId,
      status: rawPayload?.status,
      progressPercent: rawPayload?.progress_percent ?? rawPayload?.progressPercent ?? 0,
      generatedCount: rawPayload?.generated_count ?? rawPayload?.generatedCount ?? 0,
      gaps: resultPayload?.gaps || rawPayload?.gaps || [],
      summary: resultPayload?.summary || rawPayload?.summary || '',
      data: resultPayload?.data || rawPayload?.data || [],
    };
  } catch (error: any) {
    console.error('AI 生成测试用例失败:', error);
    return {
      success: false,
      error:
        error.response?.data?.error ||
        error.response?.data?.message ||
        error.message ||
        'AI 生成测试用例时发生错误',
      statusCode: error.response?.status,
    };
  }
};

export const getTestCaseGenerationJobStatus = async (
  projectId: number,
  jobId: string
): Promise<TestCaseGenerationJobStatusResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(
      `${API_BASE_URL}/projects/${projectId}/testcases/generation-jobs/${jobId}/`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    const rawPayload = response.data?.data ?? response.data ?? {};
    const payload = rawPayload?.data ?? rawPayload;
    const resultPayload = normalizeGenerationResultPayload(
      payload?.result_payload ?? null
    );

    return {
      success: true,
      data: {
        job_id: payload?.job_id || payload?.jobId || jobId,
        status: payload?.status || 'pending',
        progress_percent: payload?.progress_percent ?? payload?.progressPercent ?? 0,
        progress_stage: payload?.progress_stage || payload?.progressStage || '',
        progress_message: payload?.progress_message || payload?.progressMessage || '',
        error_message: payload?.error_message || payload?.errorMessage || '',
        generated_count: payload?.generated_count ?? payload?.generatedCount ?? 0,
        summary: payload?.summary || '',
        gaps: payload?.gaps || [],
        result_payload: resultPayload,
        created_at: payload?.created_at ?? payload?.createdAt ?? null,
        started_at: payload?.started_at ?? payload?.startedAt ?? null,
        completed_at: payload?.completed_at ?? payload?.completedAt ?? null,
      },
      statusCode: response.status,
    };
  } catch (error: any) {
    console.error('获取测试用例生成任务状态失败:', error);
    return {
      success: false,
      error:
        error.response?.data?.error ||
        error.response?.data?.message ||
        error.message ||
        '获取测试用例生成任务状态失败',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 获取测试用例详情
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @returns 返回一个Promise，解析为测试用例详情
 */
export const getTestCaseDetail = async (projectId: number, testCaseId: number): Promise<TestCaseResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/testcases/${testCaseId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的格式为 { status: 'success', code: 200, data: {...测试用例对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取测试用例详情失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('获取测试用例详情出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取测试用例详情时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 更新测试用例
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @param testCaseData 更新的测试用例数据
 * @returns 返回一个Promise，解析为更新结果
 */
export const updateTestCase = async (
  projectId: number,
  testCaseId: number,
  testCaseData: UpdateTestCaseRequest
): Promise<TestCaseResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.patch(
      `${API_BASE_URL}/projects/${projectId}/testcases/${testCaseId}/`,
      testCaseData,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 假设更新测试用例API返回的格式为 { status: 'success', code: 200, message: '测试用例更新成功', data: {...测试用例对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '更新测试用例失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('更新测试用例出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '更新测试用例时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 删除测试用例
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @returns 返回一个Promise，解析为删除结果
 */
export const deleteTestCase = async (projectId: number, testCaseId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.delete(`${API_BASE_URL}/projects/${projectId}/testcases/${testCaseId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设删除测试用例API返回的格式为 { status: 'success', code: 204, message: '测试用例删除成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '测试用例删除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '删除测试用例失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('删除测试用例出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '删除测试用例时发生错误',
      statusCode: error.response?.status,
    };
  }
};

// 批量删除相关类型定义
export interface BatchDeleteRequest {
  ids: number[];
}

export interface BatchDeletedTestCase {
  id: number;
  name: string;
  module: string;
}

export interface BatchDeleteResponse {
  success: boolean;
  message?: string;
  data?: {
    message: string;
    deleted_count: number;
    deleted_testcases: BatchDeletedTestCase[];
    deletion_details: Record<string, number>;
  };
  error?: string;
  statusCode?: number;
}

export interface BatchMoveCopyResponse {
  success: boolean;
  message?: string;
  data?: {
    message: string;
    moved_count?: number;
    copied_count?: number;
    moved_testcases?: Array<{
      id: number;
      name: string;
      from_module?: string | null;
      to_module?: string | null;
    }>;
    target_module_id: number;
    target_module_name: string;
    data?: TestCase[];
    cleared_job_count?: number;
  };
  error?: string;
  statusCode?: number;
}

export interface ClearModuleTestCasesResponse {
  success: boolean;
  message?: string;
  data?: {
    message: string;
    deleted_count: number;
    deleted_testcases: BatchDeletedTestCase[];
    deletion_details: Record<string, number>;
    cleared_job_count?: number;
  };
  error?: string;
  statusCode?: number;
}

export interface BatchUpdateExecutionStatusResponse {
  success: boolean;
  message?: string;
  data?: {
    updated_count: number;
    execution_status: ExecutionStatus;
  };
  error?: string;
  statusCode?: number;
}

/**
 * 批量删除测试用例
 * @param projectId 项目ID
 * @param testCaseIds 要删除的测试用例ID数组
 * @returns 返回一个Promise，解析为批量删除结果
 */
export const batchDeleteTestCases = async (projectId: number, testCaseIds: number[]): Promise<BatchDeleteResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  if (!testCaseIds || testCaseIds.length === 0) {
    return {
      success: false,
      error: '请选择要删除的测试用例',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/batch-delete/`,
      { ids: testCaseIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 根据API文档，返回格式为 { status: 'success', code: 200, message: '批量删除操作成功完成', data: {...} }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '批量删除操作成功完成',
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '批量删除测试用例失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('批量删除测试用例出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '批量删除测试用例时发生错误',
      statusCode: error.response?.status,
    };
  }
};

export const clearModuleTestCases = async (
  projectId: number,
  moduleId: number
): Promise<ClearModuleTestCasesResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/clear-module/`,
      { module_id: moduleId },
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '模块测试用例已清空',
        data: response.data.data,
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '清空模块测试用例失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('清空模块测试用例失败:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '清空模块测试用例时发生错误',
      statusCode: error.response?.status,
    };
  }
};

export const batchMoveTestCases = async (
  projectId: number,
  testCaseIds: number[],
  targetModuleId: number
): Promise<BatchMoveCopyResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/batch-move/`,
      { ids: testCaseIds, target_module_id: targetModuleId },
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '测试用例移动成功',
        data: response.data.data,
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '移动测试用例失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('移动测试用例失败:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '移动测试用例时发生错误',
      statusCode: error.response?.status,
    };
  }
};

export const batchCopyTestCases = async (
  projectId: number,
  testCaseIds: number[],
  targetModuleId: number
): Promise<BatchMoveCopyResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/batch-copy/`,
      { ids: testCaseIds, target_module_id: targetModuleId },
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '测试用例复制成功',
        data: response.data.data,
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '复制测试用例失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('复制测试用例失败:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '复制测试用例时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 导出所有测试用例到Excel
 * @param projectId 项目ID
 * @returns 返回一个Promise，解析为导出结果
 */
export const exportAllTestCasesToExcel = async (projectId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    // 直接请求文件，使用blob响应类型
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/testcases/export-excel/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
      responseType: 'blob', // 关键：设置为blob类型处理二进制文件
    });

    // 检查响应是否是实际的文件数据
    if (response.data instanceof Blob) {
      // 创建下载链接
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;

      // 从响应头获取文件名，如果没有则使用默认名称
      const contentDisposition = response.headers['content-disposition'];
      let filename = `测试用例导出_${new Date().toISOString().split('T')[0]}.xlsx`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      return {
        success: true,
        message: '测试用例导出成功',
        statusCode: response.status,
      };
    } else {
      // 如果不是Blob，可能是错误响应
      return {
        success: false,
        error: '导出失败：服务器返回的不是有效的文件数据',
        statusCode: response.status,
      };
    }
  } catch (error: any) {
    console.error('导出测试用例出错:', error);

    // 解析错误响应
    let errorMessage = '导出测试用例时发生错误';
    if (error.response?.data) {
      // 如果错误响应是Blob，需要转换为文本
      if (error.response.data instanceof Blob) {
        try {
          const text = await error.response.data.text();
          const errorData = JSON.parse(text);
          errorMessage = errorData.message || errorData.errors?.detail || text;
        } catch {
          errorMessage = '导出失败：服务器返回错误';
        }
      } else if (typeof error.response.data === 'string') {
        errorMessage = error.response.data;
      } else if (error.response.data.message) {
        errorMessage = error.response.data.message;
      } else if (error.response.data.errors) {
        errorMessage = error.response.data.errors.detail || JSON.stringify(error.response.data.errors);
      }
    } else if (error.message) {
      errorMessage = error.message;
    }

    return {
      success: false,
      error: errorMessage,
      statusCode: error.response?.status,
    };
  }
};

/**
 * 导出指定测试用例到Excel
 * @param projectId 项目ID
 * @param testCaseIds 测试用例ID数组
 * @returns 返回一个Promise，解析为导出结果
 */
export const exportSelectedTestCasesToExcel = async (
  projectId: number,
  testCaseIds: number[]
): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  if (!testCaseIds || testCaseIds.length === 0) {
    return {
      success: false,
      error: '请选择要导出的测试用例',
    };
  }

  try {
    const idsParam = testCaseIds.join(',');
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/testcases/export-excel/`, {
      params: {
        ids: idsParam,
      },
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
      responseType: 'blob', // 关键：设置为blob类型处理二进制文件
    });

    // 检查响应是否是实际的文件数据
    if (response.data instanceof Blob) {
      // 创建下载链接
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;

      // 从响应头获取文件名，如果没有则使用默认名称
      const contentDisposition = response.headers['content-disposition'];
      let filename = `测试用例导出_选中${testCaseIds.length}条_${new Date().toISOString().split('T')[0]}.xlsx`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      return {
        success: true,
        message: `成功导出${testCaseIds.length}条测试用例`,
        statusCode: response.status,
      };
    } else {
      // 如果不是Blob，可能是错误响应
      return {
        success: false,
        error: '导出失败：服务器返回的不是有效的文件数据',
        statusCode: response.status,
      };
    }
  } catch (error: any) {
    console.error('导出选中测试用例出错:', error);

    // 解析错误响应
    let errorMessage = '导出选中测试用例时发生错误';
    if (error.response?.data) {
      // 如果错误响应是Blob，需要转换为文本
      if (error.response.data instanceof Blob) {
        try {
          const text = await error.response.data.text();
          const errorData = JSON.parse(text);
          errorMessage = errorData.message || errorData.errors?.detail || text;
        } catch {
          errorMessage = '导出失败：服务器返回错误';
        }
      } else if (typeof error.response.data === 'string') {
        errorMessage = error.response.data;
      } else if (error.response.data.message) {
        errorMessage = error.response.data.message;
      } else if (error.response.data.errors) {
        errorMessage = error.response.data.errors.detail || JSON.stringify(error.response.data.errors);
      }
    } else if (error.message) {
      errorMessage = error.message;
    }

    return {
      success: false,
      error: errorMessage,
      statusCode: error.response?.status,
    };
  }
};

/**
 * 上传测试用例截图（多张）
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @param uploadData 上传数据
 * @returns 返回一个Promise，解析为上传结果
 */
export const uploadTestCaseScreenshots = async (
  projectId: number,
  testCaseId: number,
  uploadData: UploadScreenshotsRequest
): Promise<ScreenshotUploadResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const formData = new FormData();

    // 添加多个截图文件
    if (uploadData.screenshots && uploadData.screenshots.length > 0) {
      uploadData.screenshots.forEach((file) => {
        formData.append('screenshots', file);
      });
    }

    // 添加单个截图文件（兼容字段）
    if (uploadData.screenshot) {
      formData.append('screenshot', uploadData.screenshot);
    }

    // 添加可选参数
    if (uploadData.title) {
      formData.append('title', uploadData.title);
    }
    if (uploadData.description) {
      formData.append('description', uploadData.description);
    }
    if (uploadData.step_number !== undefined) {
      formData.append('step_number', uploadData.step_number.toString());
    }
    if (uploadData.mcp_session_id) {
      formData.append('mcp_session_id', uploadData.mcp_session_id);
    }
    if (uploadData.page_url) {
      formData.append('page_url', uploadData.page_url);
    }

    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/${testCaseId}/upload-screenshots/`,
      formData,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    // 假设API返回的格式为 { status: 'success', code: 201, message: '截图上传成功', data: [...截图对象数组] }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        message: response.data.message || '截图上传成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '上传截图失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('上传截图出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '上传截图时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 上传测试用例截图（单张，兼容旧接口）
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @param screenshot 截图文件
 * @returns 返回一个Promise，解析为上传结果
 */
export const uploadTestCaseScreenshot = async (
  projectId: number,
  testCaseId: number,
  screenshot: File
): Promise<ScreenshotUploadResponse> => {
  return uploadTestCaseScreenshots(projectId, testCaseId, {
    screenshots: [screenshot],
  });
};

/**
 * 获取测试用例的所有截图
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @returns 返回一个Promise，解析为截图列表
 */
export const getTestCaseScreenshots = async (
  projectId: number,
  testCaseId: number
): Promise<{ success: boolean; data?: TestCaseScreenshot[]; error?: string; statusCode?: number }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(
      `${API_BASE_URL}/projects/${projectId}/testcases/${testCaseId}/screenshots/`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取截图列表失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('获取截图列表出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取截图列表时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 删除指定截图
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @param screenshotId 截图ID
 * @returns 返回一个Promise，解析为删除结果
 */
export const deleteTestCaseScreenshot = async (
  projectId: number,
  testCaseId: number,
  screenshotId: number
): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.delete(
      `${API_BASE_URL}/projects/${projectId}/testcases/${testCaseId}/screenshots/${screenshotId}/`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '截图删除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '删除截图失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('删除截图出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '删除截图时发生错误',
      statusCode: error.response?.status,
    };
  }
};

// 批量删除截图相关类型定义
export interface BatchDeleteScreenshotsRequest {
  ids: number[];
}

export interface BatchDeletedScreenshot {
  id: number;
  title: string;
  step_number?: number;
}

export interface BatchDeleteScreenshotsResponse {
  success: boolean;
  message?: string;
  data?: {
    message: string;
    deleted_count: number;
    deleted_screenshots: BatchDeletedScreenshot[];
  };
  error?: string;
  statusCode?: number;
}

/**
 * 批量删除测试用例的截图
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @param screenshotIds 要删除的截图ID数组
 * @returns 返回一个Promise，解析为批量删除结果
 */
export const batchDeleteTestCaseScreenshots = async (
  projectId: number,
  testCaseId: number,
  screenshotIds: number[]
): Promise<BatchDeleteScreenshotsResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  if (!screenshotIds || screenshotIds.length === 0) {
    return {
      success: false,
      error: '请选择要删除的截图',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/${testCaseId}/screenshots/batch-delete/`,
      { ids: screenshotIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 根据API文档，返回格式为 { status: 'success', code: 200, message: '批量删除操作成功完成', data: {...} }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '批量删除截图成功',
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '批量删除截图失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('批量删除截图出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '批量删除截图时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 更新测试用例审核状态
 * @param projectId 项目ID
 * @param testCaseId 测试用例ID
 * @param reviewStatus 审核状态
 * @returns 返回一个Promise，解析为更新结果
 */
export const updateTestCaseReviewStatus = async (
  projectId: number,
  testCaseId: number,
  reviewStatus: ReviewStatus
): Promise<TestCaseResponse> => {
  return updateTestCase(projectId, testCaseId, { review_status: reviewStatus });
};


export const updateTestCaseExecutionStatus = async (
  projectId: number,
  testCaseId: number,
  executionStatus: ExecutionStatus
): Promise<TestCaseResponse> => {
  return updateTestCase(projectId, testCaseId, { execution_status: executionStatus });
};

export const batchUpdateTestCaseExecutionStatus = async (
  projectId: number,
  testCaseIds: number[],
  executionStatus: ExecutionStatus
): Promise<BatchUpdateExecutionStatusResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: 'Not logged in or session expired',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/batch-update-execution-status/`,
      { ids: testCaseIds, execution_status: executionStatus },
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    if (response.data && (response.data.success || response.data.status === 'success')) {
      return {
        success: true,
        message: response.data.message || 'Batch update execution status succeeded',
        data: {
          updated_count: response.data.updated_count ?? response.data.data?.updated_count ?? testCaseIds.length,
          execution_status: response.data.execution_status ?? response.data.data?.execution_status ?? executionStatus,
        },
        statusCode: response.status,
      };
    }

    return {
      success: false,
      error: response.data?.error || response.data?.message || 'Batch update execution status failed',
      statusCode: response.status,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || 'Batch update execution status failed',
      statusCode: error.response?.status,
    };
  }
};
