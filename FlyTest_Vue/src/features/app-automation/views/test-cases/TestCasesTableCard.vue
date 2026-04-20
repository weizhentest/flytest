<template>
  <a-card class="table-card">
    <a-table
      v-model:selectedKeys="selectedCaseIdsModel"
      :data="cases"
      :loading="loading"
      :pagination="false"
      :row-selection="rowSelection"
      row-key="id"
    >
      <template #columns>
        <a-table-column title="用例名称" :width="240">
          <template #cell="{ record }">
            <div class="case-copy">
              <strong>{{ record.name }}</strong>
              <span>{{ record.description || '未填写描述' }}</span>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="应用包" :width="180">
          <template #cell="{ record }">{{ record.package_display_name || '-' }}</template>
        </a-table-column>
        <a-table-column title="步骤数" :width="100">
          <template #cell="{ record }">{{ getStepCount(record) }}</template>
        </a-table-column>
        <a-table-column title="最近结果" :width="120">
          <template #cell="{ record }">
            <a-tag :color="getResultColor(record.last_result)">{{ getResultLabel(record.last_result) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="最近运行" :width="180">
          <template #cell="{ record }">{{ formatDateTime(record.last_run_at) }}</template>
        </a-table-column>
        <a-table-column title="更新时间" :width="180">
          <template #cell="{ record }">{{ formatDateTime(record.updated_at) }}</template>
        </a-table-column>
        <a-table-column title="操作" :width="420" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-execute', record)">执行</a-button>
              <a-button type="text" @click="emit('open-scene-builder', record)">编辑</a-button>
              <a-button type="text" @click="emit('open-edit', record)">快速编辑</a-button>
              <a-button type="text" @click="emit('duplicate-case', record)">复制</a-button>
              <a-button
                type="text"
                status="danger"
                :disabled="record.can_delete === false"
                :title="record.delete_block_reason || ''"
                @click="emit('remove', record.id)"
              >
                删除
              </a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import type { TestCasesTableCardEmits } from './testCaseEventModels'
import type { TestCasesTableCardProps } from './testCaseViewModels'

defineProps<TestCasesTableCardProps>()

const selectedCaseIdsModel = defineModel<number[]>('selectedCaseIds', { required: true })

const rowSelection = {
  type: 'checkbox' as const,
  showCheckedAll: true,
}

const emit = defineEmits<TestCasesTableCardEmits>()
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

.case-copy strong {
  color: var(--theme-text);
}

.case-copy span {
  color: var(--theme-text-secondary);
  font-size: 13px;
}
</style>
