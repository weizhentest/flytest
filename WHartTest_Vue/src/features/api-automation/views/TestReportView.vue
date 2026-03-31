<template>
  <div class="test-report-view">
    <div class="page-header api-page-header">
      <div class="header-left">
        <div class="report-title-group">
          <div class="report-title">测试报告</div>
          <div class="report-subtitle">
            {{ selectedCollectionName ? `当前集合：${selectedCollectionName}` : '当前项目 API 自动化执行汇总' }}
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
      <a-empty description="请先选择项目" />
    </div>

    <div v-else-if="loading" class="report-loading-card">
      <a-spin size="large" />
    </div>

    <div v-else-if="!report || !report.summary.total_count" class="empty-tip-card">
      <a-empty description="当前筛选条件下暂无执行记录，暂时无法生成测试报告" />
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
          <div class="summary-label">平均响应时间</div>
          <div class="summary-value">{{ formatDuration(report.summary.avg_response_time) }}</div>
          <div class="summary-meta">成功：{{ report.summary.success_count }}，失败：{{ report.summary.failed_count }}</div>
        </div>
        <div class="summary-card summary-card-danger">
          <div class="summary-label">错误 / 异常</div>
          <div class="summary-value">{{ report.summary.error_count }}</div>
          <div class="summary-meta">未通过总数：{{ report.summary.total_count - report.summary.passed_count }}</div>
        </div>
      </div>

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

        <a-card class="report-card" :bordered="false" title="按集合统计">
          <a-table :data="collectionTableData" :pagination="false" row-key="name" size="small">
            <template #columns>
              <a-table-column title="集合" data-index="name" ellipsis tooltip />
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
              <a-table-column title="集合" data-index="collection_name" :width="120" ellipsis tooltip />
              <a-table-column title="失败次数" data-index="total" :width="90" />
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
                <span>失败 {{ item.failed + item.error }}</span>
              </div>
            </div>
          </div>
        </a-card>
      </div>

      <a-card class="report-card" :bordered="false" title="最近执行记录">
        <a-table :data="report.recent_records" :pagination="false" row-key="id" size="small">
          <template #columns>
            <a-table-column title="接口" data-index="request_name" ellipsis tooltip />
            <a-table-column title="集合" data-index="request_collection_name" :width="140" ellipsis tooltip />
            <a-table-column title="方法" :width="90">
              <template #cell="{ record }">
                <a-tag :color="methodColorMap[record.method] || 'arcoblue'">{{ record.method }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="结果" :width="100">
              <template #cell="{ record }">
                <a-tag :color="record.passed ? 'green' : record.status === 'error' ? 'red' : 'orange'">
                  {{ record.passed ? '通过' : record.status }}
                </a-tag>
              </template>
            </a-table-column>
            <a-table-column title="状态码" data-index="status_code" :width="90" />
            <a-table-column title="耗时" :width="110">
              <template #cell="{ record }">{{ formatDuration(record.response_time) }}</template>
            </a-table-column>
            <a-table-column title="执行时间" :width="180">
              <template #cell="{ record }">{{ formatDate(record.created_at) }}</template>
            </a-table-column>
          </template>
        </a-table>
      </a-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { executionRecordApi } from '../api'
import type { ApiExecutionReport } from '../types'

const props = defineProps<{
  projectId?: number
  selectedCollectionId?: number
  selectedCollectionName?: string
}>()

const loading = ref(false)
const days = ref(30)
const report = ref<ApiExecutionReport | null>(null)

const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
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
    const data = res.data?.data || res.data || null
    report.value = data
  } catch (error) {
    console.error('[TestReportView] 获取测试报告失败:', error)
    Message.error('获取测试报告失败')
    report.value = null
  } finally {
    loading.value = false
  }
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

@media (max-width: 1200px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

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
