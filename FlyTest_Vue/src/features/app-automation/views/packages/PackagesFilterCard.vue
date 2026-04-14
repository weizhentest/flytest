<template>
  <a-card class="filter-card">
    <div class="filter-grid">
      <a-input-search
        v-model="searchModel"
        allow-clear
        placeholder="搜索应用名称、包名、Activity 或描述"
        @search="emit('search')"
      />
      <a-select v-model="platformFilterModel" allow-clear placeholder="全部平台">
        <a-option value="">全部平台</a-option>
        <a-option value="android">Android</a-option>
        <a-option value="ios">iOS</a-option>
      </a-select>
      <div class="filter-actions">
        <a-button @click="emit('reset')">重置</a-button>
        <a-button type="primary" @click="emit('search')">查询</a-button>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
const searchModel = defineModel<string>('search', { required: true })
const platformFilterModel = defineModel<string>('platformFilter', { required: true })

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
  grid-template-columns: minmax(260px, 1.6fr) 180px auto;
  gap: 12px;
  align-items: center;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 1200px) {
  .filter-grid {
    grid-template-columns: minmax(240px, 1fr) 180px;
  }

  .filter-actions {
    grid-column: 1 / -1;
  }
}

@media (max-width: 768px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
