<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <span class="stat-label">执行总数</span>
      <strong>{{ statistics.total }}</strong>
      <span class="stat-desc">当前筛选范围内的执行记录数量</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">运行中 / 等待中</span>
      <strong>{{ statistics.running }}</strong>
      <span class="stat-desc">页面会自动轮询这些任务的最新状态</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">通过记录</span>
      <strong>{{ statistics.passed }}</strong>
      <span class="stat-desc">已完成且通过的执行结果</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">平均通过率</span>
      <strong>{{ statistics.averagePassRate }}%</strong>
      <span class="stat-desc">按当前结果集统计步骤通过率</span>
    </a-card>
  </div>
</template>

<script setup lang="ts">
interface ExecutionStatistics {
  total: number
  running: number
  passed: number
  averagePassRate: number
}

interface Props {
  statistics: ExecutionStatistics
}

defineProps<Props>()
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

@media (max-width: 1280px) {
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
