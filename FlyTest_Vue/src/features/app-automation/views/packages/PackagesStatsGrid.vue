<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <span class="stat-label">应用包总数</span>
      <strong>{{ stats.total }}</strong>
      <span class="stat-desc">当前筛选范围内可管理的 APP 包数量</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">Android 包</span>
      <strong>{{ stats.android }}</strong>
      <span class="stat-desc">适用于 Android 设备执行与调试</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">iOS 包</span>
      <strong>{{ stats.ios }}</strong>
      <span class="stat-desc">已登记的 iOS 包与启动信息</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">已配置 Activity</span>
      <strong>{{ stats.configuredActivity }}</strong>
      <span class="stat-desc">可直接用于启动或执行的应用包</span>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { PackagesStatsGridProps } from './packageViewModels'

defineProps<PackagesStatsGridProps>()
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  min-height: 138px;
  padding: 20px;
}

.stat-label {
  font-size: 13px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.2px;
}

.stat-card strong {
  font-size: 30px;
  color: var(--theme-text);
  line-height: 1.1;
}

.stat-desc {
  font-size: 12px;
  color: var(--theme-text-secondary);
  line-height: 1.6;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .stat-card :deep(.arco-card-body) {
    min-height: 118px;
    padding: 18px;
  }
}
</style>
