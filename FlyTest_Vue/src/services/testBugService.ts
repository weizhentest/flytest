import axios from 'axios';
import { API_BASE_URL } from '@/config/api';
import { useAuthStore } from '@/store/authStore';

export type TestBugStatus = 'active' | 'resolved' | 'closed';
export type TestBugType =
  | 'codeerror'
  | 'config'
  | 'install'
  | 'security'
  | 'performance'
  | 'standard'
  | 'design'
  | 'others';
export type TestBugResolution =
  | ''
  | 'fixed'
  | 'postponed'
  | 'notrepro'
  | 'external'
  | 'duplicate'
  | 'wontfix'
  | 'bydesign';

export interface BugUserDetail {
  id: number;
  username: string;
  email?: string;
  first_name?: string;
  last_name?: string;
}

export interface TestBug {
  id: number;
  project: number;
  suite: number;
  suite_name?: string;
  testcase?: number | null;
  testcase_name?: string;
  title: string;
  steps?: string;
  expected_result?: string;
  actual_result?: string;
  bug_type: TestBugType;
  bug_type_display?: string;
  severity: string;
  priority: string;
  status: TestBugStatus;
  status_display?: string;
  resolution?: TestBugResolution;
  resolution_display?: string;
  keywords?: string;
  deadline?: string | null;
  assigned_to?: number | null;
  assigned_to_name?: string;
  assigned_to_detail?: BugUserDetail | null;
  opened_by?: number | null;
  opened_by_name?: string;
  creator_detail?: BugUserDetail | null;
  opened_at?: string;
  assigned_at?: string | null;
  resolved_by?: number | null;
  resolved_by_name?: string;
  resolved_by_detail?: BugUserDetail | null;
  resolved_at?: string | null;
  closed_by?: number | null;
  closed_by_detail?: BugUserDetail | null;
  closed_at?: string | null;
  activated_by?: number | null;
  activated_by_detail?: BugUserDetail | null;
  activated_at?: string | null;
  activated_count?: number;
  solution?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TestBugListResponse {
  success: boolean;
  data?: TestBug[];
  total?: number;
  error?: string;
}

export interface TestBugResponse {
  success: boolean;
  data?: TestBug;
  error?: string;
}

export interface OperationResponse {
  success: boolean;
  message?: string;
  error?: string;
}

const getHeaders = () => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;
  if (!accessToken) {
    return null;
  }
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
};

const unwrapPayload = (payload: any) => payload?.data ?? payload;

const parseListPayload = (payload: any) => {
  const data = unwrapPayload(payload);

  if (Array.isArray(data)) {
    return { items: data, total: data.length };
  }
  if (data?.results && Array.isArray(data.results)) {
    return { items: data.results, total: data.count ?? data.results.length };
  }
  if (data?.data && Array.isArray(data.data)) {
    return { items: data.data, total: data.total ?? data.data.length };
  }
  return { items: [], total: 0 };
};

const getErrorMessage = (error: any, fallback: string) =>
  error.response?.data?.error || error.response?.data?.message || error.message || fallback;

export const getTestBugList = async (
  projectId: number,
  params?: Record<string, any>
): Promise<TestBugListResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: '未登录或会话已过期' };

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/test-bugs/`, {
      params,
      headers,
    });
    const { items, total } = parseListPayload(response.data);
    return { success: true, data: items, total };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '获取 BUG 列表失败') };
  }
};

export const getTestBugDetail = async (projectId: number, bugId: number): Promise<TestBugResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: '未登录或会话已过期' };

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/test-bugs/${bugId}/`, {
      headers,
    });
    return { success: true, data: unwrapPayload(response.data) };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '获取 BUG 详情失败') };
  }
};

export const createTestBug = async (projectId: number, payload: Partial<TestBug>): Promise<TestBugResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: '未登录或会话已过期' };

  try {
    const response = await axios.post(`${API_BASE_URL}/projects/${projectId}/test-bugs/`, payload, { headers });
    return { success: true, data: unwrapPayload(response.data) };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '创建 BUG 失败') };
  }
};

export const updateTestBug = async (
  projectId: number,
  bugId: number,
  payload: Partial<TestBug>
): Promise<TestBugResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: '未登录或会话已过期' };

  try {
    const response = await axios.patch(`${API_BASE_URL}/projects/${projectId}/test-bugs/${bugId}/`, payload, { headers });
    return { success: true, data: unwrapPayload(response.data) };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '更新 BUG 失败') };
  }
};

export const deleteTestBug = async (projectId: number, bugId: number): Promise<OperationResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: '未登录或会话已过期' };

  try {
    await axios.delete(`${API_BASE_URL}/projects/${projectId}/test-bugs/${bugId}/`, { headers });
    return { success: true, message: 'BUG 删除成功' };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '删除 BUG 失败') };
  }
};

const postAction = async (
  projectId: number,
  bugId: number,
  action: string,
  payload?: Record<string, any>
): Promise<TestBugResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: '未登录或会话已过期' };

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/test-bugs/${bugId}/${action}/`,
      payload || {},
      { headers }
    );
    return { success: true, data: unwrapPayload(response.data) };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, `${action} 操作失败`) };
  }
};

export const assignTestBug = async (projectId: number, bugId: number, assignedTo: number) =>
  postAction(projectId, bugId, 'assign', { assigned_to: assignedTo });

export const resolveTestBug = async (
  projectId: number,
  bugId: number,
  resolution: TestBugResolution,
  solution?: string
) => postAction(projectId, bugId, 'resolve', { resolution, solution });

export const activateTestBug = async (projectId: number, bugId: number) =>
  postAction(projectId, bugId, 'activate');

export const closeTestBug = async (projectId: number, bugId: number, solution?: string) =>
  postAction(projectId, bugId, 'close', { solution });

export const TEST_BUG_TYPE_OPTIONS = [
  { label: '代码错误', value: 'codeerror' },
  { label: '配置相关', value: 'config' },
  { label: '安装部署', value: 'install' },
  { label: '安全相关', value: 'security' },
  { label: '性能问题', value: 'performance' },
  { label: '标准规范', value: 'standard' },
  { label: '设计缺陷', value: 'design' },
  { label: '其他', value: 'others' },
];

export const TEST_BUG_STATUS_OPTIONS = [
  { label: '激活', value: 'active' },
  { label: '已解决', value: 'resolved' },
  { label: '已关闭', value: 'closed' },
];

export const TEST_BUG_RESOLUTION_OPTIONS = [
  { label: '已修复', value: 'fixed' },
  { label: '延期处理', value: 'postponed' },
  { label: '无法重现', value: 'notrepro' },
  { label: '外部原因', value: 'external' },
  { label: '重复 Bug', value: 'duplicate' },
  { label: '不予修复', value: 'wontfix' },
  { label: '设计如此', value: 'bydesign' },
];
