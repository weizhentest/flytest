import type { AppAdbDiagnostics, AppRuntimeCapabilities, AppServiceHealth } from '../../types'

export interface SettingsFormModel {
  adb_path: string
  default_timeout: number
  workspace_root: string
  auto_discover_on_open: boolean
  notes: string
}

export interface SettingsEnvironmentCardProps {
  form: SettingsFormModel
  saving: boolean
  detecting: boolean
  diagnosticsLoading: boolean
}

export interface SettingsServiceHealthCardProps {
  serviceHealth: AppServiceHealth
  diagnostics: AppAdbDiagnostics
  runtimeCapabilities: AppRuntimeCapabilities
  runtimeReady: boolean
  readyCapabilityCount: number
  workspaceRoot: string
  defaultTimeout: number
  overallStatusColor: string
  overallStatusLabel: string
  formatTime: (value: string) => string
  serviceHealthLoading: boolean
  diagnosticsLoading: boolean
  runtimeLoading: boolean
}

export interface SettingsAdbDiagnosticsCardProps {
  diagnostics: AppAdbDiagnostics
  statusColor: string
  statusLabel: string
  formatTime: (value: string) => string
}

export interface SettingsRuntimeCardProps {
  runtimeCapabilities: AppRuntimeCapabilities
  runtimeReady: boolean
  installedDependencyCount: number
  runtimeLoading: boolean
  formatTime: (value: string) => string
}
