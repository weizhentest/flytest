<template>
  <a-modal v-model:visible="visibleModel" title="设备截图" width="980px" :footer="false">
    <div v-if="currentScreenshot" class="screenshot-shell">
      <div class="screenshot-meta">
        <span>设备：{{ currentScreenshot.device_id }}</span>
        <span>时间：{{ formatTimestamp(currentScreenshot.timestamp) }}</span>
      </div>
      <div class="screenshot-frame">
        <img :src="currentScreenshot.content" alt="device screenshot" class="screenshot-image" />
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { AppDeviceScreenshot } from '../../types'

interface Props {
  currentScreenshot: AppDeviceScreenshot | null
  formatTimestamp: (timestamp?: number) => string
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
.screenshot-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.screenshot-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.screenshot-frame {
  display: flex;
  justify-content: center;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: rgba(255, 255, 255, 0.03);
  overflow: auto;
}

.screenshot-image {
  max-width: 100%;
  border-radius: 16px;
  box-shadow: 0 18px 40px rgba(18, 32, 61, 0.18);
}
</style>
