<template>
  <a-card class="table-card">
    <template #title>
      <div class="card-title">
        <div class="card-title-copy">
          <span class="card-kicker">Execution Feed</span>
          <strong>最近执行记录</strong>
        </div>
        <span class="card-meta">最近 {{ executions.length }} 条</span>
      </div>
    </template>
    <a-table :data="executions" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="测试用例" :width="220">
          <template #cell="{ record }">{{ record.case_name || `执行 #${record.id}` }}</template>
        </a-table-column>
        <a-table-column title="设备" :width="180">
          <template #cell="{ record }">{{ record.device_name || record.device_serial || '-' }}</template>
        </a-table-column>
        <a-table-column title="状态" :width="120">
          <template #cell="{ record }">
            <a-tag :color="getResultColor(record.result || record.status)">{{ getExecutionResultLabel(record) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="进度 / 通过率" :width="220">
          <template #cell="{ record }">
            <div class="case-copy">
              <span>进度 {{ formatProgress(record.progress) }}%</span>
              <small>通过率 {{ formatRate(record.pass_rate) }}%</small>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="开始时间" :width="180">
          <template #cell="{ record }">{{ formatDateTime(record.started_at || record.created_at) }}</template>
        </a-table-column>
        <a-table-column title="操作" :width="220" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-execution-workspace', record.id)">执行页</a-button>
              <a-button v-if="canOpenExecutionReport(record)" type="text" @click="emit('open-execution-report', record.id)">
                报告
              </a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import type { TestCasesRecentExecutionsCardEmits } from './testCaseEventModels'
import type { TestCasesRecentExecutionsCardProps } from './testCaseViewModels'

defineProps<TestCasesRecentExecutionsCardProps>()

const emit = defineEmits<TestCasesRecentExecutionsCardEmits>()
</script>

<style scoped>
.table-card {
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.table-card :deep(.arco-card-header) {
  padding: 18px 22px 0;
  border-bottom: none;
}

.table-card :deep(.arco-card-body) {
  padding: 18px 22px 22px;
}

.table-card :deep(.arco-table-th) {
  background: rgba(var(--theme-accent-rgb), 0.06);
}

.table-card :deep(.arco-table-tr:hover .arco-table-td) {
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.card-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.card-title-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-kicker {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.card-title-copy strong {
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.card-meta {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.case-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-copy span,
.case-copy small {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

@media (max-width: 900px) {
  .card-title {
    flex-direction: column;
  }
}
</style>
