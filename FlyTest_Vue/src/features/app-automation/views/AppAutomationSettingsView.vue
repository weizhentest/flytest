<template>
  <div class="page-shell">
    <section class="settings-hero">
      <div class="settings-hero__copy">
        <span class="settings-hero__eyebrow">Environment Setup</span>
        <h3>环境设置</h3>
        <p>统一管理 ADB、运行环境与自动化服务状态，让执行链路更稳定、排查更直接。</p>
      </div>
      <div class="settings-hero__meta">
        <div class="settings-meta-card">
          <span>运行能力</span>
          <strong>{{ readyCapabilityCount }}</strong>
        </div>
        <div class="settings-meta-card">
          <span>依赖组件</span>
          <strong>{{ installedDependencyCount }}</strong>
        </div>
      </div>
    </section>

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
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  padding: 8px 6px 10px;
}

.settings-hero {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.16), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 252, 0.94));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
}

.settings-hero__copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 720px;
}

.settings-hero__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--theme-accent);
}

.settings-hero__copy h3 {
  margin: 0;
  font-size: 28px;
  line-height: 1.08;
  color: var(--theme-text);
}

.settings-hero__copy p {
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--theme-text-secondary);
}

.settings-hero__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 12px;
  min-width: 280px;
}

.settings-meta-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(255, 255, 255, 0.74);
}

.settings-meta-card span {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.settings-meta-card strong {
  font-size: 26px;
  line-height: 1;
  color: var(--theme-text);
}

.settings-shell {
  display: grid;
  gap: 18px;
  max-width: 980px;
}

.page-shell :deep(.arco-card) {
  border-radius: 20px;
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.05);
}

.page-shell :deep(.arco-card-body) {
  padding: 20px;
}

@media (max-width: 768px) {
  .page-shell {
    gap: 16px;
    padding: 4px;
  }

  .settings-hero {
    flex-direction: column;
    padding: 20px;
    border-radius: 20px;
  }

  .settings-hero__copy h3 {
    font-size: 24px;
  }

  .settings-hero__meta {
    min-width: 0;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .settings-shell {
    max-width: 100%;
  }

  .page-shell :deep(.arco-card-body) {
    padding: 18px;
  }
}
</style>
