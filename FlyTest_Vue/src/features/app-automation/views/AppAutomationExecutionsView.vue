<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再查看 APP 自动化执行记录" />
    </div>
    <template v-else>
      <ExecutionsHeaderBar
        :loading="loading"
        :last-updated-text="lastUpdatedText"
        @refresh="loadData"
      />

      <ExecutionsFilterCard
        :filters="filters"
        :suites="suites"
        @search="handleSearch"
        @reset="resetFilters"
      />

      <ExecutionsStatsGrid :statistics="statistics" />

      <ExecutionsTableCard
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :loading="loading"
        :executions="pagedExecutions"
        :total="filteredExecutions.length"
        :stopping-ids="stoppingIds"
        :format-date-time="formatDateTime"
        :format-duration="formatDuration"
        :format-rate="formatRate"
        :format-progress="formatProgress"
        :get-execution-source="getExecutionSource"
        :get-execution-status-meta="getExecutionStatusMeta"
        :can-open-report="canOpenReport"
        :is-execution-running="isExecutionRunning"
        @view-detail="viewDetail"
        @open-report="openReport"
        @stop-execution="stopExecution"
      />

      <ExecutionsDetailDialog
        v-model:visible="detailVisible"
        :detail-loading="detailLoading"
        :current-execution="currentExecution"
        :execution-artifacts="executionArtifacts"
        :stopping-ids="stoppingIds"
        :format-date-time="formatDateTime"
        :format-duration="formatDuration"
        :format-rate="formatRate"
        :format-progress="formatProgress"
        :get-execution-source="getExecutionSource"
        :get-execution-status-meta="getExecutionStatusMeta"
        :get-log-level-color="getLogLevelColor"
        :can-open-report="canOpenReport"
        :is-execution-running="isExecutionRunning"
        @open-report="openReport"
        @stop-execution="stopExecution"
        @open-artifact="openExecutionArtifact"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  ExecutionsDetailDialog,
  ExecutionsFilterCard,
  ExecutionsHeaderBar,
  ExecutionsStatsGrid,
  ExecutionsTableCard,
  useAppAutomationExecutions,
} from './executions'

const {
  projectStore,
  loading,
  detailLoading,
  detailVisible,
  lastUpdatedText,
  suites,
  currentExecution,
  stoppingIds,
  filters,
  pagination,
  formatDateTime,
  formatDuration,
  formatRate,
  formatProgress,
  getExecutionStatusMeta,
  getExecutionSource,
  isExecutionRunning,
  canOpenReport,
  getLogLevelColor,
  filteredExecutions,
  pagedExecutions,
  statistics,
  executionArtifacts,
  loadData,
  handleSearch,
  resetFilters,
  viewDetail,
  openReport,
  openExecutionArtifact,
  stopExecution,
} = useAppAutomationExecutions()
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
  color: var(--theme-text-secondary);
}

.page-shell :deep(.arco-card),
.page-shell :deep(.execution-card),
.page-shell :deep(.stats-card) {
  border-radius: 20px;
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.05);
}

.page-shell :deep(.arco-card-header) {
  min-height: 58px;
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
