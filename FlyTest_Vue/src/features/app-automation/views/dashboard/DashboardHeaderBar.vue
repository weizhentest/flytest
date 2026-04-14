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
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.page-actions {
  justify-content: flex-end;
}

.header-tip {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
