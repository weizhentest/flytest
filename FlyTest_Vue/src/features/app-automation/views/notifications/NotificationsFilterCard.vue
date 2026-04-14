<template>
  <a-card class="filter-card">
    <div class="filter-grid">
      <a-input-search
        v-model="filters.search"
        allow-clear
        placeholder="搜索任务名称、通知内容或错误信息"
        @search="emit('search')"
      />
      <a-select v-model="filters.status" allow-clear placeholder="发送状态">
        <a-option value="success">success</a-option>
        <a-option value="failed">failed</a-option>
        <a-option value="pending">pending</a-option>
      </a-select>
      <a-select v-model="filters.notification_type" allow-clear placeholder="通知类型">
        <a-option value="email">email</a-option>
        <a-option value="webhook">webhook</a-option>
        <a-option value="both">both</a-option>
      </a-select>
      <a-date-picker
        v-model="filters.start_date"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DD"
        placeholder="开始日期"
      />
      <a-date-picker
        v-model="filters.end_date"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DD"
        placeholder="结束日期"
      />
      <div class="filter-actions">
        <a-button @click="emit('reset')">重置</a-button>
        <a-button type="primary" @click="emit('search')">查询</a-button>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
interface NotificationFilters {
  search: string
  status: string
  notification_type: string
  start_date: string
  end_date: string
}

interface Props {
  filters: NotificationFilters
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
  grid-template-columns: minmax(240px, 1.4fr) 180px 180px 180px 180px auto;
  gap: 12px;
  align-items: center;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 1260px) {
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
