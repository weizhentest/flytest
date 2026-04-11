import { ref } from 'vue'
import { Notification } from '@arco-design/web-vue'

import { caseGenerationJobApi } from '../api'
import type { ApiCaseGenerationJob } from '../types'

const trackedCaseGenerationJobIds = ref<number[]>([])
const activeCaseGenerationJobs = ref<ApiCaseGenerationJob[]>([])
const recentCaseGenerationJobs = ref<ApiCaseGenerationJob[]>([])

let currentProjectId: number | undefined

const getStorageKey = () => `flytest-api-case-generation-jobs:${currentProjectId || 'unknown'}`

const isRunningStatus = (status?: string) => ['pending', 'running', 'applying'].includes(String(status || ''))
const isTerminalStatus = (status?: string) =>
  ['success', 'failed', 'canceled', 'preview_ready'].includes(String(status || ''))

const persistTrackedJobIds = () => {
  localStorage.setItem(getStorageKey(), JSON.stringify(trackedCaseGenerationJobIds.value))
}

const loadTrackedJobIds = () => {
  try {
    const raw = localStorage.getItem(getStorageKey())
    trackedCaseGenerationJobIds.value = raw ? JSON.parse(raw) : []
  } catch {
    trackedCaseGenerationJobIds.value = []
  }
}

const syncProject = (projectId?: number) => {
  if (currentProjectId === projectId) return
  currentProjectId = projectId
  activeCaseGenerationJobs.value = []
  recentCaseGenerationJobs.value = []
  if (!projectId) {
    trackedCaseGenerationJobIds.value = []
    return
  }
  loadTrackedJobIds()
}

const rememberRecentJob = (job: ApiCaseGenerationJob) => {
  recentCaseGenerationJobs.value = [job, ...recentCaseGenerationJobs.value.filter(item => item.id !== job.id)].slice(0, 8)
}

const updateTrackedJob = (job: ApiCaseGenerationJob) => {
  if (isRunningStatus(job.status)) {
    if (!trackedCaseGenerationJobIds.value.includes(job.id)) {
      trackedCaseGenerationJobIds.value.push(job.id)
      persistTrackedJobIds()
    }
    activeCaseGenerationJobs.value = [job, ...activeCaseGenerationJobs.value.filter(item => item.id !== job.id)]
    return
  }

  trackedCaseGenerationJobIds.value = trackedCaseGenerationJobIds.value.filter(id => id !== job.id)
  persistTrackedJobIds()
  activeCaseGenerationJobs.value = activeCaseGenerationJobs.value.filter(item => item.id !== job.id)
  rememberRecentJob(job)
}

const createCaseGenerationJob = async (payload: {
  scope: 'selected' | 'collection' | 'project'
  ids?: number[]
  collection_id?: number
  project_id?: number
  mode: 'generate' | 'append' | 'regenerate'
  count_per_request?: number
}) => {
  const res = await caseGenerationJobApi.create(payload)
  const job = res.data.data
  updateTrackedJob(job)
  Notification.info({
    title: 'AI 用例生成已提交',
    content: job.progress_message || '后台正在生成测试用例，完成后会自动返回结果。',
  })
  return job
}

const cancelCaseGenerationJob = async (jobId: number) => {
  const res = await caseGenerationJobApi.cancel(jobId)
  const job = res.data.data
  updateTrackedJob(job)
  return job
}

const applyCaseGenerationJob = async (jobId: number) => {
  const res = await caseGenerationJobApi.apply(jobId)
  const job = res.data.data
  updateTrackedJob(job)
  return job
}

const sleep = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

const waitForCaseGenerationJob = async (
  jobId: number,
  options?: {
    intervalMs?: number
    timeoutMs?: number
  }
) => {
  const intervalMs = Math.max(800, options?.intervalMs || 1800)
  const timeoutMs = Math.max(10_000, options?.timeoutMs || 10 * 60 * 1000)
  const startedAt = Date.now()

  while (true) {
    const res = await caseGenerationJobApi.get(jobId)
    const job = res.data.data
    updateTrackedJob(job)
    if (isTerminalStatus(job.status)) {
      return job
    }
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error('AI 用例生成等待超时，请稍后再查看任务状态。')
    }
    await sleep(intervalMs)
  }
}

export const useApiCaseGenerationJobs = () => {
  return {
    trackedCaseGenerationJobIds,
    activeCaseGenerationJobs,
    recentCaseGenerationJobs,
    syncProject,
    createCaseGenerationJob,
    cancelCaseGenerationJob,
    applyCaseGenerationJob,
    waitForCaseGenerationJob,
  }
}
