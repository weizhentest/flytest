<template>
  <div class="notification-center">
    <a-trigger
      v-model:popup-visible="popupVisible"
      trigger="click"
      position="bl"
      :unmount-on-close="false"
      :popup-translate="[0, 12]"
      @popup-visible-change="handlePopupVisibleChange"
    >
      <button type="button" class="notification-button" aria-label="站内通知" title="站内通知">
        <a-badge :count="unreadCount" :max-count="99">
          <icon-notification class="notification-icon" />
        </a-badge>
      </button>

      <template #content>
        <div class="notification-panel">
          <div class="notification-panel__header">
            <div>
              <div class="notification-panel__title">站内通知</div>
              <div class="notification-panel__meta">未读 {{ unreadCount }} 条</div>
            </div>
            <a-button v-if="isAdmin" type="outline" size="mini" @click="openSendModal">发送通知</a-button>
          </div>

          <div v-if="loading" class="notification-panel__state">正在加载通知...</div>
          <div v-else-if="notifications.length === 0" class="notification-panel__state">暂无站内通知</div>
          <div v-else class="notification-list">
            <button
              v-for="item in notifications"
              :key="item.id"
              type="button"
              class="notification-item"
              :class="{ 'notification-item--unread': !item.is_read }"
              @click="openNotificationDetail(item)"
            >
              <div class="notification-item__body">
                <div class="notification-item__title-row">
                  <span class="notification-item__title">{{ item.title }}</span>
                  <span v-if="!item.is_read" class="notification-item__tag">未读</span>
                </div>
                <div class="notification-item__preview">{{ item.preview || item.content }}</div>
                <div class="notification-item__meta-row">
                  <span>{{ item.sender_detail?.real_name || item.sender_detail?.username || '系统通知' }}</span>
                  <span>{{ formatDateTime(item.created_at) }}</span>
                </div>
              </div>
              <div class="notification-item__side">
                <span v-if="item.reply_count" class="notification-item__reply-count">{{ item.reply_count }} 条回复</span>
                <a-button v-if="!item.is_read" type="text" size="mini" @click.stop="handleMarkRead(item)">已读</a-button>
              </div>
            </button>
          </div>
        </div>
      </template>
    </a-trigger>

    <a-drawer :visible="detailVisible" :width="720" unmount-on-close @cancel="closeDetail">
      <template #title>通知详情</template>
      <div v-if="detailLoading" class="notification-detail__state">正在加载通知内容...</div>
      <div v-else-if="detailItem" class="notification-detail">
        <div class="notification-detail__header">
          <div>
            <div class="notification-detail__title">{{ detailItem.title }}</div>
            <div class="notification-detail__meta">
              <span>{{ detailItem.sender_detail?.real_name || detailItem.sender_detail?.username || '系统通知' }}</span>
              <span>{{ detailItem.scope_display }}</span>
              <span>{{ formatDateTime(detailItem.created_at) }}</span>
            </div>
          </div>
          <a-tag :color="detailItem.is_read ? 'gray' : 'arcoblue'">{{ detailItem.is_read ? '已读' : '未读' }}</a-tag>
        </div>

        <div v-if="detailItem.project_detail" class="notification-detail__project">
          所属项目：{{ detailItem.project_detail.name }}
        </div>

        <div class="notification-detail__content">{{ detailItem.content }}</div>

        <div class="notification-replies">
          <div class="notification-replies__header">
            <span>回复讨论</span>
            <span>{{ detailReplies.length }} 条回复</span>
          </div>
          <div v-if="replyLoading" class="notification-replies__state">正在加载回复...</div>
          <div v-else-if="detailReplies.length === 0" class="notification-replies__state">还没有人回复，发一条吧。</div>
          <div v-else class="notification-replies__list">
            <div v-for="reply in detailReplies" :key="reply.id" class="notification-reply">
              <div class="notification-reply__meta">
                <span class="notification-reply__author">{{ reply.sender_detail?.real_name || reply.sender_detail?.username || '未知用户' }}</span>
                <span>{{ formatDateTime(reply.created_at) }}</span>
              </div>
              <div class="notification-reply__content">{{ reply.content }}</div>
            </div>
          </div>
        </div>

        <div class="notification-reply-editor">
          <a-textarea
            v-model="replyContent"
            placeholder="回复后，该通知的所有接收人都可以看到"
            :max-length="2000"
            show-word-limit
            :auto-size="{ minRows: 4, maxRows: 8 }"
          />
          <div class="notification-detail__actions">
            <a-button v-if="!detailItem.is_read" type="outline" @click="handleMarkRead(detailItem, true)">标记为已读</a-button>
            <a-button type="primary" :loading="replySubmitting" @click="handleSubmitReply">发送回复</a-button>
            <a-button @click="closeDetail">关闭</a-button>
          </div>
        </div>
      </div>
    </a-drawer>

    <a-modal
      v-model:visible="sendModalVisible"
      title="发送站内通知"
      :width="680"
      :mask-closable="false"
      @before-ok="handleSubmitNotification"
      @close="resetForm"
    >
      <a-form :model="sendForm" layout="vertical">
        <a-form-item field="scope" label="通知范围">
          <a-radio-group v-model="sendForm.scope" @change="handleScopeChange">
            <a-radio value="all">通知所有人</a-radio>
            <a-radio value="project_members">通知项目内成员</a-radio>
            <a-radio value="users">指定用户通知</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item v-if="sendForm.scope === 'project_members'" field="project_id" label="选择项目">
          <a-select v-model="sendForm.project_id" :loading="projectLoading" placeholder="请选择项目" allow-search @change="handleProjectChange">
            <a-option v-for="project in projectOptions" :key="project.id" :value="project.id" :label="project.name" />
          </a-select>
          <div class="notification-form__hint">{{ projectMemberHint }}</div>
        </a-form-item>

        <a-form-item v-if="sendForm.scope === 'users'" field="user_ids" label="选择接收人">
          <a-select
            v-model="sendForm.user_ids"
            :loading="userLoading"
            placeholder="可选择单个或多个用户"
            multiple
            allow-search
            allow-clear
          >
            <a-option v-for="item in userOptions" :key="item.id" :value="item.id" :label="item.label" />
          </a-select>
        </a-form-item>

        <a-form-item field="title" label="通知标题">
          <a-input v-model="sendForm.title" placeholder="请输入通知标题" :max-length="200" show-word-limit />
        </a-form-item>

        <a-form-item field="content" label="通知内容">
          <a-textarea
            v-model="sendForm.content"
            placeholder="请输入通知内容"
            :max-length="5000"
            show-word-limit
            :auto-size="{ minRows: 6, maxRows: 12 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconNotification } from '@arco-design/web-vue/es/icon';

