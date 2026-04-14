<template>
  <div class="page-header">
    <div>
      <h3>执行记录</h3>
      <p>集中查看 APP 自动化执行状态、进度、步骤结果和诊断日志，执行中的任务会自动刷新。</p>
    </div>
    <a-space>
      <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
      <a-button :loading="loading" @click="emit('refresh')">刷新</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
interface Props {
  loading: boolean
  lastUpdatedText: string
}

defineProps<Props>()

const emit = defineEmits<{
  refresh: []
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

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
