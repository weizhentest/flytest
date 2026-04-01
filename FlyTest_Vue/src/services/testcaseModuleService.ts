import axios from 'axios'; // 使用 axios 替代 apiClient
import { request } from '@/utils/request';
// import type { APIResponse } from './types'; // 暂时在下方定义

// 通用 API 响应类型
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  statusCode?: number;
  total?: number; // 用于分页
}

export interface TestCaseModule {
  id: number;
  name: string;
  project: number; // 项目ID
  parent: number | null; // 父模块ID
  parent_id: number | null; // 父模块ID (另一种表示)
  level: number; // 模块层级
  creator: number; // 创建者ID
  creator_detail?: {
    id: number;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    is_staff: boolean;
    is_active: boolean;
    groups: any[];
  };
  created_at: string;
  updated_at: string;
  // 可能的附加字段
  children_count?: number;
  test_case_count?: number;
  // 前端构建树时可能需要
  children?: TestCaseModule[];
  key?: number | string; // for a-tree
  title?: string; // for a-tree
}

export interface CreateTestCaseModuleRequest {
  name: string;
  parent?: number | null; // 父模块ID，可选, Django后端通常接受null作为无父级
}

export interface UpdateTestCaseModuleRequest {
  name?: string;
  parent?: number | null; // 父模块ID，可选
}

// 辅助函数处理 Axios 错误
const handleError = (error: any, defaultMessage: string): APIResponse<any> => {
  console.error(defaultMessage, error);
  if (axios.isAxiosError(error)) {
    const responseData = error.response?.data;
    // 优先使用 errors 数组中的详细错误信息
    let message = defaultMessage;
    if (responseData?.errors && Array.isArray(responseData.errors) && responseData.errors.length > 0) {
      message = responseData.errors.join('; ');
    } else if (responseData?.detail) {
      message = responseData.detail;
    } else if (responseData?.message) {
      message = responseData.message;
    } else if (typeof responseData === 'string') {
      message = responseData;
    }
    return {
      success: false,
      error: message,
      statusCode: error.response?.status,
    };
  }
  return { success: false, error: error.message || defaultMessage };
};


// 获取模块列表
// API 响应格式
interface ApiResponse<T> {
  status: string;
  code: number;
  message: string;
  data: T;
  errors: any;
}

type ModuleListPayload =
  | TestCaseModule[]
  | {
      results?: TestCaseModule[];
      items?: TestCaseModule[];
      data?: TestCaseModule[];
      count?: number;
      total?: number;
    };

const normalizeModuleListPayload = (
  payload: ModuleListPayload | undefined
): { items: TestCaseModule[]; total?: number } => {
  if (Array.isArray(payload)) {
    return { items: payload, total: payload.length };
  }

  if (payload && typeof payload === 'object') {
    const items = payload.results || payload.items || payload.data || [];
    const total =
      payload.count ??
      payload.total ??
      (Array.isArray(items) ? items.length : 0);

    return {
      items: Array.isArray(items) ? items : [],
      total,
    };
  }

  return { items: [], total: 0 };
};

export const getTestCaseModules = async (
  projectId: string | number | undefined | null,
  params?: { search?: string; page?: number; pageSize?: number } // 添加分页参数
): Promise<APIResponse<TestCaseModule[]>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  try {
    const response = await request<ModuleListPayload>({
      url: `/projects/${projectId}/testcase-modules/`,
      method: 'GET',
      params: {
        search: params?.search,
        page: params?.page,
        page_size: params?.pageSize,
      },
    });

    if (response.success) {
      const normalized = normalizeModuleListPayload(response.data);
      return {
        success: true,
        data: normalized.items,
        total: normalized.total,
        statusCode: 200,
      };
    }

    return {
      success: false,
      error: response.error || '获取模块列表失败',
      statusCode: (response as any).status,
    };
  } catch (error: any) {
    return handleError(error, '获取模块列表失败');
  }
};

// 创建模块
export const createTestCaseModule = async (
  projectId: string | number | undefined | null,
  data: CreateTestCaseModuleRequest
): Promise<APIResponse<TestCaseModule>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  try {
    const response = await request<TestCaseModule>({
      url: `/projects/${projectId}/testcase-modules/`,
      method: 'POST',
      data,
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
        statusCode: 201,
      };
    }

    return {
      success: false,
      error: response.error || '创建模块失败',
      statusCode: (response as any).status,
    };
  } catch (error: any) {
    return handleError(error, '创建模块失败');
  }
};

// 获取模块详情
export const getTestCaseModuleDetail = async (
  projectId: string | number | undefined | null,
  moduleId: number
): Promise<APIResponse<TestCaseModule>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  try {
    const response = await request<TestCaseModule>({
      url: `/projects/${projectId}/testcase-modules/${moduleId}/`,
      method: 'GET',
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
        statusCode: 200,
      };
    }

    return {
      success: false,
      error: response.error || '获取模块详情失败',
      statusCode: (response as any).status,
    };
  } catch (error: any) {
    return handleError(error, '获取模块详情失败');
  }
};

// 更新模块
export const updateTestCaseModule = async (
  projectId: string | number | undefined | null,
  moduleId: number,
  data: UpdateTestCaseModuleRequest
): Promise<APIResponse<TestCaseModule>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  try {
    const response = await request<TestCaseModule>({
      url: `/projects/${projectId}/testcase-modules/${moduleId}/`,
      method: 'PUT',
      data,
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
        statusCode: 200,
      };
    }

    return {
      success: false,
      error: response.error || '更新模块失败',
      statusCode: (response as any).status,
    };
  } catch (error: any) {
    return handleError(error, '更新模块失败');
  }
};

// 删除模块
export const deleteTestCaseModule = async (
  projectId: string | number | undefined | null,
  moduleId: number
): Promise<APIResponse<null>> => { // data 为 null
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  try {
    const response = await request<null>({
      url: `/projects/${projectId}/testcase-modules/${moduleId}/`,
      method: 'DELETE',
    });

    if (response.success) {
      return {
        success: true,
        data: null,
        statusCode: 200,
      };
    }

    return {
      success: false,
      error: response.error || '删除模块失败',
      statusCode: (response as any).status,
    };
  } catch (error: any) {
    return handleError(error, '删除模块失败');
  }
};
