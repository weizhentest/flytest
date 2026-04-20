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

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
