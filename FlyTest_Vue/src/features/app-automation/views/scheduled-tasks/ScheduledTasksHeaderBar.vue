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
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
