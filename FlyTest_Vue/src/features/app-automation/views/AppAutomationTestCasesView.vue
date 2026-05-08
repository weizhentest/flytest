<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再管理 APP 测试用例" />
    </div>
    <template v-else>
      <TestCasesHeaderBar
        v-model:search="search"
        v-model:package-filter="packageFilter"
        :packages="packages"
        @search="loadData"
        @reset="resetFilters"
        @quick-create="openCreate"
        @open-scene-builder-draft="openSceneBuilderDraft"
      />

      <TestCasesStatsGrid :statistics="caseStats" />

      <TestCasesBatchBar
        :selected-count="selectedCaseIds.length"
        @open-batch-execute="openBatchExecute"
        @clear-selection="clearSelection"
      />

      <TestCasesTableCard
        v-model:selected-case-ids="selectedCaseIds"
        :cases="filteredCases"
        :loading="loading"
        :format-date-time="formatDateTime"
        :get-step-count="getStepCount"
        :get-result-label="getResultLabel"
        :get-result-color="getResultColor"
        @open-execute="openExecute"
        @open-scene-builder="openSceneBuilder"
        @open-edit="openEdit"
        @duplicate-case="duplicateCase"
        @remove="remove"
      />

      <TestCasesRecentExecutionsCard
        :executions="recentExecutions"
        :loading="loading"
        :format-date-time="formatDateTime"
        :get-result-color="getResultColor"
        :get-execution-result-label="getExecutionResultLabel"
        :format-progress="formatProgress"
        :format-rate="formatRate"
        :can-open-execution-report="canOpenExecutionReport"
        @open-execution-workspace="openExecutionWorkspace"
        @open-execution-report="openExecutionReport"
      />

      <TestCaseEditorDialog
        v-model:visible="visible"
        :form="form"
        :packages="packages"
        @submit="submit"
      />

      <TestCaseExecuteDialog
        v-model:visible="executeVisible"
        :mode="executeMode"
        :execute-form="executeForm"
        :available-devices="availableDevices"
        :packages="packages"
        @execute="executeCase"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  TestCaseEditorDialog,
  TestCaseExecuteDialog,
  TestCasesBatchBar,
  TestCasesHeaderBar,
  TestCasesRecentExecutionsCard,
  TestCasesStatsGrid,
  TestCasesTableCard,
  useAppAutomationTestCases,
} from './test-cases'

const {
  projectStore,
  loading,
  visible,
  executeVisible,
  executeMode,
  search,
  packageFilter,
  packages,
  recentExecutions,
  selectedCaseIds,
  form,
  executeForm,
  availableDevices,
  filteredCases,
  caseStats,
  formatDateTime,
  getStepCount,
  getResultLabel,
  getResultColor,
  getExecutionResultLabel,
  formatRate,
  formatProgress,
  canOpenExecutionReport,
  loadData,
  resetFilters,
  openCreate,
  openSceneBuilderDraft,
  openEdit,
  submit,
  duplicateCase,
  openExecute,
  openSceneBuilder,
  openExecutionWorkspace,
  openExecutionReport,
  openBatchExecute,
  clearSelection,
  executeCase,
  remove,
} = useAppAutomationTestCases()
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
  min-height: 420px;
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
.page-shell :deep(.case-card),
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
