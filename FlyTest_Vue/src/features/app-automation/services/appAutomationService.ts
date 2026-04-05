import { request } from '@/utils/request'
import type {
  AppAutomationSettings,
  AppComponent,
  AppComponentPackage,
  AppCustomComponent,
  AppDashboardStatistics,
  AppDevice,
  AppDeviceScreenshot,
  AppElement,
  AppExecution,
  AppImageCategory,
  AppNotificationLog,
  AppPackage,
  AppScheduledTask,
  AppTestCase,
  AppTestSuite,
} from '../types'

const APP_BASE = '/app-automation'
const APP_API_ROOT = (() => {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  const useProxy = import.meta.env.VITE_USE_PROXY === 'true' || import.meta.env.VITE_USE_PROXY === true

  if (useProxy) {
    return '/api'
  }

  if (envUrl && (envUrl.startsWith('http://') || envUrl.startsWith('https://'))) {
    return envUrl.replace(/\/$/, '')
  }

  return (envUrl || '/api').replace(/\/$/, '')
})()

async function unwrap<T>(config: Record<string, unknown>): Promise<T> {
  const response = await request<T>(config as never)
  if (response.success && response.data !== undefined) {
    return response.data
  }
  throw new Error(response.error || response.message || '请求失败')
}

export const AppAutomationService = {
  getDashboardStatistics(projectId?: number) {
    return unwrap<AppDashboardStatistics>({
      url: `${APP_BASE}/dashboard/statistics/`,
      method: 'GET',
      params: projectId ? { project_id: projectId } : undefined,
    })
  },

  getDevices(params?: { search?: string; status?: string }) {
    return unwrap<AppDevice[]>({
      url: `${APP_BASE}/devices/`,
      method: 'GET',
      params,
    })
  },

  captureDeviceScreenshot(id: number) {
    return unwrap<AppDeviceScreenshot>({
      url: `${APP_BASE}/devices/${id}/screenshot/`,
      method: 'POST',
    })
  },

  discoverDevices() {
    return unwrap<AppDevice[]>({
      url: `${APP_BASE}/devices/discover/`,
      method: 'GET',
    })
  },

  connectDevice(payload: { ip_address: string; port: number }) {
    return unwrap<AppDevice>({
      url: `${APP_BASE}/devices/connect/`,
      method: 'POST',
      data: payload,
    })
  },

  lockDevice(id: number, userName: string) {
    return unwrap<AppDevice>({
      url: `${APP_BASE}/devices/${id}/lock/`,
      method: 'POST',
      params: { user_name: userName },
    })
  },

  unlockDevice(id: number) {
    return unwrap<AppDevice>({
      url: `${APP_BASE}/devices/${id}/unlock/`,
      method: 'POST',
    })
  },

  disconnectDevice(id: number) {
    return unwrap<AppDevice>({
      url: `${APP_BASE}/devices/${id}/disconnect/`,
      method: 'POST',
    })
  },

  deleteDevice(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/devices/${id}/`,
      method: 'DELETE',
    })
  },

  getPackages(projectId: number, search?: string) {
    return unwrap<AppPackage[]>({
      url: `${APP_BASE}/packages/`,
      method: 'GET',
      params: { project_id: projectId, search },
    })
  },

  createPackage(payload: Omit<AppPackage, 'id' | 'updated_at'>) {
    return unwrap<AppPackage>({
      url: `${APP_BASE}/packages/`,
      method: 'POST',
      data: payload,
    })
  },

  updatePackage(id: number, payload: Omit<AppPackage, 'id' | 'updated_at'>) {
    return unwrap<AppPackage>({
      url: `${APP_BASE}/packages/${id}/`,
      method: 'PUT',
      data: payload,
    })
  },

  deletePackage(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/packages/${id}/`,
      method: 'DELETE',
    })
  },

  getElements(projectId: number, search?: string, elementType?: string) {
    return unwrap<AppElement[]>({
      url: `${APP_BASE}/elements/`,
      method: 'GET',
      params: { project_id: projectId, search, element_type: elementType },
    })
  },

  getElementPreviewUrl(id: number) {
    return `${APP_API_ROOT}${APP_BASE}/elements/${id}/preview/`
  },

  getElementAssetUrl(imagePath: string) {
    const normalized = String(imagePath || '')
      .replace(/^\/+/, '')
      .split('/')
      .map(segment => encodeURIComponent(segment))
      .join('/')
    return `${APP_API_ROOT}${APP_BASE}/elements/assets/${normalized}`
  },

  getElementImageCategories() {
    return unwrap<AppImageCategory[]>({
      url: `${APP_BASE}/elements/image-categories/`,
      method: 'GET',
    })
  },

  createElementImageCategory(name: string) {
    return unwrap<{ name: string }>({
      url: `${APP_BASE}/elements/image-categories/create/`,
      method: 'POST',
      data: { name },
    })
  },

  deleteElementImageCategory(name: string) {
    return unwrap<void>({
      url: `${APP_BASE}/elements/image-categories/${encodeURIComponent(name)}/`,
      method: 'DELETE',
    })
  },

  uploadElementAsset(file: File, projectId: number, category = 'common', elementId?: number) {
    const formData = new FormData()
    formData.append('file', file)

    return unwrap<{
      project_id: number
      image_path: string
      file_hash: string
      image_category: string
      duplicate: boolean
      url?: string
      existing_element?: { id: number; name: string; image_path: string }
    }>({
      url: `${APP_BASE}/elements/upload/`,
      method: 'POST',
      params: {
        project_id: projectId,
        category,
        element_id: elementId,
      },
      data: formData,
    })
  },

  createElement(payload: Omit<AppElement, 'id' | 'updated_at'>) {
    return unwrap<AppElement>({
      url: `${APP_BASE}/elements/`,
      method: 'POST',
      data: payload,
    })
  },

  updateElement(id: number, payload: Omit<AppElement, 'id' | 'updated_at'>) {
    return unwrap<AppElement>({
      url: `${APP_BASE}/elements/${id}/`,
      method: 'PUT',
      data: payload,
    })
  },

  deleteElement(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/elements/${id}/`,
      method: 'DELETE',
    })
  },

  getTestCases(projectId: number, search?: string) {
    return unwrap<AppTestCase[]>({
      url: `${APP_BASE}/test-cases/`,
      method: 'GET',
      params: { project_id: projectId, search },
    })
  },

  getTestCase(id: number) {
    return unwrap<AppTestCase>({
      url: `${APP_BASE}/test-cases/${id}/`,
      method: 'GET',
    })
  },

  createTestCase(payload: Omit<AppTestCase, 'id' | 'last_result' | 'last_run_at' | 'updated_at'>) {
    return unwrap<AppTestCase>({
      url: `${APP_BASE}/test-cases/`,
      method: 'POST',
      data: payload,
    })
  },

  updateTestCase(id: number, payload: Omit<AppTestCase, 'id' | 'last_result' | 'last_run_at' | 'updated_at'>) {
    return unwrap<AppTestCase>({
      url: `${APP_BASE}/test-cases/${id}/`,
      method: 'PUT',
      data: payload,
    })
  },

  deleteTestCase(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/test-cases/${id}/`,
      method: 'DELETE',
    })
  },

  executeTestCase(id: number, payload: { device_id: number; trigger_mode: string; triggered_by: string }) {
    return unwrap<AppExecution>({
      url: `${APP_BASE}/test-cases/${id}/execute/`,
      method: 'POST',
      data: payload,
    })
  },

  getExecutions(projectId: number, status?: string, search?: string, testSuiteId?: number) {
    return unwrap<AppExecution[]>({
      url: `${APP_BASE}/executions/`,
      method: 'GET',
      params: { project_id: projectId, status, search, test_suite_id: testSuiteId },
    })
  },

  getExecutionDetail(id: number) {
    return unwrap<AppExecution>({
      url: `${APP_BASE}/executions/${id}/`,
      method: 'GET',
    })
  },

  getExecutionReportUrl(id: number) {
    return `${APP_API_ROOT}${APP_BASE}/executions/${id}/report/`
  },

  stopExecution(id: number) {
    return unwrap<AppExecution>({
      url: `${APP_BASE}/executions/${id}/stop/`,
      method: 'POST',
    })
  },

  deleteExecution(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/executions/${id}/`,
      method: 'DELETE',
    })
  },

  getComponents() {
    return unwrap<AppComponent[]>({
      url: `${APP_BASE}/components/`,
      method: 'GET',
    })
  },

  createComponent(payload: Omit<AppComponent, 'id' | 'updated_at'>) {
    return unwrap<AppComponent>({
      url: `${APP_BASE}/components/`,
      method: 'POST',
      data: payload,
    })
  },

  getCustomComponents() {
    return unwrap<AppCustomComponent[]>({
      url: `${APP_BASE}/custom-components/`,
      method: 'GET',
    })
  },

  createCustomComponent(payload: Omit<AppCustomComponent, 'id' | 'updated_at'>) {
    return unwrap<AppCustomComponent>({
      url: `${APP_BASE}/custom-components/`,
      method: 'POST',
      data: payload,
    })
  },

  updateCustomComponent(id: number, payload: Omit<AppCustomComponent, 'id' | 'updated_at'>) {
    return unwrap<AppCustomComponent>({
      url: `${APP_BASE}/custom-components/${id}/`,
      method: 'PUT',
      data: payload,
    })
  },

  deleteCustomComponent(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/custom-components/${id}/`,
      method: 'DELETE',
    })
  },

  getComponentPackages() {
    return unwrap<AppComponentPackage[]>({
      url: `${APP_BASE}/component-packages/`,
      method: 'GET',
    })
  },

  createComponentPackage(payload: Omit<AppComponentPackage, 'id' | 'updated_at'>) {
    return unwrap<AppComponentPackage>({
      url: `${APP_BASE}/component-packages/`,
      method: 'POST',
      data: payload,
    })
  },

  deleteComponentPackage(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/component-packages/${id}/`,
      method: 'DELETE',
    })
  },

  getTestSuites(projectId: number, search?: string) {
    return unwrap<AppTestSuite[]>({
      url: `${APP_BASE}/test-suites/`,
      method: 'GET',
      params: { project_id: projectId, search },
    })
  },

  getTestSuite(id: number) {
    return unwrap<AppTestSuite>({
      url: `${APP_BASE}/test-suites/${id}/`,
      method: 'GET',
    })
  },

  createTestSuite(payload: { project_id: number; name: string; description: string; test_case_ids: number[] }) {
    return unwrap<AppTestSuite>({
      url: `${APP_BASE}/test-suites/`,
      method: 'POST',
      data: payload,
    })
  },

  updateTestSuite(id: number, payload: { project_id: number; name: string; description: string; test_case_ids: number[] }) {
    return unwrap<AppTestSuite>({
      url: `${APP_BASE}/test-suites/${id}/`,
      method: 'PUT',
      data: payload,
    })
  },

  deleteTestSuite(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/test-suites/${id}/`,
      method: 'DELETE',
    })
  },

  runTestSuite(id: number, payload: { device_id: number; package_name?: string; triggered_by: string }) {
    return unwrap<{ suite_id: number; execution_ids: number[]; test_case_count: number }>({
      url: `${APP_BASE}/test-suites/${id}/run/`,
      method: 'POST',
      data: payload,
    })
  },

  getTestSuiteExecutions(id: number) {
    return unwrap<AppExecution[]>({
      url: `${APP_BASE}/test-suites/${id}/executions/`,
      method: 'GET',
    })
  },

  getScheduledTasks(projectId: number, params?: { search?: string; status?: string; task_type?: string; trigger_type?: string }) {
    return unwrap<AppScheduledTask[]>({
      url: `${APP_BASE}/scheduled-tasks/`,
      method: 'GET',
      params: { project_id: projectId, ...params },
    })
  },

  getScheduledTask(id: number) {
    return unwrap<AppScheduledTask>({
      url: `${APP_BASE}/scheduled-tasks/${id}/`,
      method: 'GET',
    })
  },

  createScheduledTask(payload: Omit<AppScheduledTask, 'id' | 'device_name' | 'app_package_name' | 'test_suite_name' | 'test_case_name' | 'last_run_time' | 'next_run_time' | 'total_runs' | 'successful_runs' | 'failed_runs' | 'last_result' | 'error_message' | 'created_at' | 'updated_at'>) {
    return unwrap<AppScheduledTask>({
      url: `${APP_BASE}/scheduled-tasks/`,
      method: 'POST',
      data: payload,
    })
  },

  updateScheduledTask(id: number, payload: Omit<AppScheduledTask, 'id' | 'device_name' | 'app_package_name' | 'test_suite_name' | 'test_case_name' | 'last_run_time' | 'next_run_time' | 'total_runs' | 'successful_runs' | 'failed_runs' | 'last_result' | 'error_message' | 'created_at' | 'updated_at'>) {
    return unwrap<AppScheduledTask>({
      url: `${APP_BASE}/scheduled-tasks/${id}/`,
      method: 'PUT',
      data: payload,
    })
  },

  deleteScheduledTask(id: number) {
    return unwrap<void>({
      url: `${APP_BASE}/scheduled-tasks/${id}/`,
      method: 'DELETE',
    })
  },

  pauseScheduledTask(id: number) {
    return unwrap<AppScheduledTask>({
      url: `${APP_BASE}/scheduled-tasks/${id}/pause/`,
      method: 'POST',
    })
  },

  resumeScheduledTask(id: number) {
    return unwrap<AppScheduledTask>({
      url: `${APP_BASE}/scheduled-tasks/${id}/resume/`,
      method: 'POST',
    })
  },

  runScheduledTaskNow(id: number, triggeredBy: string) {
    return unwrap<AppScheduledTask>({
      url: `${APP_BASE}/scheduled-tasks/${id}/run_now/`,
      method: 'POST',
      params: { triggered_by: triggeredBy },
    })
  },

  getNotificationLogs(params?: { search?: string; status?: string; notification_type?: string }) {
    return unwrap<AppNotificationLog[]>({
      url: `${APP_BASE}/notification-logs/`,
      method: 'GET',
      params,
    })
  },

  retryNotification(id: number) {
    return unwrap<AppNotificationLog>({
      url: `${APP_BASE}/notification-logs/${id}/retry/`,
      method: 'POST',
    })
  },

  getSettings() {
    return unwrap<AppAutomationSettings>({
      url: `${APP_BASE}/settings/current/`,
      method: 'GET',
    })
  },

  saveSettings(payload: AppAutomationSettings) {
    return unwrap<AppAutomationSettings>({
      url: `${APP_BASE}/settings/save/`,
      method: 'POST',
      data: payload,
    })
  },
}
