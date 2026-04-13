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
import type {
  AppNotificationLog,
  AppScheduledTask,
} from '../../types'

interface ResultMeta {
  label: string
  color: string
}

interface Props {
  detailLoading: boolean
  taskNotificationsLoading: boolean
  currentTask: AppScheduledTask | null
  recentTaskNotifications: AppNotificationLog[]
  formatDateTime: (value?: string | null) => string
  getTaskTypeLabel: (value: string) => string
  getTaskTarget: (task: AppScheduledTask) => string
  getNotificationLabel: (value: string) => string
  getNotificationColor: (value: string) => string
  getNotificationStatusColor: (value: string) => string
  getLastResultMeta: (task: AppScheduledTask) => ResultMeta
  getTaskSuccessRate: (task: AppScheduledTask) => number
  getLastResultSummary: (task: AppScheduledTask) => string
  getNotificationDetail: (item: AppNotificationLog) => string
  getPrimaryExecutionIdFromLog: (item: AppNotificationLog) => number | undefined
  getTriggerSummary: (task: AppScheduledTask) => string
  getNotificationSummary: (task: AppScheduledTask) => string
  hasExecutionResult: (task: AppScheduledTask) => boolean
  hasLatestReport: (task: AppScheduledTask) => boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  'open-latest-execution': [task: AppScheduledTask]
  'open-latest-report': [task: AppScheduledTask]
  'open-task-notifications': [task: AppScheduledTask]
  'open-notification-execution': [item: AppNotificationLog]
}>()
</script>

<style scoped>
.modal-state,
.empty-note {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
  color: var(--theme-text-secondary);
}

.modal-state.small {
  min-height: 120px;
}

.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-shell,
.notification-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-card,
.notification-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-card strong {
  color: var(--theme-text);
}

.detail-label {
  display: block;
  margin-bottom: 8px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.summary-text {
  color: var(--theme-text);
  line-height: 1.7;
  margin-bottom: 14px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-bottom: 14px;
  color: var(--theme-text-secondary);
  font-size: 13px;
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
}
</style>
