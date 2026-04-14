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
      <span class="stat-label">离线设备</span>
      <strong>{{ stats.offline }}</strong>
    </a-card>
  </div>
</template>

<script setup lang="ts">
interface DeviceStats {
  total: number
  available: number
  locked: number
  offline: number
}

interface Props {
  stats: DeviceStats
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
  font-size: 24px;
  line-height: 1.2;
}

@media (max-width: 1080px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
