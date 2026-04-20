<template>
  <a-card class="table-card">
    <a-table :data="logs" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="任务" :width="220">
          <template #cell="{ record }">
            <div class="meta-stack">
              <strong>{{ record.task_name || '-' }}</strong>
              <span>{{ getTaskTypeLabel(record.task_type) }}</span>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="通知类型" :width="150">
          <template #cell="{ record }">
            <a-tag :color="getNotificationTypeColor(record.actual_notification_type || record.notification_type)">
              {{ getNotificationTypeLabel(record.actual_notification_type || record.notification_type) }}
            </a-tag>
          </template>
        </a-table-column>

        <a-table-column title="接收对象" :width="240">
          <template #cell="{ record }">
            <div class="meta-stack">
              <span>{{ recipientSummary(record) }}</span>
              <small>发送者：{{ record.sender_name || 'FlyTest' }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="状态 / 结果" :width="200">
          <template #cell="{ record }">
            <div class="meta-stack">
              <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
              <small>{{ getDeliverySummary(record) }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="通知时间" :width="210">
          <template #cell="{ record }">
            <div class="meta-stack">
              <span>创建：{{ formatDateTime(record.created_at) }}</span>
              <small>发送：{{ formatDateTime(record.sent_at) }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="操作" :width="280" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('view-detail', record)">详情</a-button>
              <a-button v-if="record.task_id" type="text" @click="emit('open-task-detail', record.task_id)">任务</a-button>
              <a-button
                v-if="getPrimaryExecutionId(record)"
                type="text"
                @click="emit('open-execution', record)"
              >
                执行
              </a-button>
              <a-button
                v-if="false"
                type="text"
                :loading="retryingId === record.id"
                @click="emit('retry', record.id)"
              >
                重试
              </a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>

    <div class="pagination-row">
      <a-pagination
        v-model:current="currentModel"
        v-model:page-size="pageSizeModel"
        :total="total"
        :show-total="true"
        :show-jumper="true"
        :show-page-size="true"
        :page-size-options="['10', '20', '50']"
      />
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { NotificationsTableCardEmits } from './notificationEventModels'
import type { NotificationsTableCardProps } from './notificationViewModels'

defineProps<NotificationsTableCardProps>()

const currentModel = defineModel<number>('current', { required: true })
const pageSizeModel = defineModel<number>('pageSize', { required: true })

const emit = defineEmits<NotificationsTableCardEmits>()
</script>

<style scoped>
.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.meta-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-stack strong,
.meta-stack span {
  color: var(--theme-text);
}

.meta-stack small {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.pagination-row {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
