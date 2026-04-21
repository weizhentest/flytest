<template>
  <a-modal
    v-model:visible="visibleModel"
    title="通知详情"
    width="900px"
    :footer="false"
  >
    <div v-if="currentLog" class="detail-shell">
      <div class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">任务名称</span>
          <strong>{{ currentLog.task_name || '-' }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">任务类型</span>
          <strong>{{ getTaskTypeLabel(currentLog.task_type) }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">通知类型</span>
          <strong>{{ getNotificationTypeLabel(currentLog.actual_notification_type || currentLog.notification_type) }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">发送状态</span>
          <strong>{{ currentLog.status }}</strong>
        </div>
      </div>

      <a-card class="detail-panel" title="投递信息">
        <div class="meta-row">
          <span>发送者：{{ currentLog.sender_name || '-' }}</span>
          <span>发送邮箱：{{ currentLog.sender_email || '-' }}</span>
          <span>接收对象：{{ recipientSummary(currentLog) }}</span>
          <span>创建时间：{{ formatDateTime(currentLog.created_at) }}</span>
          <span>发送时间：{{ formatDateTime(currentLog.sent_at) }}</span>
          <span>重试次数：{{ currentLog.retry_count || 0 }}</span>
        </div>
        <a-space wrap>
          <a-button
            v-if="currentLog.status !== 'success'"
            status="warning"
            :loading="retrying"
            @click="emit('retry', currentLog)"
          >
            重试通知
          </a-button>
          <a-button v-if="currentLog.task_id" @click="emit('open-task-detail', currentLog.task_id)">
            查看任务
          </a-button>
          <a-button
            v-if="getPrimaryExecutionId(currentLog)"
            type="primary"
            @click="emit('open-execution', currentLog)"
          >
            查看执行
          </a-button>
        </a-space>
      </a-card>

      <a-card class="detail-panel" title="通知内容">
        <div v-if="parsedContent.length" class="parsed-content">
          <div v-for="item in parsedContent" :key="`${item.label}-${item.value}`" class="parsed-row">
            <span class="parsed-label">{{ item.label }}</span>
            <span class="parsed-value">{{ item.value }}</span>
          </div>
        </div>
        <a-textarea
          v-else
          :model-value="currentLog.notification_content || '-'"
          readonly
          :auto-size="{ minRows: 8, maxRows: 16 }"
        />
      </a-card>

      <a-card class="detail-panel" title="响应 / 错误信息">
        <a-alert v-if="currentLog.error_message" type="error" class="detail-alert">
          {{ currentLog.error_message }}
        </a-alert>
        <a-textarea
          :model-value="JSON.stringify(currentLog.response_info || {}, null, 2)"
          readonly
          :auto-size="{ minRows: 8, maxRows: 16 }"
        />
      </a-card>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { NotificationDetailDialogEmits } from './notificationEventModels'
import type { NotificationDetailDialogProps } from './notificationViewModels'

defineProps<NotificationDetailDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<NotificationDetailDialogEmits>()
</script>

<style scoped>
.detail-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.detail-card,
.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-card {
  padding: 16px;
  border-radius: 16px;
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-label,
.meta-row {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.detail-card strong,
.parsed-value {
  color: var(--theme-text);
}

.detail-label {
  display: block;
  margin-bottom: 8px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-bottom: 14px;
}

.detail-alert {
  margin-bottom: 14px;
}

.parsed-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.parsed-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 16px;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(var(--theme-accent-rgb), 0.16);
}

.parsed-label {
  color: var(--theme-text-secondary);
}
</style>
