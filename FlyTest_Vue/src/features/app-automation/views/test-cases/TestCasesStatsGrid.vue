<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <span class="stat-label">用例总数</span>
      <strong>{{ statistics.total }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">最近通过</span>
      <strong>{{ statistics.passed }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">最近失败</span>
      <strong>{{ statistics.failed }}</strong>
    </a-card>
    <a-card class="stat-card">
      <span class="stat-label">未执行</span>
      <strong>{{ statistics.pending }}</strong>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { TestCasesStatsGridProps } from './testCaseViewModels'

defineProps<TestCasesStatsGridProps>()
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
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .stat-card :deep(.arco-card-body) {
    min-height: 112px;
    padding: 18px;
  }
}
</style>
