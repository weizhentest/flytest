<template>
  <a-modal v-model:visible="visibleModel" title="设备截图预览" width="980px" :footer="false">
    <div v-if="currentScreenshot" class="screenshot-shell">
      <div class="screenshot-header">
        <div class="screenshot-copy">
          <span class="screenshot-kicker">Live Capture</span>
          <strong>设备实时截图预览</strong>
        </div>
        <div class="screenshot-meta">
          <span>设备 ID：{{ currentScreenshot.device_id }}</span>
          <span>截图时间：{{ formatTimestamp(currentScreenshot.timestamp) }}</span>
        </div>
      </div>
      <div class="screenshot-frame">
        <img :src="currentScreenshot.content" alt="device screenshot" class="screenshot-image" />
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { DeviceScreenshotDialogProps } from './deviceViewModels'

defineProps<DeviceScreenshotDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
.screenshot-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.screenshot-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.1), rgba(var(--theme-accent-rgb), 0.04));
}

.screenshot-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.screenshot-kicker {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.screenshot-copy strong {
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.screenshot-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--theme-text-secondary);
  font-size: 13px;
  text-align: right;
}

.screenshot-frame {
  display: flex;
  justify-content: center;
  padding: 20px;
  border-radius: 20px;
  border: 1px solid var(--theme-card-border);
  background:
    radial-gradient(circle at top, rgba(var(--theme-accent-rgb), 0.08), transparent 48%),
    rgba(var(--theme-surface-rgb), 0.72);
  overflow: auto;
}

.screenshot-image {
  max-width: 100%;
  border-radius: 16px;
  box-shadow: 0 18px 40px rgba(18, 32, 61, 0.18);
}

@media (max-width: 900px) {
  .screenshot-header {
    flex-direction: column;
  }

  .screenshot-meta {
    text-align: left;
  }
}
</style>
