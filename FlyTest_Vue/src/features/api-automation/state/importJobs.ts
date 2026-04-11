import { ref } from 'vue'
import { Notification } from '@arco-design/web-vue'

import { importJobApi } from '../api'
import type { ApiImportJob } from '../types'

type FinishedHandler = (job: ApiImportJob) => void | Promise<void>

const trackedImportJobIds = ref<number[]>([])
const activeImportJobs = ref<ApiImportJob[]>([])
const recentImportJobs = ref<ApiImportJob[]>([])
const importTaskVisible = ref(false)

const finishHandlers = new Set<FinishedHandler>()
let importJobPollingTimer: ReturnType<typeof window.setInterval> | null = null
let currentProjectId: number | undefined

const getImportJobStorageKey = () => `flytest-api-import-jobs:${currentProjectId || 'unknown'}`

const persistTrackedImportJobs = () => {
  localStorage.setItem(getImportJobStorageKey(), JSON.stringify(trackedImportJobIds.value))
}

const loadTrackedImportJobs = () => {
  try {
    const raw = localStorage.getItem(getImportJobStorageKey())
    trackedImportJobIds.value = raw ? JSON.parse(raw) : []
  } catch {
    trackedImportJobIds.value = []
  }
}

const clearImportJobPolling = () => {
  if (importJobPollingTimer) {
    window.clearInterval(importJobPollingTimer)
    importJobPollingTimer = null
  }
}

const removeTrackedJob = (jobId: number) => {
  trackedImportJobIds.value = trackedImportJobIds.value.filter(id => id !== jobId)
  persistTrackedImportJobs()
}

const removeRecentImportJob = (jobId: number) => {
  recentImportJobs.value = recentImportJobs.value.filter(item => item.id !== jobId)
}

const upsertActiveImportJob = (job: ApiImportJob) => {
  activeImportJobs.value = [job, ...activeImportJobs.value.filter(item => item.id !== job.id)]
}

const rememberRecentImportJob = (job: ApiImportJob) => {
  recentImportJobs.value = [job, ...recentImportJobs.value.filter(item => item.id !== job.id)].slice(0, 8)
}

const notifyJobSuccess = (job: ApiImportJob) => {
  const result = job.result_payload
  Notification.success({
    title: '接口文档解析完成',
    content: result?.environment_auto_saved
      ? `已生成 ${result.created_count || 0} 个接口、${result.created_testcase_count || 0} 个测试用例，并自动创建环境“${result.environment_name}”。`
      : `已生成 ${result?.created_count || 0} 个接口和 ${result?.created_testcase_count || 0} 个测试用例。`,
  })
}

const notifyJobFailed = (job: ApiImportJob) => {
  Notification.error({
    title: '接口文档解析失败',
    content: job.error_message || job.progress_message || '后台解析任务失败，请稍后重试。',
  })
}

const notifyJobCanceled = (job: ApiImportJob) => {
  Notification.info({
    title: '接口文档解析已取消',
    content: job.progress_message || '后台解析任务已手动取消。',
  })
}

const emitFinished = async (job: ApiImportJob) => {
  for (const handler of finishHandlers) {
    await handler(job)
  }
}

const pollImportJobs = async () => {
  if (!trackedImportJobIds.value.length) {
    clearImportJobPolling()
    activeImportJobs.value = []
    return
  }

  const currentIds = [...trackedImportJobIds.value]
  const jobs = await Promise.all(
    currentIds.map(async jobId => {
      const res = await importJobApi.get(jobId)
      return res.data.data
    })
  )

  activeImportJobs.value = jobs
    .filter(job => job.status === 'pending' || job.status === 'running')
    .sort((a, b) => b.created_at.localeCompare(a.created_at))

  jobs
    .filter(job => job.status === 'success' || job.status === 'failed' || job.status === 'canceled')
    .forEach(job => rememberRecentImportJob(job))

  for (const job of jobs) {
    if (job.status === 'success') {
      removeTrackedJob(job.id)
      notifyJobSuccess(job)
      await emitFinished(job)
      continue
    }
    if (job.status === 'failed') {
      removeTrackedJob(job.id)
      notifyJobFailed(job)
      importTaskVisible.value = true
      await emitFinished(job)
      continue
    }
    if (job.status === 'canceled') {
      removeTrackedJob(job.id)
      notifyJobCanceled(job)
      importTaskVisible.value = true
      await emitFinished(job)
    }
  }

  if (!trackedImportJobIds.value.length) {
    clearImportJobPolling()
  }
}

const ensureImportJobPolling = () => {
  if (importJobPollingTimer || !trackedImportJobIds.value.length) return
  importJobPollingTimer = window.setInterval(() => {
    pollImportJobs().catch(error => {
      console.error('[ApiImportJobs] 轮询导入任务失败:', error)
    })
  }, 5000)
}

const syncProject = (projectId?: number) => {
  if (currentProjectId === projectId) return
  currentProjectId = projectId
  clearImportJobPolling()
  activeImportJobs.value = []
  recentImportJobs.value = []
  if (!projectId) {
    trackedImportJobIds.value = []
    return
  }
  loadTrackedImportJobs()
  ensureImportJobPolling()
  pollImportJobs().catch(() => undefined)
}

const trackImportJob = (job: ApiImportJob) => {
  if (!trackedImportJobIds.value.includes(job.id)) {
    trackedImportJobIds.value.push(job.id)
    persistTrackedImportJobs()
  }
  removeRecentImportJob(job.id)
  upsertActiveImportJob(job)
  ensureImportJobPolling()
}

const cancelImportJob = async (jobId: number) => {
  const res = await importJobApi.cancel(jobId)
  const job = res.data.data
  upsertActiveImportJob(job)
  if (job.status === 'canceled') {
    removeTrackedJob(job.id)
    rememberRecentImportJob(job)
  }
  return job
}

const restartImportJob = async (jobId: number) => {
  const res = await importJobApi.restart(jobId)
  const job = res.data.data
  removeRecentImportJob(job.id)
  trackImportJob(job)
  return job
}

const closeImportJob = async (jobId: number) => {
  await importJobApi.close(jobId)
  removeTrackedJob(jobId)
  removeRecentImportJob(jobId)
  activeImportJobs.value = activeImportJobs.value.filter(item => item.id !== jobId)
}

const registerFinishedHandler = (handler: FinishedHandler) => {
  finishHandlers.add(handler)
  return () => {
    finishHandlers.delete(handler)
  }
}

export const useApiImportJobs = () => {
  return {
    trackedImportJobIds,
    activeImportJobs,
    recentImportJobs,
    importTaskVisible,
    syncProject,
    trackImportJob,
    cancelImportJob,
    restartImportJob,
    closeImportJob,
    pollImportJobs,
    registerFinishedHandler,
    clearImportJobPolling,
  }
}
