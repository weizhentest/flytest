<template>
  <a-card class="settings-card diagnostics-card">
    <template #title>服务运行状态</template>

    <div class="diagnostics-header">
      <div class="diagnostics-status">
        <a-tag :color="overallStatusColor">{{ overallStatusLabel }}</a-tag>
        <a-tag :color="serviceHealth.scheduler.running ? 'green' : 'red'">
          {{ serviceHealth.scheduler.running ? '调度器运行中' : '调度器未运行' }}
        </a-tag>
        <span v-if="serviceHealth.checked_at" class="checked-at">最近检测：{{ formatTime(serviceHealth.checked_at) }}</span>
      </div>
      <p class="diagnostics-hint">集中展示 APP 自动化服务、定时调度器、ADB 连通性和运行能力是否就绪，方便快速排查后台链路。</p>
    </div>

    <div class="actions">
      <a-space wrap>
        <a-button :loading="serviceHealthLoading" @click="emit('refresh-service-health')">刷新服务状态</a-button>
        <a-button :loading="diagnosticsLoading || runtimeLoading" @click="emit('reload-all')">刷新全部诊断</a-button>
      </a-space>
    </div>

    <div class="diagnostics-grid service-grid">
      <div class="diagnostic-item">
        <span>服务名称</span>
        <strong>{{ serviceHealth.service || 'app-automation' }}</strong>
        <small class="diagnostic-subtext">版本 {{ serviceHealth.version || '-' }}</small>
      </div>
      <div class="diagnostic-item">
        <span>调度器状态</span>
        <strong>{{ serviceHealth.scheduler.running ? '运行中' : '未运行' }}</strong>
        <small class="diagnostic-subtext">轮询间隔 {{ serviceHealth.scheduler.poll_interval_seconds || 0 }} 秒</small>
      </div>
      <div class="diagnostic-item">
        <span>正在触发任务</span>
        <strong>{{ serviceHealth.scheduler.running_tasks }}</strong>
        <small class="diagnostic-subtext">当前后台在途调度任务数</small>
      </div>
      <div class="diagnostic-item">
        <span>ADB 连通性</span>
        <strong>{{ diagnostics.executable_found ? '可用' : '未就绪' }}</strong>
        <small class="diagnostic-subtext">已发现 {{ diagnostics.device_count }} 台设备</small>
      </div>
      <div class="diagnostic-item">
        <span>运行能力</span>
        <strong>{{ runtimeReady ? '已就绪' : '待补齐' }}</strong>
        <small class="diagnostic-subtext">能力 {{ readyCapabilityCount }}/{{ runtimeCapabilities.capabilities.length }}</small>
      </div>
      <div class="diagnostic-item">
        <span>当前工作目录</span>
        <strong>{{ workspaceRoot || '使用默认目录' }}</strong>
        <small class="diagnostic-subtext">默认超时 {{ defaultTimeout }} 秒</small>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { SettingsServiceHealthCardEmits } from './settingsEventModels'
import type { SettingsServiceHealthCardProps } from './settingsViewModels'

defineProps<SettingsServiceHealthCardProps>()

const emit = defineEmits<SettingsServiceHealthCardEmits>()
</script>

<style scoped>
.settings-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.diagnostics-card {
  overflow: hidden;
}

.diagnostics-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.diagnostics-status {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.checked-at,
.diagnostics-hint {
  color: var(--color-text-2);
}

.diagnostics-hint {
  margin: 0;
}

.actions {
  margin-top: 8px;
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.service-grid {
  margin-top: 16px;
}

.diagnostic-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--color-border-2);
  background: var(--color-fill-2);
}

.diagnostic-item span {
  font-size: 12px;
  color: var(--color-text-3);
}

.diagnostic-item strong {
  color: var(--color-text-1);
  line-break: anywhere;
}

.diagnostic-subtext {
  color: var(--color-text-2);
  line-height: 1.6;
}
</style>
