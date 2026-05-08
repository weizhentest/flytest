<template>
  <div class="page-shell">
    <DevicesHeaderBar
      :loading="loading"
      :auto-refresh-enabled="autoRefreshEnabled"
      :last-updated-text="lastUpdatedText"
      @toggle-auto-refresh="toggleAutoRefresh"
      @open-connect="showConnectModal = true"
      @discover="discover"
    />

    <DevicesStatsGrid :stats="stats" />

    <DevicesFilterCard
      :filters="filters"
      @search="handleSearch"
      @reset="resetFilters"
    />

    <DevicesTableCard
      :devices="devices"
      :loading="loading"
      :screenshot-loading-id="screenshotLoadingId"
      :format-date-time="formatDateTime"
      :get-status-label="getStatusLabel"
      :get-status-color="getStatusColor"
      :get-connection-label="getConnectionLabel"
      :format-endpoint="formatEndpoint"
      :can-lock="canLock"
      :can-unlock="canUnlock"
      :can-reconnect="canReconnect"
      :can-disconnect="canDisconnect"
      @open-detail="openDetail"
      @open-edit="openEdit"
      @preview-screenshot="previewScreenshot"
      @lock="lock"
      @unlock="unlock"
      @reconnect="reconnect"
      @disconnect="disconnect"
      @remove="remove"
    />

    <DeviceConnectDialog
      v-model:visible="showConnectModal"
      :connect-form="connectForm"
      @connect="connect"
    />

    <DeviceEditDialog
      v-model:visible="editVisible"
      :edit-form="editForm"
      :edit-saving="editSaving"
      @submit="submitEdit"
    />

    <DeviceDetailDialog
      v-model:visible="detailVisible"
      :current-device="currentDevice"
      :format-date-time="formatDateTime"
      :get-status-label="getStatusLabel"
      :get-connection-label="getConnectionLabel"
      :format-endpoint="formatEndpoint"
    />

    <DeviceScreenshotDialog
      v-model:visible="screenshotVisible"
      :current-screenshot="currentScreenshot"
      :format-timestamp="formatTimestamp"
    />
  </div>
</template>

<script setup lang="ts">
import {
  DeviceConnectDialog,
  DeviceDetailDialog,
  DeviceEditDialog,
  DeviceScreenshotDialog,
  DevicesFilterCard,
  DevicesHeaderBar,
  DevicesStatsGrid,
  DevicesTableCard,
  useAppAutomationDevices,
} from './devices'

const {
  loading,
  editSaving,
  autoRefreshEnabled,
  showConnectModal,
  screenshotVisible,
  screenshotLoadingId,
  detailVisible,
  editVisible,
  currentScreenshot,
  currentDevice,
  devices,
  filters,
  connectForm,
  editForm,
  stats,
  lastUpdatedText,
  formatDateTime,
  formatTimestamp,
  getStatusLabel,
  getStatusColor,
  getConnectionLabel,
  formatEndpoint,
  canLock,
  canUnlock,
  canReconnect,
  canDisconnect,
  handleSearch,
  resetFilters,
  discover,
  connect,
  openDetail,
  openEdit,
  submitEdit,
  lock,
  unlock,
  disconnect,
  reconnect,
  previewScreenshot,
  remove,
  toggleAutoRefresh,
} = useAppAutomationDevices()
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  padding: 8px 6px 10px;
}

.page-shell :deep(.arco-card),
.page-shell :deep(.device-card),
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
