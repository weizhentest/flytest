<template>
  <a-card class="table-card">
    <a-table :data="tasks" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="任务" :width="260">
          <template #cell="{ record }">
            <div class="stack">
              <strong>{{ record.name }}</strong>
              <span>{{ record.description || '暂无任务描述' }}</span>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="类型 / 目标" :width="240">
          <template #cell="{ record }">
            <div class="stack">
              <a-tag :color="record.task_type === 'TEST_SUITE' ? 'green' : 'arcoblue'">
                {{ getTaskTypeLabel(record.task_type) }}
              </a-tag>
              <span>{{ getTaskTarget(record) }}</span>
              <small>{{ getPackageLabel(record) }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="调度配置" :width="220">
          <template #cell="{ record }">
            <div class="stack">
              <a-tag color="purple">{{ getTriggerTypeLabel(record.trigger_type) }}</a-tag>
              <span>{{ getTriggerSummary(record) }}</span>
              <small>下次执行：{{ formatDateTime(record.next_run_time) }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="执行概况" :width="220">
          <template #cell="{ record }">
            <div class="stack">
              <div class="inline-meta">
                <a-tag :color="getLastResultMeta(record).color">{{ getLastResultMeta(record).label }}</a-tag>
                <span class="plain-text">成功率 {{ getTaskSuccessRate(record) }}%</span>
              </div>
              <small>{{ getLastResultSummary(record) }}</small>
              <small>最近触发：{{ formatDateTime(record.last_run_time) }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="通知 / 状态" :width="220">
          <template #cell="{ record }">
            <div class="stack">
              <div class="inline-meta">
                <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
                <a-tag
                  v-if="record.notification_type"
                  :color="getNotificationColor(record.notification_type)"
                >
                  {{ getNotificationLabel(record.notification_type) }}
                </a-tag>
              </div>
              <span>{{ record.device_name || '未指定设备' }}</span>
              <small>{{ getNotificationSummary(record) }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="操作" :width="360" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-detail', record)">详情</a-button>
              <a-button
                type="text"
                :loading="isActionLoading('run', record.id)"
                @click="emit('run-now', record.id)"
              >
                立即执行
              </a-button>
              <a-button
                v-if="hasExecutionResult(record)"
                type="text"
                @click="emit('open-latest-execution', record)"
              >
                最新执行
              </a-button>
              <a-button type="text" @click="emit('open-edit', record)">编辑</a-button>
              <a-button
                v-if="record.status === 'ACTIVE'"
                type="text"
                :loading="isActionLoading('pause', record.id)"
                @click="emit('pause', record.id)"
              >
                暂停
              </a-button>
              <a-button
                v-else-if="record.status === 'PAUSED'"
                type="text"
                :loading="isActionLoading('resume', record.id)"
                @click="emit('resume', record.id)"
              >
                恢复
              </a-button>
              <a-button
                type="text"
                status="danger"
                :loading="isActionLoading('delete', record.id)"
                @click="emit('remove', record.id)"
              >
                删除
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
import type { AppScheduledTask } from '../../types'

interface ResultMeta {
  label: string
  color: string
}

interface Props {
  loading: boolean
  tasks: AppScheduledTask[]
  total: number
  formatDateTime: (value?: string | null) => string
  getTaskTypeLabel: (value: string) => string
  getTriggerTypeLabel: (value: string) => string
  getNotificationLabel: (value: string) => string
  getNotificationColor: (value: string) => string
  getStatusColor: (value: string) => string
  getTaskTarget: (task: AppScheduledTask) => string
  getPackageLabel: (task: AppScheduledTask) => string
  getTriggerSummary: (task: AppScheduledTask) => string
  getNotificationSummary: (task: AppScheduledTask) => string
  getLastResultMeta: (task: AppScheduledTask) => ResultMeta
  getTaskSuccessRate: (task: AppScheduledTask) => number
  getLastResultSummary: (task: AppScheduledTask) => string
  hasExecutionResult: (task: AppScheduledTask) => boolean
  isActionLoading: (action: string, id: number) => boolean
}

defineProps<Props>()

const currentModel = defineModel<number>('current', { required: true })
const pageSizeModel = defineModel<number>('pageSize', { required: true })

const emit = defineEmits<{
  'open-detail': [task: AppScheduledTask]
  'run-now': [id: number]
  'open-latest-execution': [task: AppScheduledTask]
  'open-edit': [task: AppScheduledTask]
  'pause': [id: number]
  'resume': [id: number]
  'remove': [id: number]
}>()
</script>

<style scoped>
.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.pagination-row {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stack strong,
.stack span,
.plain-text {
  color: var(--theme-text);
}

.stack span,
.stack small {
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.inline-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 900px) {
  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
