import { computed, onMounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppAdbDiagnostics, AppRuntimeCapabilities, AppServiceHealth } from '../../types'
import type { SettingsFormModel } from './settingsViewModels'

export function useAppAutomationSettings() {
  const saving = ref(false)
  const detecting = ref(false)
  const diagnosticsLoading = ref(false)
  const runtimeLoading = ref(false)
  const serviceHealthLoading = ref(false)

  const form = reactive<SettingsFormModel>({
    adb_path: 'adb',
    default_timeout: 300,
    workspace_root: '',
    auto_discover_on_open: true,
    notes: '',
  })

  const diagnostics = reactive<AppAdbDiagnostics>({
    configured_path: '',
    resolved_path: '',
    executable_found: false,
    version: '',
    device_count: 0,
    devices: [],
    error: '',
    checked_at: '',
  })

  const runtimeCapabilities = reactive<AppRuntimeCapabilities>({
    checked_at: '',
    python_version: '',
    install_command: '',
    dependencies: [],
    capabilities: [],
  })

  const serviceHealth = reactive<AppServiceHealth>({
    service: '',
    status: '',
    version: '',
    checked_at: '',
    scheduler: {
      running: false,
      running_tasks: 0,
      poll_interval_seconds: 0,
    },
  })

  const statusLabel = computed(() => {
    if (diagnostics.executable_found && !diagnostics.error) {
      return 'ADB 可用'
    }
    if (diagnostics.executable_found) {
      return 'ADB 已找到'
    }
    return 'ADB 未就绪'
  })

  const statusColor = computed(() => {
    if (diagnostics.executable_found && !diagnostics.error) {
      return 'green'
    }
    if (diagnostics.executable_found) {
      return 'orange'
    }
    return 'red'
  })

  const installedDependencyCount = computed(() =>
    runtimeCapabilities.dependencies.filter(item => item.installed).length,
  )
  const readyCapabilityCount = computed(() =>
    runtimeCapabilities.capabilities.filter(item => item.ready).length,
  )

  const runtimeReady = computed(
    () =>
      runtimeCapabilities.capabilities.length > 0 &&
      runtimeCapabilities.capabilities.every(item => item.ready),
  )

  const overallStatusColor = computed(() => {
    if (serviceHealth.status !== 'ok' || !serviceHealth.scheduler.running) {
      return 'red'
    }
    if (diagnostics.executable_found && runtimeReady.value) {
      return 'green'
    }
    return 'orange'
  })

  const overallStatusLabel = computed(() => {
    if (serviceHealth.status !== 'ok') {
      return '服务异常'
    }
    if (!serviceHealth.scheduler.running) {
      return '调度器未运行'
    }
    if (diagnostics.executable_found && runtimeReady.value) {
      return '服务运行正常'
    }
    return '服务可用但依赖未就绪'
  })

  const formatTime = (value: string) => {
    if (!value) {
      return '-'
    }
    return value.replace('T', ' ').slice(0, 19)
  }

  const getErrorMessage = (error: any, fallback: string) => {
    return error?.error || error?.message || fallback
  }

  const loadSettings = async () => {
    try {
      Object.assign(form, await AppAutomationService.getSettings())
    } catch (error: any) {
      Message.error(getErrorMessage(error, '加载环境设置失败'))
    }
  }

  const loadDiagnostics = async (showMessage = false) => {
    diagnosticsLoading.value = true
    try {
      Object.assign(diagnostics, await AppAutomationService.getAdbDiagnostics())
      if (showMessage) {
        Message.success('ADB 诊断已刷新')
      }
    } catch (error: any) {
      Message.error(getErrorMessage(error, '获取 ADB 诊断失败'))
    } finally {
      diagnosticsLoading.value = false
    }
  }

  const loadRuntimeCapabilities = async (showMessage = false) => {
    runtimeLoading.value = true
    try {
      Object.assign(runtimeCapabilities, await AppAutomationService.getRuntimeCapabilities())
      if (showMessage) {
        Message.success('运行能力诊断已刷新')
      }
    } catch (error: any) {
      Message.error(getErrorMessage(error, '获取运行能力诊断失败'))
    } finally {
      runtimeLoading.value = false
    }
  }

  const loadServiceHealth = async (showMessage = false) => {
    serviceHealthLoading.value = true
    try {
      Object.assign(serviceHealth, await AppAutomationService.getHealthStatus())
      if (showMessage) {
        Message.success('服务状态已刷新')
      }
    } catch (error: any) {
      Message.error(getErrorMessage(error, '获取服务状态失败'))
    } finally {
      serviceHealthLoading.value = false
    }
  }

  const detectAdb = async () => {
    detecting.value = true
    try {
      const result = await AppAutomationService.detectAdb()
      Object.assign(form, result.settings)
      Object.assign(diagnostics, result.diagnostics)
      if (result.diagnostics.executable_found) {
        Message.success('已检测到可用 ADB，并同步到当前配置')
      } else {
        Message.warning(result.diagnostics.error || '未检测到可用 ADB')
      }
    } catch (error: any) {
      Message.error(getErrorMessage(error, '自动检测 ADB 失败'))
    } finally {
      detecting.value = false
    }
  }

  const reloadAll = async () => {
    await Promise.all([
      loadSettings(),
      loadDiagnostics(),
      loadRuntimeCapabilities(),
      loadServiceHealth(),
    ])
  }

  const save = async () => {
    saving.value = true
    try {
      await AppAutomationService.saveSettings(form)
      Message.success('环境设置已保存')
      await Promise.all([loadDiagnostics(), loadServiceHealth()])
    } catch (error: any) {
      Message.error(getErrorMessage(error, '保存环境设置失败'))
    } finally {
      saving.value = false
    }
  }

  onMounted(() => {
    void reloadAll()
  })

  return {
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
  }
}
