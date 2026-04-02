<template>
  <div v-if="record" class="detail-panel">
    <a-descriptions :column="2" bordered size="small">
      <a-descriptions-item label="执行批次">{{ record.run_name || '-' }}</a-descriptions-item>
      <a-descriptions-item label="接口名称">{{ record.interface_name || record.request_name }}</a-descriptions-item>
      <a-descriptions-item label="测试用例">{{ record.test_case_name || '接口直接执行' }}</a-descriptions-item>
      <a-descriptions-item label="执行状态">
        <a-tag :color="getStatusTag(record).color">
          {{ getStatusTag(record).label }}
        </a-tag>
      </a-descriptions-item>
      <a-descriptions-item label="状态码">{{ record.status_code ?? '-' }}</a-descriptions-item>
      <a-descriptions-item label="响应时间">{{ formatDuration(record.response_time) }}</a-descriptions-item>
      <a-descriptions-item label="执行环境">{{ record.environment_name || '-' }}</a-descriptions-item>
      <a-descriptions-item label="执行人">{{ record.executor_name || '-' }}</a-descriptions-item>
      <a-descriptions-item label="最终地址" :span="2">{{ record.url }}</a-descriptions-item>
      <a-descriptions-item label="错误信息" :span="2">{{ record.error_message || '-' }}</a-descriptions-item>
    </a-descriptions>

    <template v-if="canAnalyzeFailure">
      <a-divider>AI 失败复盘</a-divider>

      <div class="ai-analysis-toolbar">
        <a-button type="primary" size="small" :loading="analysisLoading" @click="loadFailureAnalysis">
          {{ failureAnalysis ? '重新获取复盘建议' : '生成 AI 复盘建议' }}
        </a-button>
        <span v-if="failureAnalysis" class="ai-analysis-toolbar__meta">
          {{ failureAnalysis.used_ai ? 'AI 复盘' : '规则复盘' }}
          <template v-if="failureAnalysis.cache_hit"> / 命中缓存</template>
          <template v-if="failureAnalysis.duration_ms"> / {{ Math.round(failureAnalysis.duration_ms) }} ms</template>
        </span>
      </div>

      <a-alert v-if="analysisError" type="error" :show-icon="true">{{ analysisError }}</a-alert>

      <template v-if="failureAnalysis">
        <div class="ai-summary-card">
          <div class="ai-summary-card__label">复盘结论</div>
          <div class="ai-summary-card__value">{{ failureAnalysis.summary || '暂无复盘结论' }}</div>
          <div class="ai-summary-card__meta">
            <a-tag size="small" color="arcoblue">{{ failureAnalysis.failure_mode || 'unknown_failure' }}</a-tag>
            <span>{{ failureAnalysis.note }}</span>
          </div>
        </div>

        <div class="ai-grid">
          <div class="ai-card">
            <div class="ai-card__title">可能根因</div>
            <div v-if="failureAnalysis.likely_root_causes.length" class="ai-list">
              <article v-for="(item, index) in failureAnalysis.likely_root_causes" :key="`${item.title}-${index}`" class="ai-list-item">
                <div class="ai-list-item__title">
                  {{ item.title }}
                  <span v-if="item.confidence !== null && item.confidence !== undefined" class="ai-list-item__meta">
                    置信度 {{ Math.round(item.confidence * 100) }}%
                  </span>
                </div>
                <div class="ai-list-item__detail">{{ item.detail }}</div>
              </article>
            </div>
            <a-empty v-else description="暂无根因建议" />
          </div>

          <div class="ai-card">
            <div class="ai-card__title">建议动作</div>
            <div v-if="failureAnalysis.recommended_actions.length" class="ai-list">
              <article v-for="(item, index) in failureAnalysis.recommended_actions" :key="`${item.title}-${index}`" class="ai-list-item">
                <div class="ai-list-item__title">
                  {{ item.title }}
                  <a-tag size="small" :color="getPriorityTagColor(item.priority)">{{ item.priority }}</a-tag>
                </div>
                <div class="ai-list-item__detail">{{ item.detail }}</div>
              </article>
            </div>
            <a-empty v-else description="暂无动作建议" />
          </div>
        </div>

        <div class="ai-grid">
          <div class="ai-card">
            <div class="ai-card__title">关键证据</div>
            <div v-if="failureAnalysis.evidence.length" class="ai-list">
              <article v-for="(item, index) in failureAnalysis.evidence" :key="`${item.label}-${index}`" class="ai-list-item">
                <div class="ai-list-item__title">{{ item.label }}</div>
                <div class="ai-list-item__detail">{{ item.detail }}</div>
              </article>
            </div>
            <a-empty v-else description="暂无证据摘要" />
          </div>

          <div class="ai-card">
            <div class="ai-card__title">最近相似失败</div>
            <div v-if="failureAnalysis.recent_failures.length" class="ai-list">
              <article v-for="item in failureAnalysis.recent_failures" :key="item.id" class="ai-list-item">
                <div class="ai-list-item__title">
                  记录 #{{ item.id }}
                  <span class="ai-list-item__meta">{{ formatFailureDate(item.created_at) }}</span>
                </div>
                <div class="ai-list-item__detail">
                  {{ item.status }} / 状态码 {{ item.status_code ?? '-' }} / 耗时 {{ formatDuration(item.response_time) }}
                </div>
                <div v-if="item.error_message" class="ai-list-item__detail">{{ item.error_message }}</div>
              </article>
            </div>
            <a-empty v-else description="暂无相似失败历史" />
          </div>
        </div>
      </template>
    </template>

    <template v-if="showWorkflowSection">
      <a-divider>工作流执行</a-divider>

      <div class="workflow-summary-grid">
        <div class="workflow-summary-card workflow-summary-card--primary">
          <div class="workflow-summary-card__label">执行概况</div>
          <div class="workflow-summary-card__value">
            {{ workflowSummary?.executed_step_count || workflowSteps.length }} / {{ workflowSummary?.configured_step_count || workflowSteps.length }}
          </div>
          <div class="workflow-summary-card__meta">已执行步骤 / 配置步骤</div>
        </div>
        <div class="workflow-summary-card">
          <div class="workflow-summary-card__label">失败步骤</div>
          <div class="workflow-summary-card__value">{{ workflowSummary?.failure_count || 0 }}</div>
          <div class="workflow-summary-card__meta">{{ workflowSummary?.has_failure ? '存在工作流失败' : '工作流全部成功' }}</div>
        </div>
        <div class="workflow-summary-card">
          <div class="workflow-summary-card__label">主请求</div>
          <div class="workflow-summary-card__value">{{ workflowSummary?.main_request_executed ? '已执行' : '未执行' }}</div>
          <div class="workflow-summary-card__meta">
            {{ record.main_request_blocked ? '前置步骤阻断了主请求' : '主请求已进入执行流程' }}
          </div>
        </div>
      </div>

      <div class="workflow-step-list">
        <article
          v-for="(step, index) in workflowSteps"
          :key="`${step.kind || 'step'}-${step.index || index}-${step.record_id || index}`"
          class="workflow-step-card"
        >
          <div class="workflow-step-card__header">
            <div class="workflow-step-card__copy">
              <a-space wrap :size="8">
                <a-tag size="small" color="arcoblue">#{{ step.index || index + 1 }}</a-tag>
                <a-tag :color="getStepStageTag(step).color">{{ getStepStageTag(step).label }}</a-tag>
                <a-tag :color="getStatusTag(step).color">{{ getStatusTag(step).label }}</a-tag>
                <a-tag v-if="step.kind === 'main_request'" color="cyan">主请求</a-tag>
                <a-tag v-else-if="step.continue_on_failure" color="orange">失败后继续</a-tag>
              </a-space>
              <div class="workflow-step-card__title">{{ step.name || step.request_name || `步骤 ${index + 1}` }}</div>
              <div class="workflow-step-card__meta">
                <span>{{ step.request_name || '未绑定接口信息' }}</span>
                <span>状态码 {{ step.status_code ?? '-' }}</span>
                <span>耗时 {{ formatDuration(step.response_time) }}</span>
              </div>
            </div>
          </div>

          <div v-if="step.error_message" class="workflow-step-card__error">
            {{ step.error_message }}
          </div>

          <div v-if="step.assertions_results?.length" class="workflow-step-card__note">
            该步骤包含 {{ step.assertions_results.length }} 条断言结果。
          </div>

          <div v-if="hasMeaningfulPayload(step.request_snapshot) || hasMeaningfulPayload(step.response_snapshot)" class="workflow-step-card__snapshots">
            <div v-if="hasMeaningfulPayload(step.request_snapshot)" class="workflow-step-card__snapshot">
              <div class="workflow-step-card__snapshot-title">步骤请求快照</div>
              <pre class="json-block json-block--compact">{{ stringifyBlock(step.request_snapshot) }}</pre>
            </div>
            <div v-if="hasMeaningfulPayload(step.response_snapshot)" class="workflow-step-card__snapshot">
              <div class="workflow-step-card__snapshot-title">步骤响应快照</div>
              <pre class="json-block json-block--compact">{{ stringifyBlock(step.response_snapshot) }}</pre>
            </div>
          </div>
        </article>
      </div>
    </template>

    <a-divider>断言结果</a-divider>
    <a-table :data="assertionTableData" :pagination="false" row-key="__key" size="small">
      <template #columns>
        <a-table-column title="#" data-index="index" :width="60" />
        <a-table-column title="类型" data-index="type" :width="140" />
        <a-table-column title="期望值" data-index="expected" ellipsis tooltip />
        <a-table-column title="实际值" data-index="actual" ellipsis tooltip />
        <a-table-column title="结果" :width="90">
          <template #cell="{ record: row }">
            <a-tag :color="row.passed ? 'green' : 'red'">{{ row.passed ? '通过' : '失败' }}</a-tag>
          </template>
        </a-table-column>
      </template>
    </a-table>

    <a-divider>请求快照</a-divider>
    <pre class="json-block">{{ stringifyBlock(requestSnapshotDisplay) }}</pre>

    <a-divider>响应快照</a-divider>
    <pre class="json-block">{{ stringifyBlock(record.response_snapshot) }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { executionRecordApi } from '../api'
import type {
  ApiExecutionFailureAnalysis,
  ApiExecutionRecord,
  ApiExecutionWorkflowStepResult,
  ApiExecutionWorkflowSummary,
} from '../types'

const props = defineProps<{
  record: ApiExecutionRecord | null
}>()

const analysisLoading = ref(false)
const analysisError = ref('')
const failureAnalysis = ref<ApiExecutionFailureAnalysis | null>(null)

const canAnalyzeFailure = computed(() => Boolean(props.record && !props.record.passed))

const workflowSummary = computed<ApiExecutionWorkflowSummary | null>(() => {
  const directSummary = props.record?.workflow_summary
  if (directSummary && typeof directSummary === 'object') return directSummary
  const snapshotSummary = props.record?.request_snapshot?.workflow_summary
  return snapshotSummary && typeof snapshotSummary === 'object' ? snapshotSummary : null
})

const workflowSteps = computed<ApiExecutionWorkflowStepResult[]>(() => {
  if (Array.isArray(props.record?.workflow_steps)) return props.record?.workflow_steps || []
  const snapshotSteps = props.record?.request_snapshot?.workflow_steps
  return Array.isArray(snapshotSteps) ? snapshotSteps : []
})

const showWorkflowSection = computed(() => Boolean(workflowSummary.value?.enabled || workflowSteps.value.length))

const assertionTableData = computed(() =>
  (props.record?.assertions_results || []).map((item, index) => ({
    ...item,
    __key: `${item.index ?? index}-${item.type ?? 'assertion'}-${index}`,
  }))
)

const requestSnapshotDisplay = computed(() => {
  const source = props.record?.request_snapshot
  if (!source || typeof source !== 'object') return source
  const cloned = JSON.parse(JSON.stringify(source))
  delete cloned.workflow_summary
  delete cloned.workflow_steps
  return Object.keys(cloned).length ? cloned : {}
})

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(2)} ms`
}

const formatFailureDate = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const stringifyBlock = (value: any) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const hasMeaningfulPayload = (value: any) => {
  if (value === null || value === undefined) return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}

const getStatusTag = (target?: { passed?: boolean | null; status?: string | null } | null) => {
  if (!target) return { color: 'gray', label: '未知' }
  if (target.passed === true || target.status === 'success') return { color: 'green', label: '通过' }
  if (target.status === 'error') return { color: 'red', label: '异常' }
  if (target.status === 'failed' || target.passed === false) return { color: 'orange', label: '失败' }
  return { color: 'gray', label: '未知' }
}

const getStepStageTag = (step: ApiExecutionWorkflowStepResult) => {
  if (step.kind === 'main_request') return { color: 'cyan', label: 'Main Request' }
  if (step.stage === 'teardown') return { color: 'orange', label: 'Teardown' }
  if (step.stage === 'request') return { color: 'green', label: 'Request' }
  return { color: 'arcoblue', label: 'Prepare' }
}

const getPriorityTagColor = (priority: string) => {
  if (priority === 'high') return 'red'
  if (priority === 'low') return 'gray'
  return 'orange'
}

const loadFailureAnalysis = async () => {
  if (!props.record || props.record.passed) return
  analysisLoading.value = true
  analysisError.value = ''
  try {
    const res = await executionRecordApi.analyzeFailure(props.record.id)
    failureAnalysis.value = res.data?.data || null
  } catch (error: any) {
    console.error('[ExecutionRecordDetailPanel] 获取失败复盘失败:', error)
    analysisError.value = error?.error || '获取失败复盘失败'
    Message.error(analysisError.value)
  } finally {
    analysisLoading.value = false
  }
}

watch(
  () => props.record?.id,
  () => {
    analysisError.value = ''
    failureAnalysis.value = null
  },
  { immediate: true }
)
</script>

<style scoped>
.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-analysis-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ai-analysis-toolbar__meta {
  font-size: 12px;
  color: #64748b;
}

.ai-summary-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(15, 118, 110, 0.08));
  border: 1px solid rgba(14, 165, 233, 0.14);
}

.ai-summary-card__label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0f766e;
}

.ai-summary-card__value {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.7;
  color: #0f172a;
}

.ai-summary-card__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  font-size: 12px;
  line-height: 1.7;
  color: #475569;
}

.ai-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.ai-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.ai-card__title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.ai-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-list-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.ai-list-item__title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.ai-list-item__meta {
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
}

.ai-list-item__detail {
  font-size: 12px;
  line-height: 1.7;
  color: #475569;
  word-break: break-word;
}

.workflow-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.workflow-summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.workflow-summary-card--primary {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(59, 130, 246, 0.08));
}

.workflow-summary-card__label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
}

.workflow-summary-card__value {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
}

.workflow-summary-card__meta {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.workflow-step-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.workflow-step-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.workflow-step-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.workflow-step-card__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.workflow-step-card__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.workflow-step-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.workflow-step-card__error {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(254, 242, 242, 0.9);
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-word;
}

.workflow-step-card__note {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(239, 246, 255, 0.9);
  color: #1d4ed8;
  font-size: 12px;
  line-height: 1.7;
}

.workflow-step-card__snapshots {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.workflow-step-card__snapshot {
  min-width: 0;
}

.workflow-step-card__snapshot-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
}

.json-block {
  margin: 0;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.95);
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.json-block--compact {
  padding: 12px;
  font-size: 11px;
}

@media (max-width: 900px) {
  .ai-grid,
  .workflow-summary-grid,
  .workflow-step-card__snapshots {
    grid-template-columns: 1fr;
  }
}
</style>
