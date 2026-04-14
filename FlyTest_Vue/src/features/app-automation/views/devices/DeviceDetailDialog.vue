<template>
  <a-modal v-model:visible="visibleModel" title="设备详情" width="760px" :footer="false">
    <div v-if="currentDevice" class="detail-grid">
      <div class="detail-card">
        <span class="detail-label">设备名称</span>
        <strong>{{ currentDevice.name || currentDevice.device_id }}</strong>
      </div>
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
  </a-modal>
</template>

<script setup lang="ts">
import type { AppDevice } from '../../types'

interface Props {
  currentDevice: AppDevice | null
  formatDateTime: (value?: string | null) => string
  getStatusLabel: (status: string) => string
  getConnectionLabel: (connectionType: string) => string
  formatEndpoint: (record: AppDevice) => string
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
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
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(255, 255, 255, 0.03);
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
  font-size: 24px;
  line-height: 1.2;
}

@media (max-width: 1080px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
