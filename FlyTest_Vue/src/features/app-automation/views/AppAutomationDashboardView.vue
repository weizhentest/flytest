<template>
  <div class="dashboard-view">
    <div v-if="!currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后查看 APP 自动化概览" />
    </div>
    <template v-else>
      <DashboardHeaderBar
        :service-status-tag-color="serviceStatusTagColor"
        :service-status-tag-text="serviceStatusTagText"
        :last-updated-text="lastUpdatedText"
        :ai-status-loading="aiStatusLoading"
        :loading="loading"
        @refresh-ai-status="refreshAiStatus(true)"
        @refresh-dashboard="loadDashboard"
      />

      <DashboardStatsGrid
        :statistics="statistics"
        :active-task-count="activeTaskCount"
        :paused-task-count="pausedTaskCount"
        :failed-task-count="failedTaskCount"
        :ai-ready="aiStatus.ready"
        :ai-has-config="aiStatus.hasConfig"
        :ai-capability-display="aiCapabilityDisplay"
      />

      <div class="content-grid">
        <DashboardExecutionSummaryCard :statistics="statistics" />
        <DashboardAiOverviewCard
          :ai-status-title="aiStatusTitle"
          :ai-status-description="aiStatusDescription"
          :ai-status-tag-color="aiStatusTagColor"
          :ai-status-tag-text="aiStatusTagText"
          :ai-config-display="aiConfigDisplay"
          :ai-provider-display="aiProviderDisplay"
          :ai-model-display="aiModelDisplay"
          :ai-capability-display="aiCapabilityDisplay"
          :ai-endpoint-display="aiEndpointDisplay"
          @open-scene-builder="openTab('scene-builder')"
          @open-llm-config="openLlmConfigManagement"
        />
      </div>

      <DashboardTaskSnapshotCard
        :tasks="taskSnapshot"
        :get-task-type-label="getTaskTypeLabel"
        :get-trigger-summary="getTriggerSummary"
        :get-task-target="getTaskTarget"
        :format-date-time="formatDateTime"
        :get-task-status-color="getTaskStatusColor"
        :get-primary-execution-id="getPrimaryExecutionId"
        :is-task-action-loading="isTaskActionLoading"
        @open-all="openTab('scheduled-tasks')"
        @open-task="openScheduledTask"
        @run-task="runTaskNow"
        @resume-task="resumeTask"
        @open-latest-execution="openLatestExecution"
      />

      <DashboardRecentExecutionsCard
        :executions="recentExecutions"
        :get-execution-status-color="getExecutionStatusColor"
        :get-execution-status-label="getExecutionStatusLabel"
        :format-progress="formatProgress"
        :format-date-time="formatDateTime"
        :can-open-report="canOpenReport"
        @open-all="openTab('executions')"
        @open-execution="openExecution"
        @open-report="openReport"
      />

      <DashboardQuickActionsCard @open-tab="openTab" />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  DashboardAiOverviewCard,
  DashboardExecutionSummaryCard,
  DashboardHeaderBar,
  DashboardQuickActionsCard,
  DashboardRecentExecutionsCard,
  DashboardStatsGrid,
  DashboardTaskSnapshotCard,
  useAppAutomationDashboard,
} from './dashboard'

const {
  currentProjectId,
  statistics,
  loading,
  aiStatusLoading,
  aiStatus,
  recentExecutions,
  activeTaskCount,
  pausedTaskCount,
  failedTaskCount,
  taskSnapshot,
  lastUpdatedText,
  serviceStatusTagColor,
  serviceStatusTagText,
  aiConfigDisplay,
  aiProviderDisplay,
  aiModelDisplay,
  aiEndpointDisplay,
  aiCapabilityDisplay,
  aiStatusTitle,
  aiStatusDescription,
  aiStatusTagColor,
  aiStatusTagText,
  getExecutionStatusColor,
  getExecutionStatusLabel,
  formatProgress,
  formatDateTime,
  canOpenReport,
  getTaskTypeLabel,
  getTaskTarget,
  getTaskStatusColor,
  getTriggerSummary,
  getPrimaryExecutionId,
  isTaskActionLoading,
  refreshAiStatus,
  loadDashboard,
  openTab,
  openExecution,
  openLatestExecution,
  openScheduledTask,
  openReport,
  openLlmConfigManagement,
  runTaskNow,
  resumeTask,
} = useAppAutomationDashboard()
</script>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
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

.content-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.4fr;
  gap: 16px;
}

@media (max-width: 1100px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
