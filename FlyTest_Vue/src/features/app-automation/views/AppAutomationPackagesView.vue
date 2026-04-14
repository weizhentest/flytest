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
import PackageEditorDialog from './packages/PackageEditorDialog.vue'
import PackagesFilterCard from './packages/PackagesFilterCard.vue'
import PackagesHeaderBar from './packages/PackagesHeaderBar.vue'
import PackagesStatsGrid from './packages/PackagesStatsGrid.vue'
import PackagesTableCard from './packages/PackagesTableCard.vue'
import { useAppAutomationPackages } from './packages/useAppAutomationPackages'

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
  gap: 16px;
}

.empty-shell {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}
</style>
