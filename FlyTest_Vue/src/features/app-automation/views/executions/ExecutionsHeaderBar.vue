<template>
  <div class="page-header">
    <div>
      <h3>执行记录</h3>
      <p>集中查看 APP 自动化执行状态、进度、步骤结果和诊断日志，执行中的任务会自动刷新。</p>
    </div>
    <a-space>
      <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
      <a-button :loading="loading" @click="emit('refresh')">刷新</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { ExecutionsHeaderBarEmits } from './executionEventModels'
import type { ExecutionsHeaderBarProps } from './executionViewModels'

defineProps<ExecutionsHeaderBarProps>()

const emit = defineEmits<ExecutionsHeaderBarEmits>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid var(--theme-card-border);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.02)),
    var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
  font-size: 22px;
  line-height: 1.2;
}

.page-header p {
  max-width: 760px;
  margin: 8px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.header-tip {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.page-header :deep(.arco-btn) {
  min-width: 92px;
  border-radius: 12px;
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 16px;
  }
}
</style>
