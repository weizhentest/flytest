// 测试执行服务
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';
import type { TestSuite } from './testSuiteService';
import type { TestCase } from './testcaseService';

// 测试用例执行结果接口
export interface TestCaseResult {
  id: number;
  execution: number;
  testcase: number;
  testcase_detail?: TestCase;
  status: 'pending' | 'running' | 'pass' | 'fail' | 'skip' | 'error';
  error_message?: string;
  stack_trace?: string;
  started_at?: string;
  completed_at?: string;
  execution_time?: number;
  duration?: number;
  mcp_session_id?: string;
  screenshots: string[];
  execution_log?: string;
  created_at: string;
  updated_at: string;
}

// 脚本执行结果接口
export interface ScriptExecutionResult {
  id: number;
  script: number;
  script_name?: string;
  test_execution?: number;
  status: 'pending' | 'running' | 'pass' | 'fail' | 'error' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  execution_time?: number;
  duration?: number;
  output?: string;
  error_message?: string;
  stack_trace?: string;
  screenshots: string[];
  videos: string[];
  browser_type?: string;
  viewport?: string;
  executor?: number;
  executor_detail?: {
    id: number;
    username: string;
    email: string;
  };
  created_at: string;
}

// 测试执行记录接口
export interface TestExecution {
  id: number;
  suite: number;
  suite_detail?: TestSuite;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  executor: number;
  executor_detail?: {
    id: number;
    username: string;
    email: string;
  };
  started_at?: string;
  completed_at?: string;
  total_count: number;
  passed_count: number;
  failed_count: number;
  skipped_count: number;
  error_count: number;
  celery_task_id?: string;
  duration?: number;
  pass_rate: number;
  results?: TestCaseResult[];
  script_results?: ScriptExecutionResult[];
  created_at: string;
  updated_at: string;
}

// 创建测试执行请求参数
export interface CreateTestExecutionRequest {
  suite_id: number;
  generate_playwright_script?: boolean;
}

// 测试执行列表响应接口
export interface TestExecutionListResponse {
  success: boolean;
  data?: TestExecution[];
  total?: number;
  error?: string;
  statusCode?: number;
}

// 单个测试执行响应接口
export interface TestExecutionResponse {
  success: boolean;
  data?: TestExecution;
  error?: string;
  statusCode?: number;
  message?: string;
}

// 测试执行结果列表响应接口
export interface TestCaseResultListResponse {
  success: boolean;
  data?: TestCaseResult[];
  error?: string;
  statusCode?: number;
}

// 测试报告响应接口
export interface TestReportResponse {
  success: boolean;
  data?: {
    execution_id: number;
    suite: {
      id: number;
      name: string;
      description?: string;
    };
    status: string;
    started_at?: string;
    completed_at?: string;
    duration?: number;
    statistics: {
      total: number;
      passed: number;
      failed: number;
      skipped: number;
      error: number;
      pass_rate: number;
    };
    results: Array<{
      testcase_id: number;
      testcase_name: string;
      status: string;
      error_message?: string;
      execution_time?: number;
      screenshots: string[];
      testcase_detail?: TestCase;
    }>;
    script_results?: Array<{
      script_id: number;
      script_name: string;
      status: string;
      error_message?: string;
      execution_time?: number;
      screenshots: string[];
      videos?: string[];
      output?: string;
    }>;
  };
  error?: string;
  statusCode?: number;
}

// 操作响应接口
export interface OperationResponse {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
}

/**
 * 获取项目下的测试执行列表
 * @param projectId 项目ID
 * @param params 查询参数
 * @returns 返回一个Promise，解析为包含测试执行列表的响应对象
 */
