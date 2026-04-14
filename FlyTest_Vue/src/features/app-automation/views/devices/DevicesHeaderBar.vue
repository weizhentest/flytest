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
interface Props {
  loading: boolean
  autoRefreshEnabled: boolean
  lastUpdatedText: string
}

defineProps<Props>()

const emit = defineEmits<{
  'toggle-auto-refresh': [value: string | number | boolean]
  'open-connect': []
  discover: []
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
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
}

.header-tip {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.auto-refresh-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
