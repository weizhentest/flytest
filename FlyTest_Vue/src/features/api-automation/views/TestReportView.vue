<template>
  <div class="test-report-view">
    <div class="report-hero">
      <div class="report-hero__copy">
        <div class="report-hero__eyebrow">AI Report Center</div>
        <div class="report-hero__title">测试报告</div>
        <div class="report-hero__desc">
          结合执行批次、失败用例、接口维度统计与 AI 摘要，快速生成适合测试回顾和质量同步的报告视图。
        </div>
        <div class="report-hero__meta">
          <span>{{ projectName }}</span>
          <span>{{ selectedCollectionName || '当前项目全部接口目录' }}</span>
          <span>{{ report?.summary.total_count || 0 }} 条执行记录</span>
        </div>
      </div>
      <div class="report-hero__actions">
        <a-radio-group v-model="days" type="button" @change="loadReport">
          <a-radio :value="7">7天</a-radio>
          <a-radio :value="30">30天</a-radio>
          <a-radio :value="90">90天</a-radio>
        </a-radio-group>
        <a-button :loading="aiSummaryLoading" :disabled="!report?.summary.total_count" @click="loadAiSummary">
          {{ aiSummary ? '重新获取 AI 摘要' : '生成 AI 摘要' }}
        </a-button>
        <a-button @click="loadReport">刷新</a-button>
      </div>
    </div>

    <div v-if="!projectId" class="state-card">
      <a-empty description="请先选择项目" />
    </div>

    <div v-else-if="loading" class="state-card">
      <a-spin size="large" />
    </div>

    <div v-else-if="!report || !report.summary.total_count" class="state-card">
      <a-empty description="当前筛选条件下暂无可汇总的执行记录" />
    </div>

    <template v-else>
      <div class="report-grid summary-grid">
        <div class="summary-card summary-card-primary">
          <div class="summary-label">总执行数</div>
          <div class="summary-value">{{ report.summary.total_count }}</div>
          <div class="summary-meta">最近执行：{{ formatDate(report.summary.latest_executed_at) }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">通过率</div>
          <div class="summary-value">{{ report.summary.pass_rate }}%</div>
          <a-progress :percent="report.summary.pass_rate" :show-text="false" color="#0f766e" />
        </div>
        <div class="summary-card">
          <div class="summary-label">执行批次</div>
          <div class="summary-value">{{ report.hierarchy_summary?.run_count || runGroups.length }}</div>
          <div class="summary-meta">展示最近 {{ runGroups.length }} 个批次</div>
        </div>
        <div class="summary-card summary-card-danger">
          <div class="summary-label">失败用例</div>
          <div class="summary-value">{{ report.hierarchy_summary?.failed_test_case_count || 0 }}</div>
          <div class="summary-meta">失败接口 {{ report.hierarchy_summary?.failed_interface_count || 0 }} 个</div>
        </div>
      </div>

      <a-card class="report-card ai-summary-report-card" :bordered="false" title="AI 报告摘要">
        <div class="ai-summary-report-toolbar">
          <a-button type="primary" size="small" :loading="aiSummaryLoading" @click="loadAiSummary">
            {{ aiSummary ? '重新生成摘要' : '生成摘要' }}
          </a-button>
          <span v-if="aiSummary" class="ai-summary-report-toolbar__meta">
            {{ aiSummary.used_ai ? 'AI 摘要' : '规则摘要' }}
            <template v-if="aiSummary.cache_hit"> / 命中缓存</template>
            <template v-if="aiSummary.duration_ms"> / {{ Math.round(aiSummary.duration_ms) }} ms</template>
          </span>
        </div>

        <a-alert v-if="aiSummaryError" type="error" :show-icon="true">{{ aiSummaryError }}</a-alert>
        <a-empty v-else-if="!aiSummary" description="点击上方按钮生成当前筛选范围内的测试报告摘要。" />

        <template v-else>
          <div class="ai-report-summary-card">
            <div class="ai-report-summary-card__label">摘要结论</div>
            <div class="ai-report-summary-card__value">{{ aiSummary.summary || '暂无摘要结论' }}</div>
            <div class="ai-report-summary-card__meta">{{ aiSummary.note }}</div>
          </div>

          <div class="ai-report-grid">
            <div class="ai-report-block">
              <div class="ai-report-block__title">主要风险</div>
              <div v-if="aiSummary.top_risks.length" class="ai-report-list">
                <article v-for="(item, index) in aiSummary.top_risks" :key="`${item.title}-${index}`" class="ai-report-list-item">
                  <div class="ai-report-list-item__title">{{ item.title }}</div>
                  <div class="ai-report-list-item__detail">{{ item.detail }}</div>
                </article>
              </div>
              <a-empty v-else description="暂无主要风险摘要" />
            </div>

            <div class="ai-report-block">
              <div class="ai-report-block__title">建议动作</div>
              <div v-if="aiSummary.recommended_actions.length" class="ai-report-list">
                <article
                  v-for="(item, index) in aiSummary.recommended_actions"
                  :key="`${item.title}-${index}`"
                  class="ai-report-list-item"
                >
                  <div class="ai-report-list-item__title">
                    {{ item.title }}
                    <a-tag size="small" :color="getPriorityColor(item.priority)">{{ item.priority }}</a-tag>
                  </div>
                  <div class="ai-report-list-item__detail">{{ item.detail }}</div>
                </article>
              </div>
              <a-empty v-else description="暂无建议动作" />
            </div>
          </div>

          <div class="ai-report-block">
            <div class="ai-report-block__title">关键证据</div>
            <div v-if="aiSummary.evidence.length" class="ai-report-list">
              <article v-for="(item, index) in aiSummary.evidence" :key="`${item.label}-${index}`" class="ai-report-list-item">
                <div class="ai-report-list-item__title">{{ item.label }}</div>
                <div class="ai-report-list-item__detail">{{ item.detail }}</div>
              </article>
            </div>
            <a-empty v-else description="暂无关键证据" />
          </div>
        </template>
      </a-card>

      <a-card class="report-card" :bordered="false" title="执行汇总">
        <div class="run-report-list">
          <div v-for="run in runGroups" :key="run.run_id" class="run-report-card">
            <div class="run-report-card__header">
              <div class="run-report-card__copy">
                <div class="run-report-card__eyebrow">{{ runTypeLabelMap[run.run_type] || '执行批次' }}</div>
                <div class="run-report-card__title">{{ run.run_name }}</div>
                <div class="run-report-card__meta">
                  <span>{{ formatDate(run.latest_executed_at) }}</span>
                  <span>{{ run.total_count }} 条执行</span>
                  <span>{{ run.interface_count }} 个接口</span>
                  <span v-if="run.environment_names.length">{{ run.environment_names.join(' / ') }}</span>
                </div>
              </div>
              <div class="run-report-card__stats">
                <a-tag color="green">通过 {{ run.passed_count }}</a-tag>
                <a-tag color="orange">失败 {{ run.failed_count }}</a-tag>
                <a-tag color="red">异常 {{ run.error_count }}</a-tag>
              </div>
            </div>

            <div class="interface-report-list">
              <section
                v-for="interfaceItem in run.interfaces"
                :key="`${run.run_id}-${interfaceItem.request_id || interfaceItem.interface_name}`"
                class="interface-report-card"
              >
                <div class="interface-report-card__header">
                  <div class="interface-report-card__copy">
                    <div class="interface-report-card__title">
                      <a-tag :color="methodColorMap[interfaceItem.method || ''] || 'arcoblue'">
                        {{ interfaceItem.method || '-' }}
                      </a-tag>
                      <span>{{ interfaceItem.interface_name }}</span>
                    </div>
                    <div class="interface-report-card__meta">
                      <span>{{ interfaceItem.url || '-' }}</span>
                      <span>{{ interfaceItem.collection_name || '未分组' }}</span>
                      <span>{{ interfaceItem.total_count }} 条执行</span>
                      <span>{{ interfaceItem.failed_test_case_count }} 条失败用例</span>
                    </div>
                  </div>
                  <div class="interface-report-card__summary">
                    <a-tag color="green">通过 {{ interfaceItem.passed_count }}</a-tag>
                    <a-tag color="red">未通过 {{ interfaceItem.failed_count + interfaceItem.error_count }}</a-tag>
                  </div>
                </div>

                <a-empty v-if="!interfaceItem.failed_test_cases.length" description="本接口在该批次下全部通过" />

                <div v-else class="failed-case-list">
                  <article
                    v-for="caseItem in interfaceItem.failed_test_cases"
                    :key="`${run.run_id}-${caseItem.test_case_id || caseItem.test_case_name}`"
                    class="failed-case-card"
                  >
                    <div class="failed-case-card__head">
                      <div>
                        <div class="failed-case-card__title">{{ caseItem.test_case_name }}</div>
                        <div class="failed-case-card__meta">
                          <span>{{ caseItem.is_direct_request ? '接口直接执行' : '测试用例执行' }}</span>
                          <span>状态码 {{ pickFailedRecord(caseItem)?.status_code ?? '-' }}</span>
                          <span>{{ formatDate(caseItem.latest_executed_at) }}</span>
                          <span v-if="getWorkflowSummaryText(pickFailedRecord(caseItem))">
                            {{ getWorkflowSummaryText(pickFailedRecord(caseItem)) }}
                          </span>
                        </div>
                      </div>
                      <a-tag :color="getRecordStatusTag(pickFailedRecord(caseItem)).color">
                        {{ getRecordStatusTag(pickFailedRecord(caseItem)).label }}
                      </a-tag>
                    </div>
                    <div class="failed-case-card__error">
                      {{ caseItem.latest_error_message || pickFailedRecord(caseItem)?.error_message || '断言未通过' }}
                    </div>
                    <div class="failed-case-card__footer">
                      <a-button type="text" size="small" @click="viewRecord(pickFailedRecord(caseItem))">
                        查看失败详情
                      </a-button>
                    </div>
                  </article>
                </div>
              </section>
            </div>
          </div>
        </div>
      </a-card>

      <div class="report-grid two-column-grid">
        <a-card class="report-card" :bordered="false" title="按请求方法统计">
          <a-table :data="methodTableData" :pagination="false" row-key="method" size="small">
            <template #columns>
              <a-table-column title="方法" data-index="method" :width="100">
                <template #cell="{ record }">
                  <a-tag :color="methodColorMap[record.method] || 'arcoblue'">{{ record.method }}</a-tag>
                </template>
              </a-table-column>
              <a-table-column title="总数" data-index="total" :width="80" />
              <a-table-column title="通过" data-index="passed" :width="80" />
              <a-table-column title="失败" data-index="failed" :width="80" />
              <a-table-column title="异常" data-index="error" :width="80" />
              <a-table-column title="平均耗时" :width="120">
                <template #cell="{ record }">{{ formatDuration(record.avg_response_time) }}</template>
              </a-table-column>
            </template>
          </a-table>
        </a-card>

        <a-card class="report-card" :bordered="false" title="按接口目录统计">
          <a-table :data="collectionTableData" :pagination="false" row-key="name" size="small">
            <template #columns>
              <a-table-column title="目录" data-index="name" ellipsis tooltip />
              <a-table-column title="总数" data-index="total" :width="80" />
              <a-table-column title="通过" data-index="passed" :width="80" />
              <a-table-column title="失败" data-index="failed" :width="80" />
              <a-table-column title="异常" data-index="error" :width="80" />
              <a-table-column title="通过率" :width="120">
                <template #cell="{ record }">{{ record.passRate }}%</template>
              </a-table-column>
            </template>
          </a-table>
        </a-card>
      </div>

      <div class="report-grid two-column-grid">
        <a-card class="report-card" :bordered="false" title="高频失败接口">
          <a-empty v-if="!failingRequestData.length" description="最近没有失败接口" />
          <a-table v-else :data="failingRequestData" :pagination="false" row-key="request_name" size="small">
            <template #columns>
              <a-table-column title="接口" data-index="request_name" ellipsis tooltip />
              <a-table-column title="目录" data-index="collection_name" :width="140" ellipsis tooltip />
              <a-table-column title="失败次数" data-index="total" :width="100" />
              <a-table-column title="最近状态码" data-index="latest_status_code" :width="110" />
              <a-table-column title="最近执行" :width="170">
                <template #cell="{ record }">{{ formatDate(record.latest_executed_at) }}</template>
              </a-table-column>
            </template>
          </a-table>
        </a-card>

        <a-card class="report-card" :bordered="false" title="执行趋势">
          <a-empty v-if="!trendData.length" description="暂无趋势数据" />
          <div v-else class="trend-list">
            <div v-for="item in trendData" :key="item.day" class="trend-item">
              <div class="trend-day">{{ formatDate(item.day, true) }}</div>
              <div class="trend-bars">
                <div class="trend-bar trend-bar-total" :style="{ width: `${item.totalWidth}%` }"></div>
                <div class="trend-bar trend-bar-pass" :style="{ width: `${item.passWidth}%` }"></div>
              </div>
              <div class="trend-meta">
                <span>总 {{ item.total }}</span>
                <span>通过 {{ item.passed }}</span>
                <span>未通过 {{ item.failed + item.error }}</span>
              </div>
            </div>
          </div>
        </a-card>
      </div>

      <a-card class="report-card" :bordered="false" title="最近执行记录">
        <a-table :data="report.recent_records" :pagination="false" row-key="id" size="small">
          <template #columns>
            <a-table-column title="接口" :width="220" ellipsis tooltip>
              <template #cell="{ record }">{{ record.interface_name || record.request_name }}</template>
            </a-table-column>
            <a-table-column title="用例" :width="220" ellipsis tooltip>
              <template #cell="{ record }">{{ record.test_case_name || '接口直接执行' }}</template>
            </a-table-column>
            <a-table-column title="结果" :width="100">
              <template #cell="{ record }">
                <a-tag :color="getRecordStatusTag(record).color">{{ getRecordStatusTag(record).label }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="状态码" data-index="status_code" :width="90" />
            <a-table-column title="耗时" :width="110">
              <template #cell="{ record }">{{ formatDuration(record.response_time) }}</template>
            </a-table-column>
            <a-table-column title="执行时间" :width="180">
              <template #cell="{ record }">{{ formatDate(record.created_at) }}</template>
            </a-table-column>
            <a-table-column title="操作" :width="100" align="center">
              <template #cell="{ record }">
                <a-button type="text" size="small" @click="viewRecord(record)">详情</a-button>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-card>
    </template>

    <a-modal
      v-model:visible="detailVisible"
      class="detail-modal detail-modal--wide"
      title="失败详情"
      width="1120px"
      :footer="false"
      :mask-closable="true"
      :body-style="{ maxHeight: '78vh', overflowY: 'auto' }"
    >
      <ExecutionRecordDetailPanel :record="currentRecord" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { executionRecordApi } from '../api'
import ExecutionRecordDetailPanel from '../components/ExecutionRecordDetailPanel.vue'
import type {
  ApiExecutionRecord,
  ApiExecutionReport,
  ApiExecutionReportAISummary,
  ApiExecutionReportCaseGroup,
} from '../types'

const props = defineProps<{
  projectId?: number
  selectedCollectionId?: number
  selectedCollectionName?: string
}>()

const projectStore = useProjectStore()

const loading = ref(false)
const aiSummaryLoading = ref(false)
const days = ref(30)
const report = ref<ApiExecutionReport | null>(null)
const aiSummary = ref<ApiExecutionReportAISummary | null>(null)
const aiSummaryError = ref('')
const detailVisible = ref(false)
const currentRecord = ref<ApiExecutionRecord | null>(null)

const projectName = computed(() => projectStore.currentProject?.name || '未选择项目')
const runGroups = computed(() => report.value?.run_groups || [])

const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
}

const runTypeLabelMap: Record<string, string> = {
  request: '接口执行批次',
  test_case: '测试用例执行批次',
  mixed: '混合执行批次',
}

const formatDate = (value?: string | null, compact = false) => {
  if (!value) return '-'
  const date = new Date(value)
  return compact ? date.toLocaleDateString('zh-CN') : date.toLocaleString('zh-CN')
}

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(2)} ms`
}

const getRecordStatusTag = (record?: ApiExecutionRecord | null) => {
  if (!record) return { color: 'gray', label: '未知' }
  if (record.passed) return { color: 'green', label: '通过' }
  if (record.status === 'error') return { color: 'red', label: '异常' }
  return { color: 'orange', label: '失败' }
}

const getPriorityColor = (priority: string) => {
  if (priority === 'high') return 'red'
  if (priority === 'low') return 'gray'
  return 'orange'
}

const pickFailedRecord = (caseItem: ApiExecutionReportCaseGroup) => {
  return caseItem.failed_records?.[0] || caseItem.records?.[0] || null
}

const getWorkflowSummaryText = (record?: ApiExecutionRecord | null) => {
  if (!record) return ''
  const workflowSummary = record.workflow_summary
  const stepCount =
    workflowSummary?.executed_step_count ||
    workflowSummary?.configured_step_count ||
    record.workflow_steps?.length ||
    0
  if (!workflowSummary?.enabled && !stepCount) return ''
  if (record.main_request_blocked) return `工作流 ${stepCount} 步，主请求未执行`
  if (workflowSummary?.has_failure) return `工作流 ${stepCount} 步，存在失败步骤`
  return `工作流 ${stepCount} 步`
}

const methodTableData = computed(() => report.value?.method_breakdown || [])

const collectionTableData = computed(() => {
  return (report.value?.collection_breakdown || []).map(item => {
    const total = item.total || 0
    const passRate = total ? Number(((item.passed / total) * 100).toFixed(2)) : 0
    return {
      ...item,
      name: item.request__collection__name || '未分组',
      passRate,
    }
  })
})

const failingRequestData = computed(() => {
  return (report.value?.failing_requests || []).map(item => ({
    ...item,
    collection_name: item.request__collection__name || '未分组',
  }))
})

const trendData = computed(() => {
  const trend = report.value?.trend || []
  const maxTotal = Math.max(...trend.map(item => item.total), 1)
  return trend.map(item => ({
    ...item,
    totalWidth: Number(((item.total / maxTotal) * 100).toFixed(2)),
    passWidth: item.total ? Number(((item.passed / item.total) * 100).toFixed(2)) : 0,
  }))
})

const loadReport = async () => {
  if (!props.projectId) {
    report.value = null
    aiSummary.value = null
    aiSummaryError.value = ''
    return
  }

  loading.value = true
  try {
    const res = await executionRecordApi.report({
      project: props.projectId,
      collection: props.selectedCollectionId,
      days: days.value,
    })
    report.value = res.data?.data || null
    aiSummary.value = null
    aiSummaryError.value = ''
  } catch (error) {
    console.error('[TestReportView] 获取测试报告失败:', error)
    Message.error('获取测试报告失败')
    report.value = null
    aiSummary.value = null
    aiSummaryError.value = ''
  } finally {
    loading.value = false
  }
}

const loadAiSummary = async () => {
  if (!props.projectId) return
  aiSummaryLoading.value = true
  aiSummaryError.value = ''
  try {
    const res = await executionRecordApi.reportSummary({
      project: props.projectId,
      collection: props.selectedCollectionId,
      days: days.value,
    })
    aiSummary.value = res.data?.data || null
  } catch (error: any) {
    console.error('[TestReportView] 获取AI报告摘要失败:', error)
    aiSummaryError.value = error?.error || '获取AI报告摘要失败'
    Message.error(aiSummaryError.value)
  } finally {
    aiSummaryLoading.value = false
  }
}

const viewRecord = (record: ApiExecutionRecord | null) => {
  if (!record) return
  currentRecord.value = record
  detailVisible.value = true
}

watch(
  () => [props.projectId, props.selectedCollectionId],
  () => {
    loadReport()
  },
  { immediate: true }
)

defineExpose({
  refresh: loadReport,
})
</script>

<style scoped>
.test-report-view {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.report-hero {
  display: grid;
  grid-template-columns: minmax(280px, 1.1fr) minmax(340px, 0.9fr);
  gap: 22px;
  align-items: end;
  padding: 26px 28px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(248, 250, 252, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 20px 44px rgba(15, 23, 42, 0.08);
}

.report-hero__copy,
.report-hero__actions {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

.report-hero__copy {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.report-hero__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #2563eb;
}

.report-hero__title {
  font-size: 30px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.06;
}

.report-hero__desc {
  max-width: 760px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.report-hero__meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #64748b;
}

.report-hero__actions {
  justify-content: flex-end;
  align-items: center;
}

.state-card,
.summary-card,
.report-card {
  border-radius: 26px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.state-card {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.report-grid {
  display: grid;
  gap: 18px;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.two-column-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-card {
  padding: 22px;
}

.summary-card-primary {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.14), rgba(14, 165, 233, 0.08));
}

.summary-card-danger {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(249, 115, 22, 0.08));
}

.summary-label {
  font-size: 13px;
  color: #64748b;
}

.summary-value {
  margin-top: 10px;
  font-size: 34px;
  font-weight: 800;
  color: #0f172a;
}

.summary-meta {
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}

.ai-summary-report-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.ai-summary-report-toolbar__meta {
  font-size: 12px;
  color: #64748b;
}

.ai-report-summary-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 20px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(15, 118, 110, 0.08));
  border: 1px solid rgba(14, 165, 233, 0.14);
}

.ai-report-summary-card__label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0f766e;
}

.ai-report-summary-card__value {
  font-size: 16px;
  line-height: 1.7;
  color: #0f172a;
  font-weight: 700;
}

.ai-report-summary-card__meta {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.ai-report-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.ai-report-block {
  margin-top: 16px;
  padding: 18px 20px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.ai-report-block__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.ai-report-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.ai-report-list-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-report-list-item__title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.ai-report-list-item__detail {
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
}

.run-report-list,
.interface-report-list,
.failed-case-list,
.trend-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.run-report-card,
.interface-report-card,
.failed-case-card {
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(255, 255, 255, 0.92);
}

.run-report-card {
  padding: 20px;
}

.interface-report-card {
  padding: 18px;
}

.failed-case-card {
  padding: 16px;
  background: rgba(248, 250, 252, 0.92);
}

.run-report-card__header,
.interface-report-card__header,
.failed-case-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.run-report-card__copy,
.interface-report-card__copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.run-report-card__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #0f766e;
}

.run-report-card__title,
.interface-report-card__title,
.failed-case-card__title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
}

.run-report-card__meta,
.interface-report-card__meta,
.failed-case-card__meta,
.trend-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #64748b;
}

.failed-case-card__error {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #b91c1c;
}

.failed-case-card__footer {
  margin-top: 10px;
}

.trend-item {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) 260px;
  gap: 14px;
  align-items: center;
}

.trend-day {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.trend-bars {
  position: relative;
  height: 12px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.8);
  overflow: hidden;
}

.trend-bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  border-radius: 999px;
}

.trend-bar-total {
  background: rgba(59, 130, 246, 0.22);
}

.trend-bar-pass {
  background: linear-gradient(90deg, #14b8a6, #0f766e);
}

.report-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.report-card :deep(.arco-table-container) {
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

@media (max-width: 1200px) {
  .report-hero,
  .summary-grid,
  .two-column-grid,
  .ai-report-grid {
    grid-template-columns: 1fr;
  }

  .report-hero__actions {
    justify-content: flex-start;
  }
}

@media (max-width: 900px) {
  .report-hero,
  .run-report-card__header,
  .interface-report-card__header,
  .failed-case-card__head {
    align-items: stretch;
  }

  .trend-item {
    grid-template-columns: 1fr;
  }
}
</style>
