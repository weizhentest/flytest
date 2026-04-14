<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再查看 APP 自动化执行报告" />
    </div>
    <template v-else>
      <ReportsHeaderBar
        :loading="loading"
        :last-updated-text="lastUpdatedText"
        @refresh="loadData"
      />

      <a-tabs v-model:active-key="activeTab">
        <a-tab-pane key="suite" title="套件报告">
          <ReportsSuitePanel
            :loading="loading"
            :filters="suiteFilters"
            :pagination="suitePagination"
            :statistics="suiteStats"
            :suites="pagedSuites"
            :total="filteredSuites.length"
            :format-date-time="formatDateTime"
            :get-suite-status="getSuiteStatus"
            :get-suite-health-rate="getSuiteHealthRate"
            @search="handleSuiteSearch"
            @reset="resetSuiteFilters"
            @open-detail="openSuiteDetail"
            @open-executions="openSuiteExecutions"
            @open-report="openSuiteReport"
          />
        </a-tab-pane>

        <a-tab-pane key="case" title="执行明细">
          <ReportsExecutionPanel
            :loading="loading"
            :filters="caseFilters"
            :pagination="casePagination"
            :statistics="caseStats"
            :executions="pagedExecutions"
            :total="filteredExecutions.length"
            :format-date-time="formatDateTime"
            :format-rate="formatRate"
            :format-duration="formatDuration"
            :get-execution-source="getExecutionSource"
            :get-execution-status="getExecutionStatus"
            :can-open-report="canOpenReport"
            @search="handleCaseSearch"
            @reset="resetCaseFilters"
            @open-detail="openExecutionDetail"
            @open-report="openExecutionReport"
          />
        </a-tab-pane>
      </a-tabs>

      <ReportsSuiteDetailDialog
        v-model:visible="suiteDetailVisible"
        :selected-suite="selectedSuite"
        :format-date-time="formatDateTime"
        :get-suite-status="getSuiteStatus"
        :get-suite-health-rate="getSuiteHealthRate"
      />

      <ReportsSuiteExecutionsDialog
        v-model:visible="suiteExecutionsVisible"
        :selected-suite="selectedSuite"
        :suite-executions="suiteExecutions"
        :loading="suiteExecutionsLoading"
        :format-rate="formatRate"
        :get-execution-status="getExecutionStatus"
        :can-open-report="canOpenReport"
        @open-detail="openExecutionDetail"
        @open-report="openExecutionReport"
      />

      <ReportsExecutionDetailDialog
        v-model:visible="executionDetailVisible"
        :current-execution="currentExecution"
        :execution-artifacts="executionArtifacts"
        :execution-log-text="executionLogText"
        :format-date-time="formatDateTime"
        :format-rate="formatRate"
        :format-duration="formatDuration"
        :get-execution-status="getExecutionStatus"
        :get-execution-source="getExecutionSource"
        :can-open-report="canOpenReport"
        @open-report="openExecutionReport"
        @open-artifact="openExecutionArtifact"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  ReportsExecutionDetailDialog,
  ReportsExecutionPanel,
  ReportsHeaderBar,
  ReportsSuiteDetailDialog,
  ReportsSuiteExecutionsDialog,
  ReportsSuitePanel,
  useAppAutomationReports,
} from './reports'

const {
  projectStore,
  activeTab,
  loading,
  selectedSuite,
  suiteExecutions,
  suiteExecutionsVisible,
  suiteExecutionsLoading,
  suiteDetailVisible,
  executionDetailVisible,
  currentExecution,
  suiteFilters,
  caseFilters,
  suitePagination,
  casePagination,
  formatDateTime,
  formatRate,
  formatDuration,
  getSuiteStatus,
  getExecutionStatus,
  getSuiteHealthRate,
  getExecutionSource,
  canOpenReport,
  filteredSuites,
  filteredExecutions,
  pagedSuites,
  pagedExecutions,
  suiteStats,
  caseStats,
  lastUpdatedText,
  executionArtifacts,
  executionLogText,
  loadData,
  handleSuiteSearch,
  handleCaseSearch,
  resetSuiteFilters,
  resetCaseFilters,
  openSuiteDetail,
  openSuiteExecutions,
  openExecutionDetail,
  openExecutionReport,
  openExecutionArtifact,
  openSuiteReport,
} = useAppAutomationReports()
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
  color: var(--theme-text-secondary);
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}
</style>
