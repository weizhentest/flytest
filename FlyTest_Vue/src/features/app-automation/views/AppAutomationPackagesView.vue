<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后管理 APP 应用包" />
    </div>
    <template v-else>
      <PackagesHeaderBar
        :loading="loading"
        @refresh="loadPackages"
        @create="openCreate"
      />

      <PackagesStatsGrid :stats="packageStats" />

      <PackagesFilterCard
        v-model:search="search"
        v-model:platform-filter="platformFilter"
        @search="handleSearch"
        @reset="resetFilters"
      />

      <PackagesTableCard
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :packages="pagedPackages"
        :loading="loading"
        :total="filteredPackages.length"
        :format-date-time="formatDateTime"
        :get-platform-label="getPlatformLabel"
        :get-platform-color="getPlatformColor"
        @open-edit="openEdit"
        @remove="remove"
      />

      <PackageEditorDialog
        v-model:visible="visible"
        :form="form"
        :submitting="submitting"
        @submit="submit"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  PackageEditorDialog,
  PackagesFilterCard,
  PackagesHeaderBar,
  PackagesStatsGrid,
  PackagesTableCard,
  useAppAutomationPackages,
} from './packages'

const {
  projectStore,
  loading,
  submitting,
  visible,
  search,
  platformFilter,
  pagination,
  form,
  filteredPackages,
  pagedPackages,
  packageStats,
  formatDateTime,
  getPlatformLabel,
  getPlatformColor,
  loadPackages,
  handleSearch,
  resetFilters,
  openCreate,
  openEdit,
  submit,
  remove,
} = useAppAutomationPackages()
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  padding: 8px 6px 10px;
}

.empty-shell {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.06), transparent 24%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(246, 249, 253, 0.9));
  border: 1px solid var(--theme-card-border);
  border-radius: 24px;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
}

.page-shell :deep(.arco-card),
.page-shell :deep(.package-card),
.page-shell :deep(.stats-card) {
  border-radius: 20px;
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.05);
}

.page-shell :deep(.arco-card-body) {
  padding: 20px;
}

@media (max-width: 900px) {
  .page-shell {
    gap: 16px;
    padding: 4px;
  }

  .page-shell :deep(.arco-card-body) {
    padding: 18px;
  }
}
</style>
