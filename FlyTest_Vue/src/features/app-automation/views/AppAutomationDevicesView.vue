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
import DeviceConnectDialog from './devices/DeviceConnectDialog.vue'
import DeviceDetailDialog from './devices/DeviceDetailDialog.vue'
import DeviceEditDialog from './devices/DeviceEditDialog.vue'
import DevicesFilterCard from './devices/DevicesFilterCard.vue'
import DevicesHeaderBar from './devices/DevicesHeaderBar.vue'
import DeviceScreenshotDialog from './devices/DeviceScreenshotDialog.vue'
import DevicesStatsGrid from './devices/DevicesStatsGrid.vue'
import DevicesTableCard from './devices/DevicesTableCard.vue'
import { useAppAutomationDevices } from './devices/useAppAutomationDevices'

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
  gap: 16px;
}
</style>
