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
interface PackageStats {
  total: number
  android: number
  ios: number
  configuredActivity: number
}

interface Props {
  stats: PackageStats
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
  font-size: 13px;
  color: var(--theme-text-secondary);
}

.stat-card strong {
  font-size: 28px;
  color: var(--theme-text);
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
}
</style>
