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
  color: var(--theme-text-secondary);
  font-size: 13px;
  letter-spacing: 0.2px;
}

.stat-card strong {
  font-size: 30px;
  color: var(--theme-text);
  line-height: 1.1;
}

.stat-desc {
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.65;
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

  .stat-card :deep(.arco-card-body) {
    min-height: 118px;
    padding: 18px;
  }
}
</style>
