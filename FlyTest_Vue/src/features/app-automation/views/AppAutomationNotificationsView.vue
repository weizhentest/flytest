<template>
  <div class="page-shell">
    <NotificationsHeaderBar :loading="loading" @refresh="loadData" />

    <NotificationsTaskContextAlert
      :task-context="taskContext"
      @open-task-detail="openTaskDetail"
      @clear-task-context="clearTaskContext"
    />

    <NotificationsFilterCard
      :filters="filters"
      @search="handleSearch"
      @reset="resetFilters"
    />

    <NotificationsStatsGrid :statistics="statistics" />

    <NotificationsTableCard
      v-model:current="pagination.current"
      v-model:page-size="pagination.pageSize"
      :loading="loading"
      :logs="pagedLogs"
      :total="filteredLogs.length"
      :format-date-time="formatDateTime"
      :get-task-type-label="getTaskTypeLabel"
      :get-notification-type-label="getNotificationTypeLabel"
      :get-notification-type-color="getNotificationTypeColor"
      :get-status-color="getStatusColor"
      :recipient-summary="recipientSummary"
      :get-delivery-summary="getDeliverySummary"
      :get-primary-execution-id="getPrimaryExecutionId"
      @view-detail="viewDetail"
      @open-task-detail="openTaskDetail"
      @open-execution="openExecution"
    />

    <NotificationDetailDialog
      v-model:visible="detailVisible"
      :current-log="currentLog"
      :retrying="retrying"
      :parsed-content="parsedContent"
      :format-date-time="formatDateTime"
      :get-task-type-label="getTaskTypeLabel"
      :get-notification-type-label="getNotificationTypeLabel"
      :recipient-summary="recipientSummary"
      :get-primary-execution-id="getPrimaryExecutionId"
      @open-task-detail="openTaskDetail"
      @open-execution="openExecution"
      @retry="retryNotification"
    />
  </div>
</template>

<script setup lang="ts">
import {
  NotificationDetailDialog,
  NotificationsFilterCard,
  NotificationsHeaderBar,
  NotificationsStatsGrid,
  NotificationsTableCard,
  NotificationsTaskContextAlert,
  useAppAutomationNotifications,
} from './notifications'

const {
  loading,
  retrying,
  detailVisible,
  currentLog,
  taskContext,
  filters,
  pagination,
  filteredLogs,
  pagedLogs,
  statistics,
  parsedContent,
  formatDateTime,
  getTaskTypeLabel,
  getNotificationTypeLabel,
  getNotificationTypeColor,
  getStatusColor,
  getPrimaryExecutionId,
  getDeliverySummary,
  recipientSummary,
  loadData,
  handleSearch,
  resetFilters,
  openTaskDetail,
  clearTaskContext,
  openExecution,
  viewDetail,
  retryNotification,
} = useAppAutomationNotifications()
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
