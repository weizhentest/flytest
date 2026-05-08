<template>
  <a-card class="panel-card task-card" title="定时任务快照">
    <template #extra>
      <a-button type="text" @click="emit('open-all')">查看全部</a-button>
    </template>

    <div v-if="tasks.length" class="task-list">
      <div v-for="task in tasks" :key="task.id" class="task-item">
        <div class="task-head">
          <div class="task-copy">
            <strong>{{ task.name }}</strong>
            <span>{{ getTaskTypeLabel(task.task_type) }} · {{ getTriggerSummary(task) }}</span>
            <small>{{ getTaskTarget(task) }}</small>
            <small>下次执行：{{ formatDateTime(task.next_run_time) }}</small>
          </div>
          <a-tag :color="getTaskStatusColor(task.status)">{{ task.status }}</a-tag>
        </div>
        <div class="task-actions">
          <a-button type="text" size="small" @click="emit('open-task', task)">详情</a-button>
          <a-button type="text" size="small" :loading="isTaskActionLoading('run', task.id)" @click="emit('run-task', task)">
            立即执行
          </a-button>
          <a-button
            v-if="task.status === 'PAUSED'"
            type="text"
            size="small"
            :loading="isTaskActionLoading('resume', task.id)"
            @click="emit('resume-task', task)"
          >
            恢复
          </a-button>
          <a-button v-if="getPrimaryExecutionId(task)" type="text" size="small" @click="emit('open-latest-execution', task)">
            最新执行
          </a-button>
        </div>
      </div>
    </div>
    <a-empty v-else description="当前项目还没有定时任务" />
  </a-card>
</template>

<script setup lang="ts">
import type { DashboardTaskSnapshotCardEmits } from './dashboardEventModels'
import type { DashboardTaskSnapshotCardProps } from './dashboardViewModels'

defineProps<DashboardTaskSnapshotCardProps>()

const emit = defineEmits<DashboardTaskSnapshotCardEmits>()
</script>

<style scoped>
.panel-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 18px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.task-item {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.14);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.03)),
    rgba(var(--theme-accent-rgb), 0.05);
}

.task-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.task-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-copy strong {
  color: var(--theme-text);
  font-size: 16px;
}

.task-copy span,
.task-copy small {
  margin: 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.task-copy small {
  font-size: 12px;
}

.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.task-actions :deep(.arco-btn-text),
.panel-card :deep(.arco-btn-text) {
  border-radius: 10px;
}

@media (max-width: 900px) {
  .task-head {
    flex-direction: column;
  }
}
</style>
