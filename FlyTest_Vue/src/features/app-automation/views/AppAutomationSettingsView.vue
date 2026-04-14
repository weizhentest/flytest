<template>
  <div class="settings-shell">
    <SettingsServiceHealthCard
      :service-health="serviceHealth"
      :diagnostics="diagnostics"
      :runtime-capabilities="runtimeCapabilities"
      :runtime-ready="runtimeReady"
      :ready-capability-count="readyCapabilityCount"
      :workspace-root="form.workspace_root"
      :default-timeout="form.default_timeout"
      :overall-status-color="overallStatusColor"
      :overall-status-label="overallStatusLabel"
      :format-time="formatTime"
      :service-health-loading="serviceHealthLoading"
      :diagnostics-loading="diagnosticsLoading"
      :runtime-loading="runtimeLoading"
      @refresh-service-health="loadServiceHealth(true)"
      @reload-all="reloadAll"
    />

    <SettingsEnvironmentCard
      :form="form"
      :saving="saving"
      :detecting="detecting"
      :diagnostics-loading="diagnosticsLoading"
      @reload-all="reloadAll"
      @refresh-diagnostics="loadDiagnostics(true)"
      @detect-adb="detectAdb"
      @save="save"
    />

    <SettingsAdbDiagnosticsCard
      :diagnostics="diagnostics"
      :status-color="statusColor"
      :status-label="statusLabel"
      :format-time="formatTime"
    />

    <SettingsRuntimeCard
      :runtime-capabilities="runtimeCapabilities"
      :runtime-ready="runtimeReady"
      :installed-dependency-count="installedDependencyCount"
      :runtime-loading="runtimeLoading"
      :format-time="formatTime"
      @refresh-runtime="loadRuntimeCapabilities(true)"
    />
  </div>
</template>

<script setup lang="ts">
import {
  SettingsAdbDiagnosticsCard,
  SettingsEnvironmentCard,
  SettingsRuntimeCard,
  SettingsServiceHealthCard,
  useAppAutomationSettings,
} from './settings'

const {
  saving,
  detecting,
  diagnosticsLoading,
  runtimeLoading,
  serviceHealthLoading,
  form,
  diagnostics,
  runtimeCapabilities,
  serviceHealth,
  statusLabel,
  statusColor,
  installedDependencyCount,
  readyCapabilityCount,
  runtimeReady,
  overallStatusColor,
  overallStatusLabel,
  formatTime,
  loadDiagnostics,
  loadRuntimeCapabilities,
  loadServiceHealth,
  detectAdb,
  reloadAll,
  save,
} = useAppAutomationSettings()
</script>

<style scoped>
.settings-shell {
  display: grid;
  gap: 16px;
  max-width: 920px;
}

@media (max-width: 768px) {
  .settings-shell {
    max-width: 100%;
  }
}
</style>
