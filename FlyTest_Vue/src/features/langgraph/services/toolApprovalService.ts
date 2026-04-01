import { request } from '@/utils/request';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  UserToolApproval,
  AvailableToolsResponse,
  BatchUpdateRequest,
  BatchUpdateResponse,
  ResetRequest,
  ResetResponse,
} from '@/features/langgraph/types/toolApproval';


const API_BASE_URL = '/lg/tool-approvals';

/**
 * 获取可配置审批偏好的工具列表（包含当前用户偏好）
 */
export async function getAvailableTools(
  sessionId?: string
): Promise<ApiResponse<AvailableToolsResponse>> {
  const response = await request<AvailableToolsResponse>({
    url: `${API_BASE_URL}/available_tools/`,
    method: 'GET',
    params: sessionId ? { session_id: sessionId } : undefined,
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: null,
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '获取工具列表失败',
      data: null,
      errors: { detail: response.error },
    };
  }
}

/**
 * 获取用户所有审批偏好
 */
export async function listToolApprovals(): Promise<ApiResponse<UserToolApproval[]>> {
  const response = await request<UserToolApproval[]>({
    url: `${API_BASE_URL}/`,
    method: 'GET',
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: null,
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '获取审批偏好失败',
      data: null,
      errors: { detail: response.error },
    };
  }
}

/**
 * 批量更新工具审批偏好
 */
export async function batchUpdateToolApprovals(
  data: BatchUpdateRequest
): Promise<ApiResponse<BatchUpdateResponse>> {
  const response = await request<BatchUpdateResponse>({
    url: `${API_BASE_URL}/batch_update/`,
    method: 'POST',
    data,
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '更新成功',
      data: response.data!,
      errors: null,
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '更新审批偏好失败',
      data: null,
      errors: { detail: response.error },
    };
  }
}

/**
 * 保存单个工具的审批偏好
 */
export async function saveToolApproval(
  toolName: string,
  policy: 'always_allow' | 'always_reject' | 'ask_every_time',
  scope: 'session' | 'permanent' = 'permanent',
  sessionId?: string
): Promise<ApiResponse<BatchUpdateResponse>> {
  return batchUpdateToolApprovals({
    approvals: [
      {
        tool_name: toolName,
        policy,
        scope,
        session_id: scope === 'session' ? sessionId : null,
      },
    ],
  });
}

/**
 * 重置工具审批偏好
 */
export async function resetToolApprovals(
  data?: ResetRequest
): Promise<ApiResponse<ResetResponse>> {
  const response = await request<ResetResponse>({
    url: `${API_BASE_URL}/reset/`,
    method: 'POST',
    data: data || {},
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.data?.message || '重置成功',
      data: response.data!,
      errors: null,
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '重置审批偏好失败',
      data: null,
      errors: { detail: response.error },
    };
  }
}
