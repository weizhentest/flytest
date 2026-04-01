<template>
  <div class="execution-report-view">
    <div class="page-header api-page-header">
      <div class="header-left">
        <a-input-number
          v-model="days"
          :min="1"
          :max="90"
          mode="button"
          size="large"
        />
        <span class="range-label">统计最近 {{ days }} 天</span>
      </div>
      <div class="header-right">
        <a-button @click="loadReport">刷新报告</a-button>
      </div>
    </div>

    <div v-if="report" class="report-grid">
      <section class="summary-grid">
        <article class="summary-card">
          <span class="summary-label">总执行次数</span>
          <strong class="summary-value">{{ report.summary.total_count }}</strong>
        </article>
        <article class="summary-card success">
          <span class="summary-label">通过率</span>
          <strong class="summary-value">{{ report.summary.pass_rate }}%</strong>
        </article>
        <article class="summary-card">
          <span class="summary-label">失败数</span>
          <strong class="summary-value">{{ report.summary.failed_count + report.summary.error_count }}</strong>
        </article>
        <article class="summary-card">
          <span class="summary-label">平均响应</span>
          <strong class="summary-value">
            {{ report.summary.avg_response_time !== null ? `${report.summary.avg_response_time.toFixed(2)} ms` : '-' }}
          </strong>
        </article>
      </section>

      <section class="report-card">
        <div class="card-title">请求方法分布</div>
        <a-table :data="report.method_breakdown" :pagination="false" row-key="method" size="small">
          <template #columns>
            <a-table-column title="方法" data-index="method" :width="120" />
            <a-table-column title="总数" data-index="total" :width="90" />
            <a-table-column title="通过" data-index="passed" :width="90" />
            <a-table-column title="失败" :width="90">
              <template #cell="{ record }">{{ record.failed + record.error }}</template>
            </a-table-column>
            <a-table-column title="平均响应" :width="140">
              <template #cell="{ record }">
                {{ record.avg_response_time !== null ? `${record.avg_response_time.toFixed(2)} ms` : '-' }}
              </template>
            </a-table-column>
          </template>
        </a-table>
      </section>

      <section class="report-card">
        <div class="card-title">集合维度统计</div>
        <a-table :data="report.collection_breakdown" :pagination="false" row-key="request__collection__name" size="small">
          <template #columns>
            <a-table-column title="集合" :width="220">
              <template #cell="{ record }">{{ record.request__collection__name || '未分组' }}</template>
            </a-table-column>
            <a-table-column title="总数" data-index="total" :width="90" />
            <a-table-column title="通过" data-index="passed" :width="90" />
            <a-table-column title="失败" :width="90">
              <template #cell="{ record }">{{ record.failed + record.error }}</template>
            </a-table-column>
          </template>
        </a-table>
      </section>

      <section class="report-card">
        <div class="card-title">高频失败接口</div>
        <a-table :data="report.failing_requests" :pagination="false" row-key="request_name" size="small">
          <template #columns>
            <a-table-column title="接口" data-index="request_name" ellipsis tooltip />
            <a-table-column title="集合" :width="160">
              <template #cell="{ record }">{{ record.request__collection__name || '未分组' }}</template>
            </a-table-column>
            <a-table-column title="失败次数" data-index="total" :width="100" />
            <a-table-column title="最近状态码" data-index="latest_status_code" :width="110" />
          </template>
        </a-table>
      </section>

      <section class="report-card report-card-full">
        <div class="card-title">最近执行记录</div>
        <a-table :data="report.recent_records" :pagination="false" row-key="id" size="small">
          <template #columns>
            <a-table-column title="接口" data-index="request_name" :width="220" ellipsis tooltip />
            <a-table-column title="集合" :width="140">
              <template #cell="{ record }">{{ record.request_collection_name || '-' }}</template>
            </a-table-column>
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
            <a-table-column title="执行时间" :width="180">
              <template #cell="{ record }">{{ formatDate(record.created_at) }}</template>
            </a-table-column>
          </template>
        </a-table>
      </section>
    </div>

    <a-empty v-else-if="!loading" description="暂无测试报告数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { executionRecordApi } from '../api'
import type { ApiExecutionReport } from '../types'

const projectStore = useProjectStore()
const loading = ref(false)
const days = ref(7)
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

const formatDate = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const loadReport = async () => {
  const projectId = projectStore.currentProject?.id
  if (!projectId) {
    report.value = null
    return
  }
  loading.value = true
  try {
    const res = await executionRecordApi.report({ project: projectId, days: days.value })
    report.value = res.data?.data || null
  } catch (error) {
    console.error('[ExecutionReportView] 获取测试报告失败:', error)
    Message.error('获取测试报告失败')
    report.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => projectStore.currentProject?.id,
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
.execution-report-view {
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
  gap: 12px;
  flex-wrap: wrap;
}

.range-label {
  font-size: 13px;
  color: #64748b;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.summary-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card,
.report-card {
  padding: 20px 22px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-card.success {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.12), rgba(255, 255, 255, 0.96));
}

.summary-label {
  font-size: 13px;
  color: #64748b;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.card-title {
  margin-bottom: 14px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.report-card-full {
  grid-column: 1 / -1;
}

@media (max-width: 1100px) {
  .report-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
