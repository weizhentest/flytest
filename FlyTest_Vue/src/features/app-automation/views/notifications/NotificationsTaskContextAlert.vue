<template>
  <a-alert v-if="taskContext" type="info" class="context-alert">
    当前仅查看任务“{{ taskContext.name }}”的通知日志。
    <template #action>
      <a-space>
        <a-button size="mini" type="text" @click="emit('open-task-detail', taskContext.id)">查看任务</a-button>
        <a-button size="mini" type="text" @click="emit('clear-task-context')">清除筛选</a-button>
      </a-space>
    </template>
  </a-alert>
</template>

<script setup lang="ts">
import type { AppScheduledTask } from '../../types'

interface Props {
  taskContext: AppScheduledTask | null
}

defineProps<Props>()

const emit = defineEmits<{
  'open-task-detail': [taskId: number]
  'clear-task-context': []
}>()
</script>

<style scoped>
.context-alert {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}
</style>
