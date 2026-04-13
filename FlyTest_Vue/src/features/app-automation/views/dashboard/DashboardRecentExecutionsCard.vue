<template>
  <a-card class="panel-card recent-card" title="最近执行">
    <template #extra>
      <a-button type="text" @click="emit('open-all')">查看全部</a-button>
    </template>

    <a-table :data="executions" :pagination="false" size="small" :bordered="false">
      <template #columns>
        <a-table-column title="用例" data-index="case_name" />
        <a-table-column title="设备" data-index="device_name" />
        <a-table-column title="状态">
          <template #cell="{ record }">
            <a-tag :color="getExecutionStatusColor(record)">{{ getExecutionStatusLabel(record) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="进度">
          <template #cell="{ record }">{{ formatProgress(record.progress) }}%</template>
        </a-table-column>
        <a-table-column title="时间">
          <template #cell="{ record }">{{ formatDateTime(record.started_at || record.created_at) }}</template>
        </a-table-column>
        <a-table-column title="操作" :width="160">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-execution', record.id)">执行页</a-button>
              <a-button v-if="canOpenReport(record)" type="text" @click="emit('open-report', record.id)">报告</a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import type { AppExecution } from '../../types'

interface Props {
  executions: AppExecution[]
  getExecutionStatusColor: (record: AppExecution) => string
  getExecutionStatusLabel: (record: AppExecution) => string
  formatProgress: (value?: number | null) => number
  formatDateTime: (value?: string | null) => string
  canOpenReport: (record: AppExecution) => boolean
}

defineProps<Props>()

const emit = defineEmits<{
  'open-all': []
  'open-execution': [executionId: number]
  'open-report': [executionId: number]
}>()
</script>

<style scoped>
.panel-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 16px;
}

.recent-card :deep(.arco-table-th),
.recent-card :deep(.arco-table-td) {
  background: transparent;
}

.recent-card :deep(.arco-table-tr:hover > .arco-table-td) {
  background: rgba(var(--theme-accent-rgb), 0.04);
}
</style>
