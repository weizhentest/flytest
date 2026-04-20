<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <span class="stat-label">日志总数</span>
      <strong>{{ statistics.total }}</strong>
      <span class="stat-desc">当前筛选范围内的通知记录数量</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">发送成功</span>
      <strong>{{ statistics.success }}</strong>
      <span class="stat-desc">成功送达邮箱或 Webhook 的记录</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">发送失败</span>
      <strong>{{ statistics.failed }}</strong>
      <span class="stat-desc">失败记录可进入详情查看投递上下文</span>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">历史重试</span>
      <strong>{{ statistics.retried }}</strong>
      <span class="stat-desc">保留历史上的已重试记录统计</span>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { NotificationsStatsGridProps } from './notificationViewModels'

defineProps<NotificationsStatsGridProps>()
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
  font-size: 30px;
  color: var(--theme-text);
  line-height: 1;
}

.stat-desc {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

@media (max-width: 1260px) {
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
