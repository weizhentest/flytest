import { computed, ref, type Ref } from 'vue'
import { Message } from '@arco-design/web-vue'

import { apiRequestApi } from '../api'
import type { ApiImportAiCompatibility, ApiImportJob, ApiImportResult } from '../types'

type ImportProgressStatus = 'idle' | 'uploading' | 'processing' | 'success' | 'error'

type UseRequestImportFeedbackOptions = {
  projectId: Ref<number | undefined>
  activeImportJobs: Ref<ApiImportJob[]>
  cancelImportJob: (jobId: number) => Promise<ApiImportJob>
  registerFinishedHandler: (handler: (job: ApiImportJob) => void | Promise<void>) => () => void
  clearImportProgressTimer: () => void
  importProgressActive: Ref<boolean>
  importProgressStatus: Ref<ImportProgressStatus>
  importProgressMessage: Ref<string>
  importProgressError: Ref<string>
  saveDraftsFromImport: (result: ApiImportResult, projectId: number, collectionId?: number | null) => void
  clearRequestListCache: () => void
  loadRequests: (force?: boolean) => Promise<void>
  onUpdated: () => void
}

export function useRequestImportFeedback(options: UseRequestImportFeedbackOptions) {
  const importResult = ref<ApiImportResult | null>(null)
  const importResultVisible = ref(false)
  const importAiCompatibility = ref<ApiImportAiCompatibility | null>(null)
  const importAiCompatibilityLoading = ref(false)

  const importAiCompatibilityAlertType = computed(() => {
    if (!importAiCompatibility.value) return 'info'
    return importAiCompatibility.value.compatible ? 'success' : 'warning'
  })

  const importAiParseBlocked = computed(() => {
    if (!importAiCompatibility.value) return false
    return !importAiCompatibility.value.compatible
  })

  const importResultAlertTitle = computed(() => {
    if (!importResult.value) return ''
    if (importResult.value.ai_requested) {
      if (importResult.value.ai_used) return 'AI 文档解析已生效'
      if (importResult.value.ai_issue_code === 'gateway_incompatible_empty_content') {
        return '当前 AI 网关未返回正文，无法执行文档 AI 解析'
      }
      return 'AI 文档解析未成功完成'
    }
    return '本次未执行 AI 文档解析'
  })

  const importResultAlertMessage = computed(() => {
    if (!importResult.value) return ''
    return importResult.value.ai_user_message || importResult.value.ai_note || '本次导入未返回额外的 AI 解析说明。'
  })

  const importResultAlertActionHint = computed(() => {
    if (!importResult.value) return ''
    return importResult.value.ai_action_hint || ''
  })

  const currentImportJob = computed(() => {
    if (!options.projectId.value) return null
    return options.activeImportJobs.value.find(job => job.project === options.projectId.value) || null
  })

  const canCancelImportJob = (job: ApiImportJob) => {
    return (job.status === 'pending' || job.status === 'running') && !job.cancel_requested
  }

  const loadImportAiCompatibility = async () => {
    if (importAiCompatibilityLoading.value) return
    importAiCompatibilityLoading.value = true
    try {
      const res = await apiRequestApi.getImportAiCompatibility()
      importAiCompatibility.value = res.data?.data || null
    } catch (error: any) {
      console.error('[RequestList] 获取导入 AI 兼容性失败:', error)
      importAiCompatibility.value = {
        compatible: false,
        issue_code: 'probe_failed',
        level: 'warning',
        title: '兼容性检测失败',
        message: error?.error || '暂时无法确认当前 AI 配置是否兼容文档导入。',
        action_hint: '请先修正当前 AI 配置，或稍后重试兼容性检测。',
      }
    } finally {
      importAiCompatibilityLoading.value = false
    }
  }

  const handleCancelImportJob = async (job: ApiImportJob) => {
    try {
      await options.cancelImportJob(job.id)
      options.importProgressActive.value = true
      options.importProgressStatus.value = 'processing'
      options.importProgressMessage.value = '已发送停止解析请求，正在等待后台终止任务。'
      Message.success('已发送停止解析请求')
    } catch (error) {
      console.error('[RequestList] 停止解析失败:', error)
      Message.error('停止解析失败')
    }
  }

  const unregisterImportFinishedHandler = options.registerFinishedHandler(async job => {
    if (job.project !== options.projectId.value) return
    if (job.status === 'canceled') {
      options.clearImportProgressTimer()
      options.importProgressActive.value = true
      options.importProgressStatus.value = 'error'
      options.importProgressError.value = job.error_message || job.progress_message || '文档解析已手动停止'
      options.importProgressMessage.value = job.progress_message || '文档解析任务已取消'
      return
    }

    const result = job.result_payload
    if (!result) return

    importResult.value = result
    importResultVisible.value = true
    options.saveDraftsFromImport(result, options.projectId.value || job.project, job.collection)
    options.clearRequestListCache()
    await options.loadRequests(true)
    options.onUpdated()
  })

  return {
    importResult,
    importResultVisible,
    importAiCompatibility,
    importAiCompatibilityLoading,
    importAiCompatibilityAlertType,
    importAiParseBlocked,
    importResultAlertTitle,
    importResultAlertMessage,
    importResultAlertActionHint,
    currentImportJob,
    canCancelImportJob,
    loadImportAiCompatibility,
    handleCancelImportJob,
    unregisterImportFinishedHandler,
  }
}
