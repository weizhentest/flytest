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
import ExecutionsDetailDialog from './executions/ExecutionsDetailDialog.vue'
import ExecutionsFilterCard from './executions/ExecutionsFilterCard.vue'
import ExecutionsHeaderBar from './executions/ExecutionsHeaderBar.vue'
import ExecutionsStatsGrid from './executions/ExecutionsStatsGrid.vue'
import ExecutionsTableCard from './executions/ExecutionsTableCard.vue'
import { useAppAutomationExecutions } from './executions/useAppAutomationExecutions'

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
  gap: 16px;
}

.empty-shell {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
  color: var(--theme-text-secondary);
}
</style>
