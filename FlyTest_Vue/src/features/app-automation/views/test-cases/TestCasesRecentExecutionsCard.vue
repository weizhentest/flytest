<template>
  <a-card class="table-card">
    <template #title>最近执行记录</template>
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
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
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
</style>
