<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="selectedSuite ? `${selectedSuite.name} 执行记录` : '套件执行记录'"
    width="980px"
    :footer="false"
  >
    <a-table :data="suiteExecutions" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="测试用例" data-index="case_name" />
        <a-table-column title="设备" data-index="device_name" />
        <a-table-column title="状态">
          <template #cell="{ record }">
            <a-tag :color="getExecutionStatus(record).color">{{ getExecutionStatus(record).label }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="通过率">
          <template #cell="{ record }">{{ formatRate(record.pass_rate) }}%</template>
        </a-table-column>
        <a-table-column title="操作" :width="180">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-detail', record.id)">详情</a-button>
              <a-button v-if="canOpenReport(record)" type="text" @click="emit('open-report', record)">报告</a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import type { ReportsSuiteExecutionsDialogEmits } from './reportEventModels'
import type { ReportsSuiteExecutionsDialogProps } from './reportViewModels'

defineProps<ReportsSuiteExecutionsDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<ReportsSuiteExecutionsDialogEmits>()
</script>
