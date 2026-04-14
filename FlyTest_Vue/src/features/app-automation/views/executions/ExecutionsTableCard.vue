<template>
  <a-card class="table-card">
    <a-table :data="executions" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="用例 / 设备" :width="260">
          <template #cell="{ record }">
            <div class="name-cell">
              <strong>{{ record.case_name || `执行 #${record.id}` }}</strong>
              <span>{{ record.device_name || record.device_serial || '未绑定设备' }}</span>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="执行来源" :width="220">
          <template #cell="{ record }">
            <div class="meta-stack">
              <a-tag :color="record.test_suite_id ? 'green' : 'arcoblue'">
                {{ record.test_suite_id ? '套件执行' : '独立执行' }}
              </a-tag>
              <span>{{ getExecutionSource(record) }}</span>
              <small>触发人：{{ record.triggered_by || '-' }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="状态 / 进度" :width="240">
          <template #cell="{ record }">
            <div class="progress-cell">
              <div class="progress-head">
                <a-tag :color="getExecutionStatusMeta(record).color">
                  {{ getExecutionStatusMeta(record).label }}
                </a-tag>
                <span>{{ formatProgress(record.progress) }}%</span>
              </div>
              <div class="progress-track">
                <div
                  class="progress-fill"
                  :style="{
                    width: `${formatProgress(record.progress)}%`,
                    background: getExecutionStatusMeta(record).hex,
                  }"
                />
              </div>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="步骤统计" :width="200">
          <template #cell="{ record }">
            <div class="stats-cell">
              <span class="success-text">通过 {{ record.passed_steps || 0 }}</span>
              <span class="danger-text">失败 {{ record.failed_steps || 0 }}</span>
              <small>总计 {{ record.total_steps || 0 }} 步 / 通过率 {{ formatRate(record.pass_rate) }}%</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="时间信息" :width="220">
          <template #cell="{ record }">
            <div class="meta-stack">
              <span>开始：{{ formatDateTime(record.started_at || record.created_at) }}</span>
              <small>结束：{{ formatDateTime(record.finished_at) }}</small>
              <small>耗时：{{ formatDuration(record.duration) }}</small>
            </div>
          </template>
        </a-table-column>

        <a-table-column title="操作" :width="260" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('view-detail', record.id)">详情</a-button>
              <a-button v-if="canOpenReport(record)" type="text" @click="emit('open-report', record)">报告</a-button>
              <a-button
                v-if="isExecutionRunning(record)"
                type="text"
                status="danger"
                :loading="Boolean(stoppingIds[record.id])"
                @click="emit('stop-execution', record)"
              >
                停止
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
import type { AppExecution } from '../../types'

interface ExecutionStatusMeta {
  label: string
  color: string
  hex: string
}

interface Props {
  loading: boolean
  executions: AppExecution[]
  total: number
  stoppingIds: Record<number, boolean>
  formatDateTime: (value?: string | null) => string
  formatDuration: (value?: number | null) => string
  formatRate: (value?: number | null) => number
  formatProgress: (value?: number | null) => number
  getExecutionSource: (record: AppExecution) => string
  getExecutionStatusMeta: (record: AppExecution) => ExecutionStatusMeta
  canOpenReport: (record: AppExecution) => boolean
  isExecutionRunning: (record: AppExecution) => boolean
}

defineProps<Props>()

const currentModel = defineModel<number>('current', { required: true })
const pageSizeModel = defineModel<number>('pageSize', { required: true })

const emit = defineEmits<{
  'view-detail': [id: number]
  'open-report': [record: AppExecution]
  'stop-execution': [record: AppExecution]
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
  justify-content: flex-end;
  margin-top: 16px;
}

.name-cell,
.meta-stack,
.stats-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-cell strong,
.meta-stack span,
.stats-cell span {
  color: var(--theme-text);
}

.name-cell span,
.meta-stack small,
.stats-cell small {
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.progress-cell {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.progress-head span {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(var(--theme-accent-rgb), 0.08);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.2s ease;
}

.success-text {
  color: #4caf50 !important;
}

.danger-text {
  color: #f44336 !important;
}

@media (max-width: 900px) {
  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
