<template>
  <a-card class="filter-card">
    <div class="filter-header">
      <div class="filter-header-copy">
        <span class="filter-kicker">Task Filter</span>
        <strong>快速定位调度任务</strong>
      </div>
      <span class="filter-summary">支持按任务类型、触发方式与状态组合筛选</span>
    </div>
    <div class="filter-grid">
      <a-input-search
        v-model="filters.search"
        allow-clear
        placeholder="搜索任务名称、描述或目标"
        @search="emit('search')"
      />
      <a-select v-model="filters.task_type" allow-clear placeholder="任务类型">
        <a-option value="TEST_SUITE">测试套件执行</a-option>
        <a-option value="TEST_CASE">测试用例执行</a-option>
      </a-select>
      <a-select v-model="filters.trigger_type" allow-clear placeholder="触发方式">
        <a-option value="CRON">CRON</a-option>
        <a-option value="INTERVAL">INTERVAL</a-option>
        <a-option value="ONCE">ONCE</a-option>
      </a-select>
      <a-select v-model="filters.status" allow-clear placeholder="任务状态">
        <a-option value="ACTIVE">ACTIVE</a-option>
        <a-option value="PAUSED">PAUSED</a-option>
        <a-option value="COMPLETED">COMPLETED</a-option>
        <a-option value="FAILED">FAILED</a-option>
      </a-select>
      <div class="filter-actions">
        <a-button @click="emit('reset')">重置</a-button>
        <a-button type="primary" @click="emit('search')">查询</a-button>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { ScheduledTaskFilterCardEmits } from './scheduledTaskEventModels'
import type { ScheduledTaskFilterCardProps } from './scheduledTaskViewModels'

defineProps<ScheduledTaskFilterCardProps>()

const emit = defineEmits<ScheduledTaskFilterCardEmits>()
</script>

<style scoped>
.filter-card {
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.filter-card :deep(.arco-card-body) {
  padding: 20px 22px 22px;
}

.filter-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.filter-header-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-kicker {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.filter-header-copy strong {
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.filter-summary {
  color: var(--theme-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.5fr repeat(3, minmax(140px, 180px)) auto;
  gap: 12px;
  align-items: center;
}

.filter-grid :deep(.arco-input-wrapper),
.filter-grid :deep(.arco-select-view),
.filter-grid :deep(.arco-picker) {
  border-radius: 12px;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.filter-actions :deep(.arco-btn) {
  min-width: 88px;
  border-radius: 12px;
}

@media (max-width: 1360px) {
  .filter-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-header {
    flex-direction: column;
  }

  .filter-actions {
    justify-content: flex-start;
  }
}
</style>