export const getTestExecutionList = async (
  projectId: number,
  params?: {
    search?: string;
    ordering?: string;
  }
): Promise<TestExecutionListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/test-executions/`, {
      params,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    if (response.data && response.data.status === 'success') {
      if (Array.isArray(response.data.data)) {
        return {
          success: true,
          data: response.data.data,
          total: response.data.data.length,
          statusCode: response.data.code,
        };
      } else if (response.data.data && response.data.data.results) {
        return {
          success: true,
          data: response.data.data.results,
          total: response.data.data.count,
          statusCode: response.data.code,
        };
      }
    }

    return {
      success: false,
      error: response.data?.message || '获取测试执行列表失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('获取测试执行列表出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取测试执行列表时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 创建并启动测试执行
 * @param projectId 项目ID
 * @param executionData 测试执行数据
 * @returns 返回一个Promise，解析为创建结果
 */
export const createTestExecution = async (
  projectId: number,
  executionData: CreateTestExecutionRequest
): Promise<TestExecutionResponse> => {
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
      `${API_BASE_URL}/projects/${projectId}/test-executions/`,
      executionData,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        message: response.data.message || '测试执行已启动',
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '创建测试执行失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('创建测试执行出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '创建测试执行时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 获取测试执行详情
 * @param projectId 项目ID
 * @param executionId 测试执行ID
 * @returns 返回一个Promise，解析为测试执行详情
 */
export const getTestExecutionDetail = async (
  projectId: number,
  executionId: number
): Promise<TestExecutionResponse> => {
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
      `${API_BASE_URL}/projects/${projectId}/test-executions/${executionId}/`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
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
    }

    return {
      success: false,
      error: response.data?.message || '获取测试执行详情失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('获取测试执行详情出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取测试执行详情时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 取消测试执行
 * @param projectId 项目ID
 * @param executionId 测试执行ID
 * @returns 返回一个Promise，解析为取消结果
 */
export const cancelTestExecution = async (
  projectId: number,
  executionId: number
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
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/test-executions/${executionId}/cancel/`,
      {},
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '测试执行取消请求已发送',
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '取消测试执行失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('取消测试执行出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '取消测试执行时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 获取测试执行的所有结果
 * @param projectId 项目ID
 * @param executionId 测试执行ID
 * @returns 返回一个Promise，解析为测试用例结果列表
 */
export const getTestExecutionResults = async (
  projectId: number,
  executionId: number
): Promise<TestCaseResultListResponse> => {
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
      `${API_BASE_URL}/projects/${projectId}/test-executions/${executionId}/results/`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
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
    }

    return {
      success: false,
      error: response.data?.message || '获取测试结果失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('获取测试结果出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取测试结果时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 获取测试执行报告
 * @param projectId 项目ID
 * @param executionId 测试执行ID
 * @returns 返回一个Promise，解析为测试报告
 */
export const getTestExecutionReport = async (
  projectId: number,
  executionId: number
): Promise<TestReportResponse> => {
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
      `${API_BASE_URL}/projects/${projectId}/test-executions/${executionId}/report/`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
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
    }

    return {
      success: false,
      error: response.data?.message || '获取测试报告失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('获取测试报告出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取测试报告时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 删除测试执行记录
 * @param projectId 项目ID
 * @param executionId 测试执行ID
 * @returns 返回一个Promise，解析为删除结果
 */
export const deleteTestExecution = async (
  projectId: number,
  executionId: number
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
      `${API_BASE_URL}/projects/${projectId}/test-executions/${executionId}/`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '测试执行记录已删除',
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '删除测试执行记录失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('删除测试执行记录出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '删除测试执行记录时发生错误',
      statusCode: error.response?.status,
    };
  }
};