import { getProjectList, getProjectMembers, type ProjectMember } from '@/services/projectService';
import { getUserList } from '@/services/userService';
import {
  createNotification,
  createNotificationReply,
  fetchNotificationDetail,
  fetchNotificationInbox,
  fetchNotificationUnreadCount,
  markNotificationRead,
  type NotificationInboxItem,
  type NotificationReply,
} from '@/services/notificationService';

const props = defineProps<{ isAdmin?: boolean }>();

type ScopeType = 'all' | 'project_members' | 'users';

const popupVisible = ref(false);
const loading = ref(false);
const notifications = ref<NotificationInboxItem[]>([]);
const unreadCount = ref(0);
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailItem = ref<NotificationInboxItem | null>(null);
const detailReplies = ref<NotificationReply[]>([]);
const replyContent = ref('');
const replyLoading = ref(false);
const replySubmitting = ref(false);
const sendModalVisible = ref(false);
const projectLoading = ref(false);
const userLoading = ref(false);
const projectMemberCount = ref(0);
const projectMemberLoading = ref(false);
const refreshTimer = ref<number | null>(null);

const projectOptions = ref<Array<{ id: number; name: string }>>([]);
const userOptions = ref<Array<{ id: number; label: string }>>([]);

const sendForm = reactive<{
  scope: ScopeType;
  project_id: number | null;
  user_ids: number[];
  title: string;
  content: string;
}>({
  scope: 'all',
  project_id: null,
  user_ids: [],
  title: '',
  content: '',
});

const isAdmin = computed(() => Boolean(props.isAdmin));

