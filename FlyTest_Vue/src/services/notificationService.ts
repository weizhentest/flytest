import { request } from '@/utils/request';

export interface NotificationUser {
  id: number;
  username: string;
  real_name?: string;
  email?: string;
}

export interface NotificationProject {
  id: number;
  name: string;
}

export interface NotificationReply {
  id: number;
  content: string;
  sender_detail?: NotificationUser | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationInboxItem {
  id: number;
  notification_id: number;
  title: string;
  content: string;
  preview: string;
  scope: 'all' | 'project_members' | 'users';
  scope_display: string;
  project_detail?: NotificationProject | null;
  sender_detail?: NotificationUser | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
  replies?: NotificationReply[];
  reply_count?: number;
}

export interface NotificationInboxResponse {
  success: boolean;
  data?: {
    items: NotificationInboxItem[];
    unread_count: number;
  };
  error?: string;
}

export interface NotificationUnreadCountResponse {
  success: boolean;
  data?: {
    unread_count: number;
    total_count: number;
  };
  error?: string;
}

export interface NotificationActionResponse<T = any> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}

export interface CreateNotificationPayload {
  scope: 'all' | 'project_members' | 'users';
  title: string;
  content: string;
  project_id?: number | null;
  user_ids?: number[];
}

export async function fetchNotificationInbox(limit = 20): Promise<NotificationInboxResponse> {
  const response = await request<{ items: NotificationInboxItem[]; unread_count: number }>({
    url: '/notifications/inbox/',
    method: 'GET',
    params: { limit },
  });
  return { success: response.success, data: response.data, error: response.error };
}

export async function fetchNotificationUnreadCount(): Promise<NotificationUnreadCountResponse> {
  const response = await request<{ unread_count: number; total_count: number }>({
    url: '/notifications/inbox/unread-count/',
    method: 'GET',
  });
  return { success: response.success, data: response.data, error: response.error };
}

export async function fetchNotificationDetail(id: number): Promise<NotificationActionResponse<NotificationInboxItem>> {
  const response = await request<NotificationInboxItem>({
    url: `/notifications/inbox/${id}/`,
    method: 'GET',
  });
  return { success: response.success, data: response.data, error: response.error };
}

export async function markNotificationRead(id: number): Promise<NotificationActionResponse> {
  const response = await request<any>({
    url: `/notifications/inbox/${id}/mark-read/`,
    method: 'POST',
  });
  return { success: response.success, message: response.message, data: response.data, error: response.error };
}

export async function createNotification(payload: CreateNotificationPayload): Promise<NotificationActionResponse> {
  const response = await request<any>({
    url: '/notifications/',
    method: 'POST',
    data: payload,
  });
  return { success: response.success, message: response.message, data: response.data, error: response.error };
}

export async function fetchNotificationReplies(id: number): Promise<NotificationActionResponse<{ items: NotificationReply[] }>> {
  const response = await request<{ items: NotificationReply[] }>({
    url: `/notifications/inbox/${id}/replies/`,
    method: 'GET',
  });
  return { success: response.success, data: response.data, error: response.error };
}

export async function createNotificationReply(id: number, content: string): Promise<NotificationActionResponse<NotificationReply>> {
  const response = await request<NotificationReply>({
    url: `/notifications/inbox/${id}/replies/`,
    method: 'POST',
    data: { content },
  });
  return { success: response.success, message: response.message, data: response.data, error: response.error };
}
