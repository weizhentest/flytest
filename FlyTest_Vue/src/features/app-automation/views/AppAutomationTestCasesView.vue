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
