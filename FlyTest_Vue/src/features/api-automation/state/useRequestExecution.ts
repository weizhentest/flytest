import { Message } from '@arco-design/web-vue'
import { ref, type Ref } from 'vue'

import { apiRequestApi } from '../api'
import type { ApiExecutionBatchResult, ApiExecutionRecord, ApiRequest } from '../types'

type UseRequestExecutionOptions = {
  projectId: Ref<number | undefined>
  selectedEnvironmentId: Ref<number | undefined>
  ensureRequestDetail: (record: ApiRequest) => Promise<ApiRequest>
  requestToSnapshot: (detail: ApiRequest) => ApiExecutionRecord
  getErrorMessage: (error: unknown) => string
  setLoading?: (value: boolean) => void
  onExecuted?: () => void
}

export function useRequestExecution(options: UseRequestExecutionOptions) {
  const currentResult = ref<ApiExecutionRecord | null>(null)
  const resultVisible = ref(false)

  const stringifyBlock = (value: any) => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'string') return value
    return JSON.stringify(value, null, 2)
  }

  const formatDate = (value?: string) => {
    if (!value) return '-'
    return new Date(value).toLocaleString('zh-CN')
  }

  const formatDuration = (value?: number | null) => {
    if (value === null || value === undefined) return '-'
    return `${value.toFixed(2)} ms`
  }

  const showBatchExecutionMessage = (label: string, summary: ApiExecutionBatchResult) => {
    const text = `${label}完成：共 ${summary.total_count} 条，成功 ${summary.success_count} 条，断言失败 ${summary.failed_count} 条，异常 ${summary.error_count} 条。`
    if (summary.failed_count || summary.error_count) {
      Message.warning(text)
      return
    }
    Message.success(text)
  }

  const executeRequestBatch = async (payload: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    environment_id?: number
  }, label: string) => {
    try {
      const res = await apiRequestApi.executeBatch(payload)
      const summary = res.data.data
      showBatchExecutionMessage(label, summary)
      options.onExecuted?.()
    } catch (error: any) {
      console.error('[RequestList] 批量执行接口失败:', error)
      Message.error(error?.error || '批量执行接口失败')
    }
  }

  const executeRequest = async (record: ApiRequest) => {
    try {
      const res = await apiRequestApi.execute(record.id, options.selectedEnvironmentId.value)
      currentResult.value = res.data.data
      resultVisible.value = true
      if (currentResult.value.passed) {
        Message.success('接口执行通过')
      } else if (currentResult.value.status === 'error') {
        Message.error(currentResult.value.error_message || '接口执行失败，请检查环境变量或请求配置')
      } else {
        Message.warning('接口执行未通过，请检查断言或响应内容')
      }
      options.onExecuted?.()
    } catch (error: any) {
      console.error('[RequestList] 执行接口失败:', error)
      Message.error(error?.error || '执行接口失败')
    }
  }

  const viewRequest = async (record: ApiRequest) => {
    try {
      options.setLoading?.(true)
      const detail = await options.ensureRequestDetail(record)
      currentResult.value = options.requestToSnapshot(detail)
      resultVisible.value = true
    } catch (error) {
      console.error('[RequestList] 获取接口详情失败:', error)
      Message.error(options.getErrorMessage(error))
    } finally {
      options.setLoading?.(false)
    }
  }

  return {
    currentResult,
    resultVisible,
    stringifyBlock,
    formatDate,
    formatDuration,
    executeRequestBatch,
    executeRequest,
    viewRequest,
  }
}
