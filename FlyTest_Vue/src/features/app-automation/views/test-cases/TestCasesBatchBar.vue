<template>
  <div v-if="selectedCount" class="batch-bar">
    <span>已选择 <strong>{{ selectedCount }}</strong> 个用例</span>
    <a-space wrap>
      <a-button type="primary" size="small" @click="emit('open-batch-execute')">批量执行</a-button>
      <a-button size="small" @click="emit('clear-selection')">取消选择</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { TestCasesBatchBarEmits } from './testCaseEventModels'
import type { TestCasesBatchBarProps } from './testCaseViewModels'

defineProps<TestCasesBatchBarProps>()

const emit = defineEmits<TestCasesBatchBarEmits>()
</script>

<style scoped>
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: var(--theme-text);
}

.batch-bar strong {
  color: var(--theme-accent);
}
</style>
