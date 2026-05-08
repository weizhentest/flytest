<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="selectedSuite ? `${selectedSuite.name} 执行历史` : '套件执行历史'"
    width="980px"
    :footer="false"
  >
    <a-table :data="history" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="用例 / 设备" :width="240">
          <template #cell="{ record }">
            <div class="stack">
              <strong>{{ record.case_name || `执行 #${record.id}` }}</strong>
              <span>{{ record.device_name || record.device_serial || '-' }}</span>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="状态 / 通过率" :width="180">
          <template #cell="{ record }">
            <div class="stack">
              <a-tag :color="getExecutionStatusMeta(record).color">{{ getExecutionStatusMeta(record).label }}</a-tag>
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
              <a-button type="text" @click="emit('open-execution-detail', record.id)">详情</a-button>
              <a-button type="text" @click="emit('open-workspace', record.id, selectedSuite?.id || null)">执行页</a-button>
              <a-button v-if="canOpenReport(record)" type="text" @click="emit('open-report', record)">报告</a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import type { SuiteHistoryDialogEmits } from './suiteEventModels'
import type { SuiteHistoryDialogProps } from './suiteViewModels'

defineProps<SuiteHistoryDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<SuiteHistoryDialogEmits>()
</script>

<style scoped>
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
  padding: 20px 24px 24px;
}

:deep(.arco-table) {
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  border-radius: 18px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.02);
}

:deep(.arco-table-th) {
  background: rgba(var(--theme-accent-rgb), 0.06);
}

:deep(.arco-table-tr:hover .arco-table-td) {
  background: rgba(var(--theme-accent-rgb), 0.045);
}

:deep(.arco-btn-text) {
  padding: 0 6px;
  border-radius: 10px;
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stack strong {
  color: var(--theme-text);
  font-size: 14px;
}

.stack span,
.stack small {
  color: var(--theme-text-secondary);
  line-height: 1.6;
}

@media (max-width: 900px) {
  :deep(.arco-modal-body) {
    padding: 16px;
  }
}
</style>
