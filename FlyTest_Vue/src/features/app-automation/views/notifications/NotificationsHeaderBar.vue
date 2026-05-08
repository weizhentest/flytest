<template>
  <div class="page-header">
    <div>
      <h3>通知日志</h3>
      <p>查看 APP 自动化任务的通知投递结果、历史状态和关联执行上下文。</p>
    </div>
    <a-space>
      <a-button :loading="loading" @click="emit('refresh')">刷新</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { NotificationsHeaderBarEmits } from './notificationEventModels'
import type { NotificationsHeaderBarProps } from './notificationViewModels'

defineProps<NotificationsHeaderBarProps>()

const emit = defineEmits<NotificationsHeaderBarEmits>()
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

.page-header :deep(.arco-btn) {
  min-width: 92px;
  border-radius: 12px;
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 16px;
  }
}
</style>
