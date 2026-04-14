<template>
  <a-card class="filter-card">
    <div class="filter-grid">
      <a-input-search
        v-model="filters.search"
        allow-clear
        placeholder="搜索设备名称或序列号"
        @search="emit('search')"
      />
      <a-select v-model="filters.status" allow-clear placeholder="筛选状态">
        <a-option value="">全部状态</a-option>
        <a-option value="available">可用</a-option>
        <a-option value="online">在线</a-option>
        <a-option value="locked">锁定</a-option>
        <a-option value="offline">离线</a-option>
      </a-select>
      <div class="filter-actions">
        <a-button @click="emit('reset')">重置</a-button>
        <a-button type="primary" @click="emit('search')">查询</a-button>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
interface DeviceFilters {
  search: string
  status: string
}

interface Props {
  filters: DeviceFilters
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
  grid-template-columns: minmax(260px, 2fr) minmax(180px, 1fr) auto;
  gap: 12px;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 1080px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    justify-content: flex-start;
  }
}
</style>
