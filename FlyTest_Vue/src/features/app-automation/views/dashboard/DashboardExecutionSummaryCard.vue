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
import type { DashboardExecutionSummaryCardProps } from './dashboardViewModels'

defineProps<DashboardExecutionSummaryCardProps>()
</script>

<style scoped>
.panel-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 18px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.summary-item {
  padding: 18px;
  border-radius: 16px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.025)),
    rgba(var(--theme-accent-rgb), 0.08);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-item span {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.summary-item strong {
  font-size: 28px;
  color: var(--theme-text);
  line-height: 1.1;
}

.summary-item .success {
  color: var(--theme-success);
}

.summary-item .danger {
  color: var(--theme-danger);
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
