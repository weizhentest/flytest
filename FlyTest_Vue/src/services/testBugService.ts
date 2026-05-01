import axios from 'axios';
import { API_BASE_URL } from '@/config/api';
import { useAuthStore } from '@/store/authStore';

export type TestBugStatus =
  | 'unassigned'
  | 'assigned'
  | 'confirmed'
  | 'fixed'
  | 'pending_retest'
  | 'closed'
  | 'expired';
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
export type TestBugAttachmentSection = 'steps' | 'expected_result' | 'actual_result';
export type TestBugAttachmentType = 'image' | 'video' | 'file';
export type TestBugActivityAction =
  | 'create'
  | 'update'
  | 'assign'
  | 'confirm'
  | 'fix'
  | 'resolve'
  | 'activate'
  | 'close'
  | 'status_change'
  | 'upload_attachment'
  | 'delete_attachment';

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
  testcase_ids?: number[];
  testcase_names?: string[];
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
  assigned_to_ids?: number[];
  assigned_to_names?: string[];
  assigned_to_details?: BugUserDetail[];
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
  attachments?: TestBugAttachment[];
  activity_logs?: TestBugActivity[];
  created_at?: string;
  updated_at?: string;
}

export interface TestBugAttachment {
  id: number;
  bug: number;
  section: TestBugAttachmentSection;
  attachment?: string;
  url: string;
  original_name: string;
  file_type: TestBugAttachmentType;
  content_type?: string;
  file_size?: number;
  uploaded_by?: number | null;
  uploaded_by_name?: string;
  created_at: string;
}

export interface TestBugActivity {
  id: number;
  bug: number;
  action: TestBugActivityAction;
  action_display?: string;
  content?: string;
  metadata?: Record<string, any>;
  operator?: number | null;
  operator_name?: string;
  created_at: string;
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
  updated_ids?: number[];
}

export interface TestBugAttachmentUploadResponse {
  success: boolean;
  data?: TestBugAttachment[];
  error?: string;
}

const SESSION_EXPIRED_MESSAGE = '未登录或会话已过期';

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

const normalizeErrorMessage = (message?: string, fallback?: string) => {
  const raw = String(message || '').trim();
  if (!raw) {
    return fallback || '操作失败，请稍后重试';
  }
  const lower = raw.toLowerCase();
  if (lower.includes('network error')) {
    return '网络异常，请检查服务是否正常启动';
  }
  if (lower.includes('request failed with status code 500')) {
    return '服务器处理失败，请稍后重试';
  }
  if (lower.includes('request failed with status code 404')) {
    return '请求的接口不存在';
  }
  if (lower.includes('request failed with status code 403')) {
    return '没有权限执行当前操作';
  }
  if (lower.includes('request failed with status code 401')) {
    return '登录状态已失效，请重新登录';
  }
  if (lower.includes('timeout')) {
    return '请求超时，请稍后重试';
  }
  return raw;
};
const getErrorMessage = (error: any, fallback: string) =>
  normalizeErrorMessage(
    error.response?.data?.error || error.response?.data?.message || error.message,
    fallback
  );

export const getTestBugList = async (
  projectId: number,
  params?: Record<string, any>
): Promise<TestBugListResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

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
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

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
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

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
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

  try {
    const response = await axios.patch(`${API_BASE_URL}/projects/${projectId}/test-bugs/${bugId}/`, payload, { headers });
    return { success: true, data: unwrapPayload(response.data) };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '更新 BUG 失败') };
  }
};

export const deleteTestBug = async (projectId: number, bugId: number): Promise<OperationResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

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
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

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

