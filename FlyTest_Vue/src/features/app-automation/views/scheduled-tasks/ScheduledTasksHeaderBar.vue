<template>
  <div class="page-header">
    <div>
      <h3>定时任务</h3>
      <p>统一管理 APP 自动化调度任务，支持触发、排查、通知回看和最近执行追踪。</p>
    </div>
    <a-space>
      <a-button :loading="loading" @click="emit('refresh')">刷新</a-button>
      <a-button type="primary" @click="emit('create')">新建任务</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { ScheduledTaskHeaderBarEmits } from './scheduledTaskEventModels'
import type { ScheduledTaskHeaderBarProps } from './scheduledTaskViewModels'

defineProps<ScheduledTaskHeaderBarProps>()

const emit = defineEmits<ScheduledTaskHeaderBarEmits>()
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
