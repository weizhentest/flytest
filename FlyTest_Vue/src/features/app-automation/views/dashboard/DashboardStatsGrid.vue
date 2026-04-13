<template>
  <div class="stats-grid">
    <a-card class="stat-card">
      <div class="stat-label">设备在线</div>
      <div class="stat-value">{{ statistics.devices.online }}</div>
      <div class="stat-meta">总设备 {{ statistics.devices.total }} / 锁定 {{ statistics.devices.locked }}</div>
    </a-card>
    <a-card class="stat-card">
      <div class="stat-label">应用包</div>
      <div class="stat-value">{{ statistics.packages.total }}</div>
      <div class="stat-meta">当前项目已登记应用</div>
    </a-card>
    <a-card class="stat-card">
      <div class="stat-label">元素资产</div>
      <div class="stat-value">{{ statistics.elements.total }}</div>
      <div class="stat-meta">用于定位与页面编排</div>
    </a-card>
    <a-card class="stat-card">
      <div class="stat-label">测试用例</div>
      <div class="stat-value">{{ statistics.test_cases.total }}</div>
      <div class="stat-meta">通过率 {{ statistics.executions.pass_rate }}%</div>
    </a-card>
    <a-card class="stat-card">
      <div class="stat-label">激活任务</div>
      <div class="stat-value">{{ activeTaskCount }}</div>
      <div class="stat-meta">暂停 {{ pausedTaskCount }} / 失败 {{ failedTaskCount }}</div>
    </a-card>
    <a-card class="stat-card">
      <div class="stat-label">AI 智能模式</div>
      <div class="stat-value">{{ aiReady ? 'ON' : aiHasConfig ? 'Fallback' : 'OFF' }}</div>
      <div class="stat-meta">{{ aiCapabilityDisplay }}</div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { AppDashboardStatistics } from '../../types'

interface Props {
  statistics: AppDashboardStatistics
  activeTaskCount: number
  pausedTaskCount: number
  failedTaskCount: number
  aiReady: boolean
  aiHasConfig: boolean
  aiCapabilityDisplay: string
}

defineProps<Props>()
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.stat-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 16px;
}

.stat-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.stat-value {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 700;
  color: var(--theme-text);
}

.stat-meta {
  margin-top: 8px;
  color: var(--theme-text-tertiary);
  font-size: 12px;
}
</style>
