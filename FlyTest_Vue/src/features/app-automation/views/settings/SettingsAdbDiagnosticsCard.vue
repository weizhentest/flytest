<template>
  <a-card class="settings-card diagnostics-card">
    <template #title>ADB 环境诊断</template>

    <div class="diagnostics-header">
      <div class="diagnostics-status">
        <a-tag :color="statusColor">{{ statusLabel }}</a-tag>
        <span v-if="diagnostics.checked_at" class="checked-at">最近检测：{{ formatTime(diagnostics.checked_at) }}</span>
      </div>
      <p class="diagnostics-hint">这里会展示当前配置路径、实际解析到的 ADB、版本信息以及已发现的设备数量。</p>
    </div>

    <div class="diagnostics-grid">
      <div class="diagnostic-item">
        <span>配置路径</span>
        <strong>{{ diagnostics.configured_path || '-' }}</strong>
      </div>
      <div class="diagnostic-item">
        <span>解析路径</span>
        <strong>{{ diagnostics.resolved_path || '-' }}</strong>
      </div>
      <div class="diagnostic-item">
        <span>ADB 状态</span>
        <strong>{{ diagnostics.executable_found ? '已找到' : '未找到' }}</strong>
      </div>
      <div class="diagnostic-item">
        <span>版本信息</span>
        <strong>{{ diagnostics.version || '-' }}</strong>
      </div>
      <div class="diagnostic-item">
        <span>已发现设备</span>
        <strong>{{ diagnostics.device_count }}</strong>
      </div>
    </div>

    <div v-if="diagnostics.devices.length" class="device-section">
      <div class="section-title">在线设备</div>
      <a-space wrap>
        <a-tag v-for="device in diagnostics.devices" :key="device.device_id" color="blue">
          {{ device.name || device.device_id }} · {{ device.device_id }}
        </a-tag>
      </a-space>
    </div>

    <div v-else class="empty-text">当前没有发现在线设备。</div>

    <div v-if="diagnostics.error" class="diagnostic-error">
      {{ diagnostics.error }}
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { AppAdbDiagnostics } from '../../types'

interface Props {
  diagnostics: AppAdbDiagnostics
  statusColor: string
  statusLabel: string
  formatTime: (value: string) => string
}

defineProps<Props>()
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
.diagnostics-hint,
.empty-text {
  color: var(--color-text-2);
}

.diagnostics-hint,
.empty-text {
  margin: 0;
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
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

.diagnostic-item span,
.section-title {
  font-size: 12px;
  color: var(--color-text-3);
}

.diagnostic-item strong {
  color: var(--color-text-1);
  line-break: anywhere;
}

.device-section {
  margin-top: 16px;
}

.section-title {
  margin-bottom: 10px;
}

.diagnostic-error {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(var(--warning-6), 0.35);
  background: rgba(var(--warning-6), 0.08);
  color: rgb(var(--warning-6));
  line-height: 1.6;
}
</style>
