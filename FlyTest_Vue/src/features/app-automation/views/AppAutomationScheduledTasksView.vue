<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请选择项目后再配置 APP 定时任务" />
    </div>
    <template v-else>
      <ScheduledTasksHeaderBar :loading="loading" @refresh="loadData" @create="openCreate" />

      <ScheduledTasksFilterCard :filters="filters" @search="handleSearch" @reset="resetFilters" />

      <ScheduledTasksStatsGrid :statistics="statistics" />

      <ScheduledTasksTableCard
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :loading="loading"
        :tasks="pagedTasks"
        :total="filteredTasks.length"
        :format-date-time="formatDateTime"
        :get-task-type-label="getTaskTypeLabel"
        :get-trigger-type-label="getTriggerTypeLabel"
        :get-notification-label="getNotificationLabel"
        :get-notification-color="getNotificationColor"
        :get-status-color="getStatusColor"
        :get-task-target="getTaskTarget"
        :get-package-label="getPackageLabel"
        :get-trigger-summary="getTriggerSummary"
        :get-notification-summary="getNotificationSummary"
        :get-last-result-meta="getLastResultMeta"
        :get-task-success-rate="getTaskSuccessRate"
        :get-last-result-summary="getLastResultSummary"
        :has-execution-result="hasExecutionResult"
        :is-action-loading="isActionLoading"
        @open-detail="openDetail"
        @run-now="runNow"
        @open-latest-execution="openLatestExecution"
        @open-edit="openEdit"
        @pause="pause"
        @resume="resume"
        @remove="remove"
      />

      <ScheduledTaskDetailDialog
        v-model:visible="detailVisible"
        :detail-loading="detailLoading"
        :task-notifications-loading="taskNotificationsLoading"
        :current-task="currentTask"
        :recent-task-notifications="recentTaskNotifications"
        :format-date-time="formatDateTime"
        :get-task-type-label="getTaskTypeLabel"
        :get-task-target="getTaskTarget"
        :get-notification-label="getNotificationLabel"
        :get-notification-color="getNotificationColor"
        :get-notification-status-color="getNotificationStatusColor"
        :get-last-result-meta="getLastResultMeta"
        :get-task-success-rate="getTaskSuccessRate"
        :get-last-result-summary="getLastResultSummary"
        :get-notification-detail="getNotificationDetail"
        :get-primary-execution-id-from-log="getPrimaryExecutionIdFromLog"
        :get-trigger-summary="getTriggerSummary"
        :get-notification-summary="getNotificationSummary"
        :has-execution-result="hasExecutionResult"
        :has-latest-report="hasLatestReport"
        @open-latest-execution="openLatestExecution"
        @open-latest-report="openLatestReport"
        @open-task-notifications="openTaskNotifications"
        @open-notification-execution="openNotificationExecution"
      />

      <ScheduledTaskFormDialog
        v-model:visible="visible"
        v-model:notify-emails-text="notifyEmailsText"
        :form="form"
        :devices="devices"
        :suites="suites"
        :test-cases="testCases"
        :packages="packages"
        :notifications-enabled="notificationsEnabled"
        :needs-email-recipients="needsEmailRecipients"
        @before-ok="handleBeforeOk"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  ScheduledTaskDetailDialog,
  ScheduledTaskFormDialog,
  ScheduledTasksFilterCard,
  ScheduledTasksHeaderBar,
  ScheduledTasksStatsGrid,
  ScheduledTasksTableCard,
  useAppAutomationScheduledTasks,
} from './scheduled-tasks'

const {
  projectStore,
  loading,
  visible,
  detailVisible,
  detailLoading,
  taskNotificationsLoading,
  notifyEmailsText,
  suites,
  testCases,
  devices,
  packages,
  currentTask,
  filters,
  pagination,
  form,
  notificationsEnabled,
  needsEmailRecipients,
  recentTaskNotifications,
  filteredTasks,
  pagedTasks,
  statistics,
  isActionLoading,
  formatDateTime,
  getTaskTypeLabel,
  getTriggerTypeLabel,
  getNotificationLabel,
  getNotificationColor,
  getStatusColor,
  getNotificationStatusColor,
  getTaskTarget,
  getPackageLabel,
  getTriggerSummary,
  getNotificationSummary,
  hasExecutionResult,
  hasLatestReport,
  getTaskSuccessRate,
  getLastResultMeta,
  getLastResultSummary,
  getNotificationDetail,
  getPrimaryExecutionIdFromLog,
  loadData,
  openCreate,
  openDetail,
  openEdit,
  handleSearch,
  resetFilters,
  handleBeforeOk,
  openLatestExecution,
  openLatestReport,
  openTaskNotifications,
  openNotificationExecution,
  runNow,
  pause,
  resume,
  remove,
} = useAppAutomationScheduledTasks()
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
