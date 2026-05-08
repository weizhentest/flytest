<template>
  <a-card class="filter-card">
    <div class="filter-grid">
      <a-input-search
        v-model="filters.search"
        allow-clear
        placeholder="搜索用例、设备、触发人或执行摘要"
        @search="emit('search')"
      />
      <a-select v-model="filters.status" placeholder="执行状态" allow-clear>
        <a-option value="pending">等待执行</a-option>
        <a-option value="running">执行中</a-option>
        <a-option value="passed">执行通过</a-option>
        <a-option value="failed">执行失败</a-option>
        <a-option value="stopped">已停止</a-option>
      </a-select>
      <a-select v-model="filters.suite" placeholder="执行来源">
        <a-option value="all">全部来源</a-option>
        <a-option value="standalone">独立执行</a-option>
        <a-option v-for="suite in suites" :key="suite.id" :value="String(suite.id)">
          {{ suite.name }}
        </a-option>
      </a-select>
      <div class="filter-actions">
        <a-button @click="emit('reset')">重置</a-button>
        <a-button type="primary" @click="emit('search')">查询</a-button>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { ExecutionsFilterCardEmits } from './executionEventModels'
import type { ExecutionsFilterCardProps } from './executionViewModels'

defineProps<ExecutionsFilterCardProps>()

const emit = defineEmits<ExecutionsFilterCardEmits>()
</script>

<style scoped>
.filter-card {
  border-radius: 18px;
  border: 1px solid rgba(149, 161, 187, 0.14);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.06), transparent 22%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92));
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.05);
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.6fr 180px 220px auto;
  gap: 12px;
  align-items: center;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.filter-card :deep(.arco-card-body) {
  padding: 18px 20px;
}

.filter-card :deep(.arco-input-wrapper),
.filter-card :deep(.arco-select-view),
.filter-card :deep(.arco-btn) {
  border-radius: 10px;
}

@media (max-width: 1280px) {
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
