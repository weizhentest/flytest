<template>
  <div class="test-report-view">
    <div class="page-header api-page-header">
      <div class="header-left">
        <div class="report-title-group">
          <div class="report-title">测试报告</div>
          <div class="report-subtitle">
            {{ projectName }} / {{ selectedCollectionName || '当前项目全部接口目录' }}
          </div>
        </div>
      </div>
      <div class="header-right">
        <a-radio-group v-model="days" type="button" @change="loadReport">
          <a-radio :value="7">7天</a-radio>
          <a-radio :value="30">30天</a-radio>
          <a-radio :value="90">90天</a-radio>
        </a-radio-group>
        <a-button @click="loadReport">刷新</a-button>
      </div>
    </div>

    <div v-if="!projectId" class="empty-tip-card">
      <a-empty description="请先选择项目。" />
    </div>

    <div v-else-if="loading" class="report-loading-card">
      <a-spin size="large" />
    </div>

    <div v-else-if="!report || !report.summary.total_count" class="empty-tip-card">
      <a-empty description="当前筛选条件下暂无可汇总的执行记录。" />
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
          <div class="summary-meta">
            失败接口 {{ report.hierarchy_summary?.failed_interface_count || 0 }} 个
          </div>
        </div>
      </div>

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
              <section v-for="interfaceItem in run.interfaces" :key="`${run.run_id}-${interfaceItem.request_id || interfaceItem.interface_name}`" class="interface-report-card">
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

                <a-empty
                  v-if="!interfaceItem.failed_test_cases.length"
                  description="本接口在该批次下全部通过。"
                />

                <div v-else class="failed-case-list">
                  <article v-for="caseItem in interfaceItem.failed_test_cases" :key="`${run.run_id}-${caseItem.test_case_id || caseItem.test_case_name}`" class="failed-case-card">
                    <div class="failed-case-card__head">
                      <div>
                        <div class="failed-case-card__title">{{ caseItem.test_case_name }}</div>
                        <div class="failed-case-card__meta">
                          <span>{{ caseItem.is_direct_request ? '接口直接执行' : '测试用例执行' }}</span>
                          <span>状态码 {{ pickFailedRecord(caseItem)?.status_code ?? '-' }}</span>
                          <span>{{ formatDate(caseItem.latest_executed_at) }}</span>
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
          <a-empty v-if="!failingRequestData.length" description="最近没有失败接口。" />
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
          <a-empty v-if="!trendData.length" description="暂无趋势数据。" />
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
      <div v-if="currentRecord" class="detail-drawer">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="执行批次">{{ currentRecord.run_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="接口名称">{{ currentRecord.interface_name || currentRecord.request_name }}</a-descriptions-item>
          <a-descriptions-item label="测试用例">{{ currentRecord.test_case_name || '接口直接执行' }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="getRecordStatusTag(currentRecord).color">
              {{ getRecordStatusTag(currentRecord).label }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="状态码">{{ currentRecord.status_code ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="响应时间">{{ formatDuration(currentRecord.response_time) }}</a-descriptions-item>
          <a-descriptions-item label="执行环境">{{ currentRecord.environment_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ currentRecord.executor_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="最终地址" :span="2">{{ currentRecord.url }}</a-descriptions-item>
          <a-descriptions-item label="错误信息" :span="2">{{ currentRecord.error_message || '-' }}</a-descriptions-item>
        </a-descriptions>

        <a-divider>断言结果</a-divider>
        <a-table :data="currentRecord.assertions_results || []" :pagination="false" row-key="index" size="small">
          <template #columns>
            <a-table-column title="#" data-index="index" :width="60" />
            <a-table-column title="类型" data-index="type" :width="120" />
            <a-table-column title="期望值" data-index="expected" ellipsis tooltip />
            <a-table-column title="实际值" data-index="actual" ellipsis tooltip />
            <a-table-column title="结果" :width="90">
              <template #cell="{ record }">
                <a-tag :color="record.passed ? 'green' : 'red'">{{ record.passed ? '通过' : '失败' }}</a-tag>
              </template>
            </a-table-column>
          </template>
        </a-table>

        <a-divider>请求快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentRecord.request_snapshot) }}</pre>

        <a-divider>响应快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentRecord.response_snapshot) }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { executionRecordApi } from '../api'
import type {
  ApiExecutionRecord,
  ApiExecutionReport,
  ApiExecutionReportCaseGroup,
} from '../types'

const props = defineProps<{
  projectId?: number
  selectedCollectionId?: number
  selectedCollectionName?: string
}>()

const projectStore = useProjectStore()

const loading = ref(false)
const days = ref(30)
const report = ref<ApiExecutionReport | null>(null)
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

const stringifyBlock = (value: any) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const getRecordStatusTag = (record?: ApiExecutionRecord | null) => {
  if (!record) return { color: 'gray', label: '未知' }
  if (record.passed) return { color: 'green', label: '通过' }
  if (record.status === 'error') return { color: 'red', label: '异常' }
  return { color: 'orange', label: '失败' }
}

const pickFailedRecord = (caseItem: ApiExecutionReportCaseGroup) => {
  return caseItem.failed_records?.[0] || caseItem.records?.[0] || null
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
  } catch (error) {
    console.error('[TestReportView] 获取测试报告失败:', error)
    Message.error('获取测试报告失败')
    report.value = null
  } finally {
    loading.value = false
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

.api-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.9));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.06);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.report-title-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.report-title {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  color: #0f172a;
}

.report-subtitle {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.report-loading-card,
.empty-tip-card {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  padding: 32px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
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
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 22px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.summary-card-primary {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(59, 130, 246, 0.08));
}

.summary-card-danger {
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.12), rgba(249, 115, 22, 0.08));
}

.summary-label {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #64748b;
  text-transform: uppercase;
}

.summary-value {
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
}

.summary-meta {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.report-card {
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.report-card :deep(.arco-card-header) {
  padding-bottom: 0;
}

.run-report-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.run-report-card {
  padding: 18px;
  border-radius: 20px;
  background: rgba(248, 250, 252, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.run-report-card__header,
.interface-report-card__header,
.failed-case-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.run-report-card__copy,
.interface-report-card__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-report-card__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #0f766e;
}

.run-report-card__title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.run-report-card__meta,
.interface-report-card__meta,
.failed-case-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.run-report-card__stats,
.interface-report-card__summary {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.interface-report-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.interface-report-card {
  padding: 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.interface-report-card__title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.interface-report-card__title span {
  min-width: 0;
  word-break: break-word;
}

.failed-case-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.failed-case-card {
  padding: 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(248, 113, 113, 0.16);
}

.failed-case-card__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.failed-case-card__error {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(254, 242, 242, 0.9);
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-word;
}

.failed-case-card__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.trend-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.trend-item {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) 210px;
  gap: 16px;
  align-items: center;
}

.trend-day {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.trend-bars {
  position: relative;
  height: 14px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.8);
  overflow: hidden;
}

.trend-bar {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  border-radius: 999px;
}

.trend-bar-total {
  background: rgba(59, 130, 246, 0.24);
}

.trend-bar-pass {
  background: linear-gradient(90deg, #0f766e, #14b8a6);
}

.trend-meta {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  font-size: 12px;
  color: #64748b;
}

.detail-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.detail-modal :deep(.arco-modal) {
  max-width: min(1120px, calc(100vw - 32px));
}

.detail-modal :deep(.arco-modal-body) {
  padding: 20px 24px 24px;
}

@media (max-width: 1200px) {
  .summary-grid,
  .two-column-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .api-page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .trend-item {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .trend-meta {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
