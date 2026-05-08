<template>
  <a-modal
    v-model:visible="visibleModel"
    title="任务详情"
    width="980px"
    :footer="false"
  >
    <div v-if="detailLoading" class="modal-state">正在加载任务详情...</div>
    <div v-else-if="currentTask" class="detail-shell">
      <div class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">任务状态</span>
          <strong>{{ currentTask.status }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">最近结果</span>
          <strong>{{ getLastResultMeta(currentTask).label }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">下次执行</span>
          <strong>{{ formatDateTime(currentTask.next_run_time) }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">触发成功率</span>
          <strong>{{ getTaskSuccessRate(currentTask) }}%</strong>
        </div>
      </div>

      <a-card class="detail-panel" title="任务配置">
        <div class="summary-text">{{ currentTask.description || '暂无任务描述。' }}</div>
        <div class="meta-row">
          <span>任务类型：{{ getTaskTypeLabel(currentTask.task_type) }}</span>
          <span>任务目标：{{ getTaskTarget(currentTask) }}</span>
          <span>执行设备：{{ currentTask.device_name || '-' }}</span>
          <span>应用包：{{ currentTask.app_package_name || '-' }}</span>
          <span>触发方式：{{ getTriggerSummary(currentTask) }}</span>
          <span>创建人：{{ currentTask.created_by || '-' }}</span>
        </div>
        <div class="meta-row">
          <span>通知渠道：{{ getNotificationLabel(currentTask.notification_type) }}</span>
          <span>通知对象：{{ getNotificationSummary(currentTask) }}</span>
          <span>创建时间：{{ formatDateTime(currentTask.created_at) }}</span>
          <span>更新时间：{{ formatDateTime(currentTask.updated_at) }}</span>
        </div>
      </a-card>

      <a-card class="detail-panel" title="最近触发结果">
        <div class="summary-text">{{ getLastResultSummary(currentTask) }}</div>
        <div class="meta-row">
          <span>最近触发时间：{{ formatDateTime(currentTask.last_run_time) }}</span>
          <span>累计触发：{{ currentTask.total_runs || 0 }}</span>
          <span>成功次数：{{ currentTask.successful_runs || 0 }}</span>
          <span>失败次数：{{ currentTask.failed_runs || 0 }}</span>
        </div>
        <a-alert v-if="currentTask.error_message" type="error" class="detail-alert">
          {{ currentTask.error_message }}
        </a-alert>
        <a-space wrap>
          <a-button
            v-if="hasExecutionResult(currentTask)"
            type="primary"
            @click="emit('open-latest-execution', currentTask)"
          >
            查看执行记录
          </a-button>
          <a-button
            v-if="hasLatestReport(currentTask)"
            @click="emit('open-latest-report', currentTask)"
          >
            打开最近报告
          </a-button>
          <a-button @click="emit('open-task-notifications', currentTask)">查看通知日志</a-button>
        </a-space>
      </a-card>

      <a-card class="detail-panel" title="最近通知">
        <div v-if="taskNotificationsLoading" class="modal-state small">正在加载通知日志...</div>
        <div v-else-if="recentTaskNotifications.length" class="notification-list">
          <div
            v-for="item in recentTaskNotifications"
            :key="item.id"
            class="notification-item"
          >
            <div class="notification-head">
              <div class="inline-meta">
                <a-tag :color="getNotificationStatusColor(item.status)">{{ item.status }}</a-tag>
                <a-tag :color="getNotificationColor(item.actual_notification_type || item.notification_type)">
                  {{ getNotificationLabel(item.actual_notification_type || item.notification_type) }}
                </a-tag>
              </div>
              <span>{{ formatDateTime(item.created_at) }}</span>
            </div>
            <div class="notification-body">
              {{ item.error_message || getNotificationDetail(item) }}
            </div>
            <div class="notification-actions">
              <a-button type="text" @click="emit('open-task-notifications', currentTask)">查看日志</a-button>
              <a-button
                v-if="getPrimaryExecutionIdFromLog(item)"
                type="text"
                @click="emit('open-notification-execution', item)"
              >
                关联执行
              </a-button>
            </div>
          </div>
        </div>
        <div v-else class="empty-note">当前任务还没有通知日志。</div>
      </a-card>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { ScheduledTaskDetailDialogEmits } from './scheduledTaskEventModels'
import type { ScheduledTaskDetailDialogProps } from './scheduledTaskViewModels'

defineProps<ScheduledTaskDetailDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<ScheduledTaskDetailDialogEmits>()
</script>

<style scoped>
.modal-state,
.empty-note {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--theme-accent-rgb), 0.04);
  border: 1px dashed rgba(var(--theme-accent-rgb), 0.14);
  border-radius: 16px;
  color: var(--theme-text-secondary);
}

.modal-state.small {
  min-height: 120px;
}

.detail-panel {
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-panel :deep(.arco-card-header) {
  min-height: 60px;
  padding: 0 22px;
  border-bottom-color: rgba(var(--theme-accent-rgb), 0.12);
}

.detail-panel :deep(.arco-card-header-title) {
  color: var(--theme-text);
  font-size: 15px;
  font-weight: 700;
}

.detail-panel :deep(.arco-card-body) {
  padding: 22px;
}

.detail-shell,
.notification-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.detail-card,
.notification-item {
  padding: 18px;
  border-radius: 16px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.03)),
    rgba(var(--theme-accent-rgb), 0.04);
}

.detail-card strong {
  color: var(--theme-text);
  font-size: 28px;
  line-height: 1.15;
}

.detail-label {
  display: block;
  margin-bottom: 10px;
  color: var(--theme-text-secondary);
  font-size: 13px;
  letter-spacing: 0.2px;
}

.summary-text {
  color: var(--theme-text);
  line-height: 1.7;
  white-space: pre-wrap;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  margin-top: 14px;
  padding-top: 14px;
  color: var(--theme-text-secondary);
  font-size: 13px;
  border-top: 1px dashed rgba(var(--theme-accent-rgb), 0.14);
}

.detail-alert {
  margin-bottom: 14px;
}

.inline-meta,
.notification-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.notification-actions {
  gap: 10px;
}

.notification-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.notification-body {
  color: var(--theme-text);
  line-height: 1.7;
  margin-bottom: 10px;
  word-break: break-word;
}

:deep(.arco-modal-header) {
  min-height: 68px;
  padding: 0 24px;
  border-bottom: 1px solid rgba(var(--theme-accent-rgb), 0.12);
}

:deep(.arco-modal-title) {
  color: var(--theme-text);
  font-size: 18px;
  font-weight: 700;
}

:deep(.arco-modal-body) {
  padding: 22px 24px 24px;
}

@media (max-width: 1360px) {
  .detail-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .notification-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .detail-panel :deep(.arco-card-body),
  :deep(.arco-modal-body) {
    padding: 18px;
  }
}
</style>
