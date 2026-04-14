<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <span class="stat-label">任务总数</span>
      <strong>{{ statistics.total }}</strong>
      <span class="stat-desc">当前筛选结果中的调度任务数量</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">激活任务</span>
      <strong>{{ statistics.active }}</strong>
      <span class="stat-desc">仍在自动调度中的任务</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">暂停任务</span>
      <strong>{{ statistics.paused }}</strong>
      <span class="stat-desc">已保留配置但暂停调度的任务</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">触发成功率</span>
      <strong>{{ statistics.successRate }}%</strong>
      <span class="stat-desc">成功 {{ statistics.successfulRuns }} / 总触发 {{ statistics.totalRuns }}</span>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { ScheduledTaskStatsGridProps } from './scheduledTaskViewModels'

defineProps<ScheduledTaskStatsGridProps>()
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.stat-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.stat-card strong {
  color: var(--theme-text);
  font-size: 30px;
  line-height: 1;
}

.stat-desc {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

@media (max-width: 1360px) {
  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
