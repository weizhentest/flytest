<template>
  <div class="panel-shell">
    <a-card class="filter-card">
      <div class="filter-grid case-filter-grid">
        <a-input-search
          v-model="filters.search"
          allow-clear
          placeholder="搜索用例、设备、触发人或套件"
          @search="emit('search')"
        />
        <a-select v-model="filters.status" placeholder="执行状态" allow-clear>
          <a-option value="pending">等待执行</a-option>
          <a-option value="running">执行中</a-option>
          <a-option value="passed">执行通过</a-option>
          <a-option value="failed">执行失败</a-option>
          <a-option value="stopped">已停止</a-option>
        </a-select>
        <a-select v-model="filters.source" placeholder="执行来源">
          <a-option value="all">全部来源</a-option>
          <a-option value="suite">套件执行</a-option>
          <a-option value="standalone">独立执行</a-option>
        </a-select>
        <div class="filter-actions">
          <a-button @click="emit('reset')">重置</a-button>
          <a-button type="primary" @click="emit('search')">查询</a-button>
        </div>
      </div>
    </a-card>

    <div class="stats-grid">
      <a-card class="stat-card">
        <span class="stat-label">执行记录</span>
        <strong>{{ statistics.total }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">通过记录</span>
        <strong>{{ statistics.passed }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">失败记录</span>
        <strong>{{ statistics.failed }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">平均通过率</span>
        <strong>{{ statistics.passRate }}%</strong>
      </a-card>
    </div>

    <a-card class="table-card">
      <a-table :data="executions" :loading="loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="用例 / 设备" :width="260">
            <template #cell="{ record }">
              <div class="stack">
                <strong>{{ record.case_name || `执行 #${record.id}` }}</strong>
                <span>{{ record.device_name || record.device_serial || '未绑定设备' }}</span>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="执行来源" :width="220">
            <template #cell="{ record }">
              <div class="stack">
                <a-tag :color="record.test_suite_id ? 'green' : 'arcoblue'">
                  {{ record.test_suite_id ? '套件执行' : '独立执行' }}
                </a-tag>
                <small>{{ getExecutionSource(record) }}</small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="状态 / 通过率" :width="220">
            <template #cell="{ record }">
              <div class="stack">
                <a-tag :color="getExecutionStatus(record).color">{{ getExecutionStatus(record).label }}</a-tag>
                <small>通过率 {{ formatRate(record.pass_rate) }}%</small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="时间 / 耗时" :width="220">
            <template #cell="{ record }">
              <div class="stack">
                <span>{{ formatDateTime(record.started_at || record.created_at) }}</span>
                <small>耗时 {{ formatDuration(record.duration) }}</small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="操作" :width="220" fixed="right">
            <template #cell="{ record }">
              <a-space wrap>
                <a-button type="text" @click="emit('open-detail', record.id)">详情</a-button>
                <a-button v-if="canOpenReport(record)" type="text" @click="emit('open-report', record)">
                  报告
                </a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>

      <div class="pagination-row">
        <a-pagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :show-total="true"
          :show-jumper="true"
          :show-page-size="true"
          :page-size-options="['10', '20', '50']"
        />
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { AppExecution } from '../../types'

interface CaseFilters {
  search: string
  status: string
  source: string
}

interface PaginationState {
  current: number
  pageSize: number
}

interface CaseStats {
  total: number
  passed: number
  failed: number
  passRate: number
}

interface StatusMeta {
  label: string
  color: string
}

interface Props {
  loading: boolean
  filters: CaseFilters
  pagination: PaginationState
  statistics: CaseStats
  executions: AppExecution[]
  total: number
  formatDateTime: (value?: string | null) => string
  formatRate: (value?: number | null) => number
  formatDuration: (value?: number | null) => string
  getExecutionSource: (record: AppExecution) => string
  getExecutionStatus: (record: AppExecution) => StatusMeta
  canOpenReport: (record: AppExecution) => boolean
}

defineProps<Props>()

const emit = defineEmits<{
  search: []
  reset: []
  'open-detail': [id: number]
  'open-report': [record: AppExecution]
}>()
</script>

<style scoped>
.panel-shell,
.stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stack span,
.stack small {
  color: var(--theme-text-secondary);
}

.stack strong,
.stat-card strong {
  color: var(--theme-text);
}

.filter-card,
.table-card,
.stat-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.filter-grid {
  display: grid;
  gap: 12px;
  align-items: center;
}

.case-filter-grid {
  grid-template-columns: 1.5fr 180px 180px auto;
}

.filter-actions,
.pagination-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label {
  font-size: 13px;
  color: var(--theme-text-secondary);
}

.stat-card strong {
  font-size: 30px;
  line-height: 1;
}

@media (max-width: 1280px) {
  .case-filter-grid,
  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .case-filter-grid,
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
