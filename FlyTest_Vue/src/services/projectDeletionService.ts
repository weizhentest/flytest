import axios from 'axios';

import { API_BASE_URL } from '@/config/api';
import { useAuthStore } from '@/store/authStore';
import type { Project } from '@/services/projectService';

export interface ProjectDeletionRequest {
  id: number;
  project?: Project | null;
  project_name: string;
  project_display_id: number;
  requested_by_name: string;
  request_note: string;
  status: 'pending' | 'approved' | 'rejected' | 'restored';
  reviewed_by_name: string;
  review_note: string;
  requested_at: string;
  reviewed_at?: string | null;
  deleted_at?: string | null;
  restored_at?: string | null;
  restored_by_name?: string;
  can_restore?: boolean;
}

interface ListResponse {
  success: boolean;
  data?: ProjectDeletionRequest[];
  error?: string;
}

interface BasicResponse {
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

export const getProjectDeletionRequests = async (): Promise<ListResponse> => {
  const headers = getHeaders();
  if (!headers) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/deletion-requests/`, { headers });
    const data = response.data?.data ?? response.data;
    if (Array.isArray(data)) {
      return { success: true, data };
    }
    return { success: false, error: response.data?.message || '获取项目删除记录失败' };
  } catch (error: any) {
    return { success: false, error: error.response?.data?.message || error.message || '获取项目删除记录失败' };
  }
};

const postAction = async (
  requestId: number,
  action: 'approve' | 'reject' | 'restore',
  payload?: Record<string, unknown>
): Promise<BasicResponse> => {
  const headers = getHeaders();
  if (!headers) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/deletion-requests/${requestId}/${action}/`,
      payload || {},
      { headers }
    );
    return {
      success: true,
      message: response.data?.message || '操作成功',
    };
  } catch (error: any) {
    return { success: false, error: error.response?.data?.message || error.message || '操作失败' };
  }
};

export const approveProjectDeletionRequest = async (requestId: number, reviewNote = '') =>
  postAction(requestId, 'approve', { review_note: reviewNote });

export const rejectProjectDeletionRequest = async (requestId: number, reviewNote = '') =>
  postAction(requestId, 'reject', { review_note: reviewNote });

export const restoreProjectDeletionRequest = async (requestId: number) =>
  postAction(requestId, 'restore');
