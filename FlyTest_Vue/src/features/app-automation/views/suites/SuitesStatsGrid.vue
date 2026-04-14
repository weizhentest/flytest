<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <span class="stat-label">套件总数</span>
      <strong>{{ statistics.total }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">执行中</span>
      <strong>{{ statistics.running }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">执行通过</span>
      <strong>{{ statistics.passed }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">已停止</span>
      <strong>{{ statistics.stopped }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">平均健康度</span>
      <strong>{{ statistics.health }}%</strong>
    </a-card>
  </div>
</template>

<script setup lang="ts">
interface SuiteStats {
  total: number
  running: number
  passed: number
  stopped: number
  health: number
}

interface Props {
  statistics: SuiteStats
}

defineProps<Props>()
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
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
  font-size: 24px;
  line-height: 1.2;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
