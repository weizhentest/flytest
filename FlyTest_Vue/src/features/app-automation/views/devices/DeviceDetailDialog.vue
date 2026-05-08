<template>
  <a-modal v-model:visible="visibleModel" title="设备详情" width="760px" :footer="false">
    <div v-if="currentDevice" class="detail-shell">
      <div class="detail-hero">
        <div class="detail-hero-copy">
          <span class="detail-kicker">Device Profile</span>
          <strong>{{ currentDevice.name || currentDevice.device_id }}</strong>
          <p>查看设备连接状态、在线情况与锁定信息，作为执行排期和环境调度的基础视图。</p>
        </div>
        <div class="detail-hero-metrics">
          <div class="detail-card">
            <span class="detail-label">当前状态</span>
            <strong>{{ getStatusLabel(currentDevice.status) }}</strong>
          </div>
          <div class="detail-card">
            <span class="detail-label">连接方式</span>
            <strong>{{ getConnectionLabel(currentDevice.connection_type) }}</strong>
          </div>
          <div class="detail-card">
            <span class="detail-label">Android 版本</span>
            <strong>{{ currentDevice.android_version || '-' }}</strong>
          </div>
        </div>
      </div>

      <div class="detail-grid">
        <div class="detail-panel">
          <span class="detail-label">序列号</span>
          <strong>{{ currentDevice.device_id }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">网络地址</span>
          <strong>{{ formatEndpoint(currentDevice) }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">锁定用户</span>
          <strong>{{ currentDevice.locked_by || '-' }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">锁定时间</span>
          <strong>{{ formatDateTime(currentDevice.locked_at) }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">位置</span>
          <strong>{{ currentDevice.location || '-' }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">最近在线</span>
          <strong>{{ formatDateTime(currentDevice.last_seen_at) }}</strong>
        </div>
        <div class="detail-panel detail-panel-wide">
          <span class="detail-label">备注</span>
          <strong>{{ currentDevice.description || '-' }}</strong>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { DeviceDetailDialogProps } from './deviceViewModels'

defineProps<DeviceDetailDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
.detail-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 16px;
}

.detail-hero-copy {
  padding: 20px 22px;
  border-radius: 20px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.12), rgba(var(--theme-accent-rgb), 0.04));
}

.detail-kicker {
  display: inline-block;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-hero-copy strong {
  display: block;
  color: var(--theme-text);
  font-size: 24px;
  line-height: 1.2;
}

.detail-hero-copy p {
  margin: 8px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.detail-hero-metrics {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.detail-card,
.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.detail-panel-wide {
  grid-column: 1 / -1;
}

.detail-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.detail-card strong,
.detail-panel strong {
  color: var(--theme-text);
  font-size: 20px;
  line-height: 1.2;
}

@media (max-width: 1080px) {
  .detail-hero,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
