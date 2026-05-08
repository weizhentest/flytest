<template>
  <div class="page-header">
    <div>
      <h3>APP 自动化总控台</h3>
      <p>集中查看当前项目的 AI 编排状态、定时任务、执行健康度和最近回归动作。</p>
    </div>
    <a-space wrap class="page-actions">
      <a-tag :color="serviceStatusTagColor">{{ serviceStatusTagText }}</a-tag>
      <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
      <a-button :loading="aiStatusLoading" @click="emit('refresh-ai-status')">刷新 AI 状态</a-button>
      <a-button type="primary" :loading="loading" @click="emit('refresh-dashboard')">刷新总览</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { DashboardHeaderBarEmits } from './dashboardEventModels'
import type { DashboardHeaderBarProps } from './dashboardViewModels'

defineProps<DashboardHeaderBarProps>()

const emit = defineEmits<DashboardHeaderBarEmits>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid var(--theme-card-border);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.02)),
    var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
  font-size: 22px;
  line-height: 1.2;
}

.page-header p {
  max-width: 760px;
  margin: 8px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.page-actions {
  justify-content: flex-end;
  align-items: center;
}

.header-tip {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.page-header :deep(.arco-btn) {
  min-width: 104px;
  border-radius: 12px;
}

.page-header :deep(.arco-tag) {
  border-radius: 999px;
  padding-inline: 12px;
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    padding: 16px;
  }
}
</style>
