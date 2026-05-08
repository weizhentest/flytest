<template>
  <div class="page-header">
    <div>
      <h3>设备管理</h3>
      <p>统一管理本地模拟器、远程设备和真机，支持快速排查、锁定、截图和重连。</p>
    </div>
    <a-space wrap>
      <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
      <label class="auto-refresh-toggle">
        <span>30 秒自动刷新</span>
        <a-switch :model-value="autoRefreshEnabled" size="small" @change="emit('toggle-auto-refresh', $event)" />
      </label>
      <a-button @click="emit('open-connect')">添加远程设备</a-button>
      <a-button type="primary" :loading="loading" @click="emit('discover')">刷新设备</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { DevicesHeaderBarEmits } from './deviceEventModels'
import type { DevicesHeaderBarProps } from './deviceViewModels'

defineProps<DevicesHeaderBarProps>()

const emit = defineEmits<DevicesHeaderBarEmits>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
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

.header-tip {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.auto-refresh-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--theme-text-secondary);
  font-size: 13px;
  padding: 0 12px;
  min-height: 36px;
  border-radius: 999px;
  background: rgba(var(--theme-accent-rgb), 0.06);
}

.page-header :deep(.arco-btn) {
  min-width: 104px;
  border-radius: 12px;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 16px;
  }
}
</style>