export interface AiIterationTestReport {
  suite_ids: number[];
  suite_count: number;
  selected_suite_count: number;
  testcase_count: number;
  bug_count: number;
  generated_at: string;
  used_ai: boolean;
  note: string;
  model_name?: string | null;
  summary: string;
  quality_overview: string;
  risk_overview: string;
  findings: Array<{
    title: string;
    detail: string;
    severity: 'high' | 'medium' | 'low';
  }>;
  recommendations: Array<{
    title: string;
    detail: string;
    priority: 'high' | 'medium' | 'low';
  }>;
  evidence: Array<{
    label: string;
    detail: string;
  }>;
  suite_breakdown: Array<{
    id: number;
    name: string;
    level: number;
    parent_id?: number | null;
    path: string;
    testcase_count: number;
    approved_testcase_count: number;
    failed_testcase_count: number;
    not_executed_testcase_count: number;
    bug_count: number;
    pending_retest_bug_count: number;
    open_bug_count: number;
  }>;
  execution_status_distribution: Record<string, number>;
  bug_status_distribution: Record<string, number>;
  review_status_distribution: Record<string, number>;
}

export interface AiIterationTestReportResponse {
  success: boolean;
  data?: AiIterationTestReport;
  error?: string;
  statusCode?: number;
}

export interface TestReportSnapshot {
  id: number;
  project: number;
  title: string;
  is_pinned?: boolean;
  suite_ids: number[];
  report_data: AiIterationTestReport;
  creator?: number | null;
  creator_name?: string;
  created_at: string;
  updated_at: string;
}

export interface TestReportSnapshotListResponse {
  success: boolean;
  data?: TestReportSnapshot[];
  error?: string;
  statusCode?: number;
}

export interface TestReportSnapshotResponse {
  success: boolean;
  data?: TestReportSnapshot;
  error?: string;
  statusCode?: number;
}

export interface UpdateTestReportSnapshotPayload {
  title?: string;
  is_pinned?: boolean;
  suite_ids?: number[];
  report_data?: AiIterationTestReport;
}

export const generateAiIterationTestReport = async (
  projectId: number,
  suiteIds: number[]
): Promise<AiIterationTestReportResponse> => {
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
      `${API_BASE_URL}/projects/${projectId}/test-executions/ai-report/`,
      { suite_ids: suiteIds },
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    return {
      success: true,
      data: response.data?.data || response.data,
      statusCode: response.status,
    };
  } catch (error: any) {
    return {
      success: false,
      error:
        error.response?.data?.error ||
        error.response?.data?.message ||
        error.message ||
        '生成测试报告失败',
      statusCode: error.response?.status,
    };
  }
};

export const getTestReportSnapshots = async (
  projectId: number
): Promise<TestReportSnapshotListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/test-executions/report-snapshots/`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    return {
      success: true,
      data: response.data?.data || [],
      statusCode: response.status,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '获取报告快照失败',
      statusCode: error.response?.status,
    };
  }
};

export const createTestReportSnapshot = async (
  projectId: number,
  payload: {
    title: string;
    is_pinned?: boolean;
    suite_ids: number[];
    report_data: AiIterationTestReport;
  }
): Promise<TestReportSnapshotResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/test-executions/report-snapshots/`,
      payload,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    return {
      success: true,
      data: response.data?.data,
      statusCode: response.status,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '保存报告快照失败',
      statusCode: error.response?.status,
    };
  }
};

export const updateTestReportSnapshot = async (
  projectId: number,
  snapshotId: number,
  payload: UpdateTestReportSnapshotPayload
): Promise<TestReportSnapshotResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.patch(
      `${API_BASE_URL}/projects/${projectId}/test-executions/report-snapshots/${snapshotId}/update/`,
      payload,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    return {
      success: true,
      data: response.data?.data,
      statusCode: response.status,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '更新报告快照失败',
      statusCode: error.response?.status,
    };
  }
};

export const deleteTestReportSnapshot = async (
  projectId: number,
  snapshotId: number
): Promise<{ success: boolean; error?: string; statusCode?: number }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.delete(
      `${API_BASE_URL}/projects/${projectId}/test-executions/report-snapshots/${snapshotId}/`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    return {
      success: true,
      statusCode: response.status,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '删除报告快照失败',
      statusCode: error.response?.status,
    };
  }
};
