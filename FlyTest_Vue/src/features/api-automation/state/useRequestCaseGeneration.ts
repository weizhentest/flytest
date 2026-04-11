import { h, type Ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'

import type { ApiCaseGenerationJob, ApiTestCaseGenerationResult } from '../types'

export type CaseGenerationMode = 'generate' | 'append' | 'regenerate'

export type CaseGenerationPayload = {
  scope: 'selected' | 'collection' | 'project'
  ids?: number[]
  collection_id?: number
  project_id?: number
  mode: CaseGenerationMode
  count_per_request?: number
  apply_changes?: boolean
}

type UseRequestCaseGenerationOptions = {
  createCaseGenerationJob: (payload: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    mode: CaseGenerationMode
    count_per_request?: number
  }) => Promise<ApiCaseGenerationJob>
  waitForCaseGenerationJob: (jobId: number) => Promise<ApiCaseGenerationJob>
  applyCaseGenerationJob: (jobId: number) => Promise<ApiCaseGenerationJob>
  clearRequestListCache: () => void
  loadRequests: (force?: boolean) => Promise<void>
  expandedRequestKeys: Ref<number[]>
  loadRequestTestCases: (requestId: number, force?: boolean) => Promise<void>
  onUpdated: () => void
}

export function useRequestCaseGeneration(options: UseRequestCaseGenerationOptions) {
  const showCaseGenerationMessage = (summary: ApiTestCaseGenerationResult, mode: CaseGenerationMode) => {
    const modeLabelMap: Record<CaseGenerationMode, string> = {
      generate: '生成',
      append: '追加生成',
      regenerate: '重新生成',
    }
    const cacheText = summary.ai_cache_hit_count ? ` 命中缓存 ${summary.ai_cache_hit_count} 个接口。` : ''
    const text = `${modeLabelMap[mode]}完成：处理 ${summary.processed_requests}/${summary.total_requests} 个接口，新增 ${summary.created_testcase_count} 条测试用例。${cacheText}`
    if (summary.skipped_requests) {
      Message.warning(`${text} 跳过 ${summary.skipped_requests} 个已有用例的接口。`)
      return
    }
    Message.success(text)
  }

  const formatCaseSummaryLine = (
    caseItem: NonNullable<ApiTestCaseGenerationResult['items'][number]['case_summaries']>[number]
  ) => {
    const detailParts = [
      caseItem.assertion_types.length ? `断言: ${caseItem.assertion_types.join(', ')}` : '断言: -',
      caseItem.extractor_variables.length ? `提取变量: ${caseItem.extractor_variables.join(', ')}` : '提取变量: -',
      caseItem.override_sections.length ? `覆盖字段: ${caseItem.override_sections.join(', ')}` : '覆盖字段: 无额外覆盖',
    ]
    return [`  - ${caseItem.name}`, `    ${detailParts.join(' | ')}`]
  }

  const buildCaseSummaryLines = (summary: ApiTestCaseGenerationResult) => {
    const lines: string[] = []
    summary.items.forEach(item => {
      if (item.skipped || !item.case_summaries?.length) return
      const header = `${item.request_name} (${item.request_method} ${item.request_url})`
      const metaParts = [
        item.ai_used ? 'AI生成' : '模板回退',
        item.ai_cache_hit ? '命中缓存' : null,
        item.ai_duration_ms ? `耗时 ${Math.round(item.ai_duration_ms)} ms` : null,
      ].filter(Boolean)
      lines.push(header)
      if (metaParts.length) lines.push(`  ${metaParts.join(' / ')}`)
      item.case_summaries.forEach(caseItem => {
        lines.push(...formatCaseSummaryLine(caseItem))
      })
    })
    return lines
  }

  const buildRegeneratePreviewLines = (summary: ApiTestCaseGenerationResult) => {
    const lines: string[] = []
    summary.items.forEach(item => {
      if (!item.preview_only) return
      const replacement = item.replacement_summary
      lines.push(`${item.request_name} (${item.request_method} ${item.request_url})`)
      lines.push(
        `  当前 ${replacement?.existing_count ?? item.existing_case_summaries?.length ?? 0} 条用例，候选 ${replacement?.proposed_count ?? item.proposed_case_summaries?.length ?? 0} 条用例`
      )
      if (replacement?.removed_case_names?.length) {
        lines.push(`  将移除: ${replacement.removed_case_names.join(', ')}`)
      }
      if (replacement?.added_case_names?.length) {
        lines.push(`  将新增: ${replacement.added_case_names.join(', ')}`)
      }
      if (replacement?.unchanged_case_names?.length) {
        lines.push(`  同名替换: ${replacement.unchanged_case_names.join(', ')}`)
      }
      if (item.existing_case_summaries?.length) {
        lines.push('  当前用例:')
        item.existing_case_summaries.forEach(caseItem => {
          lines.push(...formatCaseSummaryLine(caseItem).map(line => `  ${line}`))
        })
      }
      if (item.proposed_case_summaries?.length) {
        lines.push('  候选用例:')
        item.proposed_case_summaries.forEach(caseItem => {
          lines.push(...formatCaseSummaryLine(caseItem).map(line => `  ${line}`))
        })
      }
    })
    return lines
  }

  const showCaseGenerationInsight = (summary: ApiTestCaseGenerationResult, mode: CaseGenerationMode) => {
    const lines = buildCaseSummaryLines(summary)
    if (!lines.length) return
    const titleMap: Record<CaseGenerationMode, string> = {
      generate: 'AI生成结果',
      append: 'AI追加结果',
      regenerate: 'AI重新生成结果',
    }
    Modal.info({
      title: titleMap[mode],
      okText: '知道了',
      content: () =>
        h('div', { style: 'white-space: pre-wrap; line-height: 1.75; font-size: 13px;' }, lines.join('\n')),
    })
  }

  const confirmRegeneratePreview = (summary: ApiTestCaseGenerationResult) =>
    new Promise<boolean>(resolve => {
      const lines = buildRegeneratePreviewLines(summary)
      let settled = false
      const finish = (value: boolean) => {
        if (settled) return
        settled = true
        resolve(value)
      }
      Modal.confirm({
        title: 'AI重新生成预览',
        okText: '确认替换',
        cancelText: '取消',
        alignCenter: true,
        width: 980,
        maskClosable: false,
        content: () =>
          h(
            'div',
            {
              style:
                'white-space: pre-wrap; line-height: 1.75; font-size: 13px; max-height: 68vh; overflow-y: auto;',
            },
            lines.join('\n')
          ),
        onOk: () => finish(true),
        onCancel: () => finish(false),
      })
    })

  const ensureCaseGenerationSummary = (job: ApiCaseGenerationJob) => {
    if (job.result_payload) return job.result_payload
    throw new Error(job.error_message || 'AI 用例生成任务未返回结果')
  }

  const runCaseGenerationJob = async (payload: CaseGenerationPayload) => {
    const job = await options.createCaseGenerationJob({
      scope: payload.scope,
      ids: payload.ids,
      collection_id: payload.collection_id,
      project_id: payload.project_id,
      mode: payload.mode,
      count_per_request: payload.count_per_request,
    })

    let currentJob = await options.waitForCaseGenerationJob(job.id)
    if (currentJob.status === 'preview_ready' && payload.mode === 'regenerate') {
      const previewSummary = ensureCaseGenerationSummary(currentJob)
      const confirmed = await confirmRegeneratePreview(previewSummary)
      if (!confirmed) {
        Message.info('已取消替换当前测试用例')
        return null
      }
      await options.applyCaseGenerationJob(currentJob.id)
      currentJob = await options.waitForCaseGenerationJob(currentJob.id)
    }

    if (currentJob.status === 'failed') {
      throw new Error(currentJob.error_message || 'AI 用例生成失败')
    }
    if (currentJob.status === 'canceled') {
      Message.info(currentJob.progress_message || 'AI 用例生成已取消')
      return null
    }
    return ensureCaseGenerationSummary(currentJob)
  }

  const generateCasesByScope = async (payload: CaseGenerationPayload, targetRequestIds: number[] = []) => {
    try {
      const summary = await runCaseGenerationJob(payload)
      if (!summary) return
      showCaseGenerationMessage(summary, payload.mode)
      showCaseGenerationInsight(summary, payload.mode)
      options.clearRequestListCache()
      await options.loadRequests(true)
      const requestIdsToRefresh = targetRequestIds.length
        ? targetRequestIds
        : summary.items.map(item => item.request_id)
      for (const requestId of requestIdsToRefresh) {
        if (options.expandedRequestKeys.value.includes(requestId)) {
          await options.loadRequestTestCases(requestId, true)
        }
      }
      options.onUpdated()
    } catch (error: any) {
      console.error('[RequestList] AI 生成测试用例失败:', error)
      Message.error(error?.error || 'AI 生成测试用例失败')
    }
  }

  return {
    generateCasesByScope,
  }
}
