<template>
  <div class="chat-sidebar">
    <div class="sidebar-header">
      <!-- 未选中任何对话时:新对话和全选在同一行,各占一半 -->
      <div v-if="selectedSessions.length === 0" class="header-row">
        <a-button type="primary" style="flex: 1; margin-right: 8px;" @click="$emit('create-new-chat')">
          <template #icon>
            <icon-plus />
          </template>
          新对话
        </a-button>
        <a-button
          v-if="sessions.length > 0"
          style="flex: 1;"
          @click="toggleSelectAll"
        >
          <template #icon>
            <icon-check-circle />
          </template>
          全选
        </a-button>
      </div>
      
      <!-- 选中对话后:新对话在第一行,全选/批量删除在第二行 -->
      <template v-else>
        <div class="header-row">
          <a-button type="primary" block style="width: 100%;" @click="$emit('create-new-chat')">
            <template #icon>
              <icon-plus />
            </template>
            新对话
          </a-button>
        </div>
        <div class="header-row" style="margin-top: 12px;">
          <a-space>
            <a-button
              size="small"
              @click="toggleSelectAll"
            >
              <template #icon>
                <icon-close-circle />
              </template>
              取消全选
            </a-button>
            <a-button
              type="primary"
              status="danger"
              size="small"
              @click="handleBatchDelete"
            >
              <template #icon>
                <icon-delete />
              </template>
              批量删除 ({{ selectedSessions.length }})
            </a-button>
          </a-space>
        </div>
      </template>
    </div>

    <div class="chat-history-list">
      <div v-if="sessions.length === 0" class="empty-history">
        暂无历史对话
      </div>
      <div
        v-for="session in sessions"
        :key="session.id"
        :class="['chat-history-item', session.id === currentSessionId ? 'active' : '']"
      >
        <a-checkbox 
          v-model="selectedSessions"
          :value="session.id"
          class="history-item-checkbox"
          @click.stop
        />
        <div class="history-item-content" @click="$emit('switch-session', session.id)">
          <div class="history-item-info">
            <div class="history-item-title">{{ session.title || '未命名对话' }}</div>
            <div class="history-item-time">{{ formatTime(session.lastTime) }}</div>
          </div>
        </div>
        <div v-if="selectedSessions.length === 0" class="history-item-actions">
          <a-button type="text" size="mini" @click.stop="$emit('delete-session', session.id)">
            <template #icon>
              <icon-delete style="color: #f53f3f;" />
            </template>
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Button as AButton, Checkbox as ACheckbox, Space as ASpace, Modal, Message } from '@arco-design/web-vue';
import { IconPlus, IconDelete, IconCheckCircle, IconCloseCircle } from '@arco-design/web-vue/es/icon';

interface ChatSession {
  id: string;
  title: string;
  lastTime: Date;
  messageCount: number;
}

interface Props {
  sessions: ChatSession[];
  currentSessionId: string;
  isLoading: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'create-new-chat': [];
  'switch-session': [id: string];
  'delete-session': [id: string];
  'batch-delete-sessions': [sessionIds: string[]];
}>();

// 选中的会话列表
const selectedSessions = ref<string[]>([]);

// 计算是否全选
const isAllSelected = computed(() => {
  return props.sessions.length > 0 && selectedSessions.value.length === props.sessions.length;
});

// 全选/取消全选
const toggleSelectAll = () => {
  if (isAllSelected.value || selectedSessions.value.length > 0) {
    // 取消全选
    selectedSessions.value = [];
  } else {
    // 全选
    selectedSessions.value = props.sessions.map(session => session.id);
  }
};

// 批量删除处理
const handleBatchDelete = () => {
  if (selectedSessions.value.length === 0) {
    Message.warning('请先选择要删除的对话');
    return;
  }

  Modal.confirm({
    title: '确认批量删除',
    content: `确定要删除选中的 ${selectedSessions.value.length} 个对话吗？此操作不可恢复。`,
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: {
      status: 'danger',
    },
    onOk: () => {
      emit('batch-delete-sessions', [...selectedSessions.value]);
      selectedSessions.value = [];
    },
  });
};

// 格式化时间显示
const formatTime = (date: Date) => {
  if (!date || !(date instanceof Date) || isNaN(date.getTime()) || date.getTime() === 0) {
    return '时间未知';
  }

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date >= today) {
    return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } else if (date >= yesterday) {
    return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } else {
    return `${date.getMonth() + 1}月${date.getDate()}日 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  }
};
</script>

<style scoped>
.chat-sidebar {
  width: 280px;
  background-color: #ffffff;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e5e6eb;
}

.header-row {
  display: flex;
  align-items: center;
  width: 100%;
}

.chat-history-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.empty-history {
  padding: 16px;
  color: #86909c;
  text-align: center;
}

.chat-history-item {
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background-color 0.2s;
}

.chat-history-item:hover {
  background-color: #f2f3f5;
}

.chat-history-item.active {
  background-color: #e8f3ff;
}

.history-item-checkbox {
  margin-right: 8px;
  flex-shrink: 0;
}

.history-item-content {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.history-item-icon {
  font-size: 16px;
  color: #4e5969;
  margin-right: 8px;
}

.history-item-info {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 14px;
  font-weight: 500;
  color: #1d2129;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-time {
  font-size: 12px;
  color: #86909c;
}

.history-item-actions {
  opacity: 0;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.chat-history-item:hover .history-item-actions {
  opacity: 1;
}
</style>