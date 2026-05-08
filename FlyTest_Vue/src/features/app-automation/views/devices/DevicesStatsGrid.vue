<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <span class="stat-label">设备总数</span>
      <strong>{{ stats.total }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">可用设备</span>
      <strong>{{ stats.available }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">锁定中</span>
      <strong>{{ stats.locked }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">正在停止</span>
      <strong>{{ stats.stopping }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">离线设备</span>
      <strong>{{ stats.offline }}</strong>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { DevicesStatsGridProps } from './deviceViewModels'

defineProps<DevicesStatsGridProps>()
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 18px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.stat-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.05), transparent 42%);
  pointer-events: none;
}

.stat-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 126px;
  padding: 20px;
}

.stat-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
  letter-spacing: 0.2px;
}

.stat-card strong {
  color: var(--theme-text);
  font-size: 30px;
  line-height: 1.1;
}

@media (max-width: 1080px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .stat-card :deep(.arco-card-body) {
    min-height: 112px;
    padding: 18px;
  }
}
</style>
