<template>
  <a-card class="panel-card" title="执行态势">
    <div class="summary-grid">
      <div class="summary-item">
        <span>总执行</span>
        <strong>{{ statistics.executions.total }}</strong>
      </div>
      <div class="summary-item">
        <span>运行中</span>
        <strong>{{ statistics.executions.running }}</strong>
      </div>
      <div class="summary-item">
        <span>通过</span>
        <strong class="success">{{ statistics.executions.passed }}</strong>
      </div>
      <div class="summary-item">
        <span>失败</span>
        <strong class="danger">{{ statistics.executions.failed }}</strong>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { AppDashboardStatistics } from '../../types'

interface Props {
  statistics: AppDashboardStatistics
}

defineProps<Props>()
</script>

<style scoped>
.panel-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.summary-item {
  padding: 16px;
  border-radius: 14px;
  background: rgba(var(--theme-accent-rgb), 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-item span {
  color: var(--theme-text-secondary);
}

.summary-item strong {
  font-size: 28px;
  color: var(--theme-text);
}

.summary-item .success {
  color: var(--theme-success);
}

.summary-item .danger {
  color: var(--theme-danger);
}
</style>
