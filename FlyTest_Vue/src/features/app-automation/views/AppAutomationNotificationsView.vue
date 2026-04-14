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
      :retrying-id="retryingId"
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
      @retry="retry"
    />

    <NotificationDetailDialog
      v-model:visible="detailVisible"
      :current-log="currentLog"
      :retrying-id="retryingId"
      :parsed-content="parsedContent"
      :format-date-time="formatDateTime"
      :get-task-type-label="getTaskTypeLabel"
      :get-notification-type-label="getNotificationTypeLabel"
      :recipient-summary="recipientSummary"
      :get-primary-execution-id="getPrimaryExecutionId"
      @open-task-detail="openTaskDetail"
      @open-execution="openExecution"
      @retry="retry"
    />
  </div>
</template>

<script setup lang="ts">
import NotificationDetailDialog from './notifications/NotificationDetailDialog.vue'
import NotificationsFilterCard from './notifications/NotificationsFilterCard.vue'
import NotificationsHeaderBar from './notifications/NotificationsHeaderBar.vue'
import NotificationsStatsGrid from './notifications/NotificationsStatsGrid.vue'
import NotificationsTableCard from './notifications/NotificationsTableCard.vue'
import NotificationsTaskContextAlert from './notifications/NotificationsTaskContextAlert.vue'
import { useAppAutomationNotifications } from './notifications/useAppAutomationNotifications'

const {
  loading,
  retryingId,
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
  retry,
  viewDetail,
} = useAppAutomationNotifications()
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