const postBatchAction = async (
  projectId: number,
  action: string,
  payload?: Record<string, any>
): Promise<OperationResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/test-bugs/${action}/`,
      payload || {},
      { headers }
    );
    const data = unwrapPayload(response.data);
    return {
      success: true,
      message: data?.message,
      updated_ids: data?.updated_ids,
    };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, `${action} 操作失败`) };
  }
};

export const assignTestBug = async (projectId: number, bugId: number, assignedToIds: number[]) =>
  postAction(projectId, bugId, 'assign', { assigned_to_ids: assignedToIds });

export const confirmTestBug = async (projectId: number, bugId: number) =>
  postAction(projectId, bugId, 'confirm');

export const fixTestBug = async (
  projectId: number,
  bugId: number,
  resolution: TestBugResolution,
  solution?: string
) => postAction(projectId, bugId, 'fix', { resolution, solution });

export const resolveTestBug = async (
  projectId: number,
  bugId: number,
  resolution?: TestBugResolution,
  solution?: string
) => postAction(projectId, bugId, 'resolve', { resolution, solution });

export const activateTestBug = async (projectId: number, bugId: number) =>
  postAction(projectId, bugId, 'activate');

export const closeTestBug = async (
  projectId: number,
  bugId: number,
  resolution?: TestBugResolution,
  solution?: string
) => postAction(projectId, bugId, 'close', { resolution, solution });

export const changeTestBugStatus = async (
  projectId: number,
  bugId: number,
  status: Exclude<TestBugStatus, 'expired'>
) => postAction(projectId, bugId, 'change-status', { status });

export const batchAssignTestBugs = async (
  projectId: number,
  ids: number[],
  assignedToIds: number[]
) => postBatchAction(projectId, 'batch-assign', { ids, assigned_to_ids: assignedToIds });

export const batchChangeTestBugStatus = async (
  projectId: number,
  ids: number[],
  status: Exclude<TestBugStatus, 'expired'>
) => postBatchAction(projectId, 'batch-change-status', { ids, status });

export const batchUpdateTestBugPriority = async (
  projectId: number,
  ids: number[],
  priority: string
) => postBatchAction(projectId, 'batch-update-priority', { ids, priority });

export const batchUpdateTestBugSeverity = async (
  projectId: number,
  ids: number[],
  severity: string
) => postBatchAction(projectId, 'batch-update-severity', { ids, severity });

export const batchUpdateTestBugType = async (
  projectId: number,
  ids: number[],
  bugType: string
) => postBatchAction(projectId, 'batch-update-bug-type', { ids, bug_type: bugType });

export const batchUpdateTestBugResolution = async (
  projectId: number,
  ids: number[],
  resolution: string,
  solution?: string
) =>
  postBatchAction(projectId, 'batch-update-resolution', {
    ids,
    resolution,
    ...(solution ? { solution } : {}),
  });

export const batchDeleteTestBugs = async (
  projectId: number,
  ids: number[]
) => postBatchAction(projectId, 'batch-delete', { ids });

export const uploadTestBugAttachments = async (
  projectId: number,
  bugId: number,
  section: TestBugAttachmentSection,
  files: File[]
): Promise<TestBugAttachmentUploadResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;
  if (!accessToken) return { success: false, error: SESSION_EXPIRED_MESSAGE };

  try {
    const formData = new FormData();
    formData.append('section', section);
    files.forEach((file) => formData.append('files', file));

    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/test-bugs/${bugId}/upload-attachments/`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
          Accept: 'application/json',
        },
      }
    );
    return { success: true, data: unwrapPayload(response.data) };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '上传 BUG 附件失败') };
  }
};

export const deleteTestBugAttachment = async (
  projectId: number,
  bugId: number,
  attachmentId: number
): Promise<OperationResponse> => {
  const headers = getHeaders();
  if (!headers) return { success: false, error: SESSION_EXPIRED_MESSAGE };

  try {
    await axios.delete(
      `${API_BASE_URL}/projects/${projectId}/test-bugs/${bugId}/attachments/${attachmentId}/`,
      { headers }
    );
    return { success: true, message: 'BUG 附件删除成功' };
  } catch (error: any) {
    return { success: false, error: getErrorMessage(error, '删除 BUG 附件失败') };
  }
};

export const TEST_BUG_TYPE_OPTIONS = [
  { label: '代码错误', value: 'codeerror' },
  { label: '设计缺陷', value: 'design' },
  { label: '界面优化', value: 'standard' },
  { label: '性能问题', value: 'performance' },
  { label: '配置相关', value: 'config' },
  { label: '安装部署', value: 'install' },
  { label: '安全相关', value: 'security' },
  { label: '其他', value: 'others' },
];
export const TEST_BUG_STATUS_OPTIONS = [
  { label: '未指派', value: 'unassigned' },
  { label: '未确认', value: 'assigned' },
  { label: '已确认', value: 'confirmed' },
  { label: '已修复', value: 'fixed' },
  { label: '待复测', value: 'pending_retest' },
  { label: '已关闭', value: 'closed' },
  { label: '已过期', value: 'expired' },
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
