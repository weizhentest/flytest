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
import type { AppTestSuite } from '../../types'

interface ExecutionFilters {
  search: string
  status: string
  suite: string
}

interface Props {
  filters: ExecutionFilters
  suites: AppTestSuite[]
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
  grid-template-columns: 1.6fr 180px 220px auto;
  gap: 12px;
  align-items: center;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
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