const projectMemberHint = computed(() => {
  if (!sendForm.project_id) {
    return '选择项目后，将自动通知该项目下的所有成员。';
  }
  if (projectMemberLoading.value) {
    return '正在加载项目成员...';
  }
  return `该项目当前可通知 ${projectMemberCount.value} 位成员。`;
});

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hours = `${date.getHours()}`.padStart(2, '0');
  const minutes = `${date.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function resetForm() {
  sendForm.scope = 'all';
  sendForm.project_id = null;
  sendForm.user_ids = [];
  sendForm.title = '';
  sendForm.content = '';
  projectMemberCount.value = 0;
}

async function loadUnreadCount() {
  const response = await fetchNotificationUnreadCount();
  if (response.success && response.data) {
    unreadCount.value = response.data.unread_count || 0;
  }
}

async function loadNotifications() {
  loading.value = true;
  const response = await fetchNotificationInbox(20);
  loading.value = false;
  if (!response.success || !response.data) {
    Message.error(response.error || '获取通知列表失败');
    return;
  }
  notifications.value = response.data.items || [];
  unreadCount.value = response.data.unread_count || 0;
}

async function handlePopupVisibleChange(visible: boolean) {
  popupVisible.value = visible;
  if (visible) {
    await loadNotifications();
  }
}

async function openNotificationDetail(item: NotificationInboxItem) {
  detailVisible.value = true;
  detailLoading.value = true;
  replyLoading.value = true;
  replyContent.value = '';
  const response = await fetchNotificationDetail(item.id);
  detailLoading.value = false;
  replyLoading.value = false;
  if (!response.success || !response.data) {
    Message.error(response.error || '获取通知详情失败');
    return;
  }
  detailItem.value = response.data;
  detailReplies.value = response.data.replies || [];
}

function closeDetail() {
  detailVisible.value = false;
  detailItem.value = null;
  detailReplies.value = [];
  replyContent.value = '';
}

function syncReadState(targetId: number, readAt?: string | null) {
  notifications.value = notifications.value.map(item =>
    item.id === targetId ? { ...item, is_read: true, read_at: readAt || item.read_at || new Date().toISOString() } : item
  );
  if (detailItem.value && detailItem.value.id === targetId) {
    detailItem.value = {
      ...detailItem.value,
      is_read: true,
      read_at: readAt || detailItem.value.read_at || new Date().toISOString(),
    };
  }
}

async function handleMarkRead(item: NotificationInboxItem, silent = false) {
  const response = await markNotificationRead(item.id);
  if (!response.success) {
    Message.error(response.error || '标记已读失败');
    return;
  }
  syncReadState(item.id, response.data?.read_at);
  unreadCount.value = Math.max(0, Number(response.data?.unread_count ?? unreadCount.value - 1));
  if (!silent) {
    Message.success(response.message || '消息已标记为已读');
  }
}

async function handleSubmitReply() {
  if (!detailItem.value) return;
  const content = replyContent.value.trim();
  if (!content) {
    Message.error('请输入回复内容');
    return;
  }
  replySubmitting.value = true;
  const response = await createNotificationReply(detailItem.value.id, content);
  replySubmitting.value = false;
  if (!response.success || !response.data) {
    Message.error(response.error || '发送回复失败');
    return;
  }
  detailReplies.value = [...detailReplies.value, response.data];
  detailItem.value = {
    ...detailItem.value,
    replies: detailReplies.value,
    reply_count: detailReplies.value.length,
  };
  notifications.value = notifications.value.map(item =>
    item.id === detailItem.value!.id
      ? { ...item, reply_count: detailReplies.value.length }
      : item
  );
  replyContent.value = '';
  Message.success(response.message || '回复发送成功');
}

async function ensureProjectOptionsLoaded() {
  if (projectOptions.value.length > 0) return;
  projectLoading.value = true;
  const response = await getProjectList({ page: 1, pageSize: 1000, search: '' });
  projectLoading.value = false;
  if (!response.success || !response.data) {
    Message.error(response.error || '获取项目列表失败');
    return;
  }
  projectOptions.value = response.data.map(item => ({ id: item.id, name: item.name }));
}

async function ensureUserOptionsLoaded() {
  if (userOptions.value.length > 0) return;
  userLoading.value = true;
  const response = await getUserList({ page: 1, pageSize: 1000, search: '', approvalStatus: 'all' });
  userLoading.value = false;
  if (!response.success || !response.data) {
    Message.error(response.error || '获取用户列表失败');
    return;
  }
  userOptions.value = response.data
    .filter(item => item.is_active)
    .map(item => ({
      id: item.id,
      label: item.real_name?.trim() ? `${item.real_name}（${item.username}）` : item.username,
    }));
}

async function handleProjectChange(value: number | string) {
  const projectId = Number(value);
  if (!projectId) {
    projectMemberCount.value = 0;
    return;
  }
  projectMemberLoading.value = true;
  const response = await getProjectMembers(projectId);
  projectMemberLoading.value = false;
  if (!response.success || !response.data) {
    Message.error(response.error || '获取项目成员失败');
    projectMemberCount.value = 0;
    return;
  }
  projectMemberCount.value = (response.data as ProjectMember[]).length;
}

async function openSendModal() {
  sendModalVisible.value = true;
  await Promise.all([ensureProjectOptionsLoaded(), ensureUserOptionsLoaded()]);
}

function handleScopeChange(scope: ScopeType) {
  sendForm.scope = scope;
  sendForm.project_id = null;
  sendForm.user_ids = [];
  projectMemberCount.value = 0;
}

async function handleSubmitNotification() {
  if (!sendForm.title.trim()) {
    Message.error('请输入通知标题');
    return false;
  }
  if (!sendForm.content.trim()) {
    Message.error('请输入通知内容');
    return false;
  }
  if (sendForm.scope === 'project_members' && !sendForm.project_id) {
    Message.error('请选择项目');
    return false;
  }
  if (sendForm.scope === 'users' && sendForm.user_ids.length === 0) {
    Message.error('请至少选择一个接收人');
    return false;
  }
  const response = await createNotification({
    scope: sendForm.scope,
    title: sendForm.title.trim(),
    content: sendForm.content.trim(),
    project_id: sendForm.scope === 'project_members' ? sendForm.project_id : null,
    user_ids: sendForm.scope === 'users' ? sendForm.user_ids : [],
  });
  if (!response.success) {
    Message.error(response.error || '发送通知失败');
    return false;
  }
  Message.success(response.message || '通知发送成功');
  sendModalVisible.value = false;
  resetForm();
  if (popupVisible.value) {
    await loadNotifications();
  } else {
    await loadUnreadCount();
  }
  return true;
}

function startTimer() {
  stopTimer();
  refreshTimer.value = window.setInterval(() => void loadUnreadCount(), 30000);
}

function stopTimer() {
  if (refreshTimer.value !== null) {
    window.clearInterval(refreshTimer.value);
    refreshTimer.value = null;
  }
}

watch(sendModalVisible, visible => {
  if (!visible) resetForm();
});

onMounted(() => {
  void loadUnreadCount();
  startTimer();
});

onUnmounted(() => {
  stopTimer();
});
</script>

<style scoped>
.notification-center {
  display: inline-flex;
  align-items: center;
}

.notification-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: var(--theme-text-secondary);
  cursor: pointer;
  transition: color 0.2s ease, border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.notification-button:hover {
  color: var(--theme-text);
  border-color: rgba(var(--theme-accent-rgb), 0.36);
  background: rgba(255, 255, 255, 0.96);
  transform: translateY(-1px);
}

.notification-button:focus-visible {
  outline: 2px solid rgba(var(--theme-accent-rgb), 0.45);
  outline-offset: 2px;
}

.notification-icon {
  font-size: 18px;
}

.notification-panel {
  width: 420px;
  max-height: 560px;
  display: flex;
  flex-direction: column;
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(245, 248, 252, 0.94));
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(22px);
}

.notification-panel__header,
.notification-replies__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.notification-panel__header {
  padding: 8px 8px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.notification-panel__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--theme-text);
}

.notification-panel__meta,
.notification-detail__meta,
.notification-form__hint,
.notification-replies__state,
.notification-reply__meta,
.notification-item__meta-row,
.notification-item__reply-count {
  color: var(--theme-text-secondary);
}

.notification-panel__meta,
.notification-form__hint,
.notification-item__meta-row,
.notification-item__reply-count,
.notification-reply__meta {
  font-size: 12px;
}

.notification-panel__state,
.notification-detail__state,
.notification-replies__state {
  padding: 32px 12px;
  text-align: center;
}

.notification-list,
.notification-replies__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.notification-list {
  padding: 12px 4px 4px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 14px 14px 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.notification-item:hover {
  border-color: rgba(var(--theme-accent-rgb), 0.28);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.notification-item--unread {
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.08), rgba(255, 255, 255, 0.92));
}

.notification-item__body,
.notification-item__side {
  display: flex;
  flex-direction: column;
}

.notification-item__body {
  min-width: 0;
  flex: 1;
}

.notification-item__side {
  align-items: flex-end;
  gap: 8px;
}

.notification-item__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notification-item__title,
.notification-detail__title,
.notification-replies__header,
.notification-reply__author {
  color: var(--theme-text);
}

.notification-item__title {
  font-size: 14px;
  font-weight: 700;
}

.notification-item__tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(22, 93, 255, 0.12);
  color: #165dff;
  font-size: 11px;
  font-weight: 700;
}

.notification-item__preview,
.notification-reply__content,
.notification-detail__content {
  word-break: break-word;
  white-space: pre-wrap;
}

.notification-item__preview {
  margin-top: 8px;
  color: var(--theme-text-secondary);
  line-height: 1.6;
}

.notification-item__meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}

.notification-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.notification-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.notification-detail__title {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.4;
}

.notification-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 13px;
}

.notification-detail__project {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: var(--theme-text);
}

.notification-detail__content,
.notification-replies,
.notification-reply-editor {
  padding: 18px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.9);
}

.notification-detail__content {
  min-height: 180px;
  color: var(--theme-text);
  line-height: 1.9;
}

.notification-replies {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.notification-replies__header {
  font-size: 14px;
  font-weight: 700;
}

.notification-reply {
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
}

.notification-reply__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.notification-reply__author {
  font-weight: 700;
}

.notification-reply__content {
  line-height: 1.8;
  color: var(--theme-text);
}

.notification-reply-editor {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.notification-detail__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
