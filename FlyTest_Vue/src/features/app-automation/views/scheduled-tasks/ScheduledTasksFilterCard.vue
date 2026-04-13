<template>
  <a-card class="filter-card">
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
interface FiltersModel {
  search: string
  status: string
  task_type: string
  trigger_type: string
}

interface Props {
  filters: FiltersModel
}

defineProps<Props>()

const emit = defineEmits<{
  search: []
  reset: []
}>()
</script>

<style scoped>
.filter-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.5fr repeat(3, minmax(140px, 180px)) auto;
  gap: 12px;
  align-items: center;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
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

  .filter-actions {
    justify-content: flex-start;
  }
}
</style>
