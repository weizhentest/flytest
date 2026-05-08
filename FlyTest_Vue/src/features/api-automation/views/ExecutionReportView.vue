<template>
  <div class="execution-report-view">
    <div class="report-hero">
      <div class="report-hero__copy">
        <div class="report-hero__eyebrow">Execution Analytics</div>
        <div class="report-hero__title">执行分析</div>
        <div class="report-hero__desc">
          聚合最近时间范围内的接口执行情况，快速查看通过率、失败热点和最近执行明细。
        </div>
      </div>
      <div class="report-hero__actions">
        <div class="range-selector">
          <span class="range-selector__label">统计范围</span>
          <a-input-number v-model="days" :min="1" :max="90" mode="button" size="large" />
          <span class="range-selector__value">最近 {{ days }} 天</span>
        </div>
        <a-button @click="loadReport">刷新报告</a-button>
      </div>
    </div>

    <div v-if="report" class="report-grid">
      <section class="summary-grid">
        <article class="summary-card summary-card--primary">
          <span class="summary-label">总执行次数</span>
          <strong class="summary-value">{{ report.summary.total_count }}</strong>
          <span class="summary-note">覆盖当前时间窗口内全部接口执行记录</span>
        </article>
        <article class="summary-card summary-card--success">
          <span class="summary-label">通过率</span>
          <strong class="summary-value">{{ report.summary.pass_rate }}%</strong>
          <span class="summary-note">通过 {{ report.summary.passed_count }} 次</span>
        </article>
        <article class="summary-card">
          <span class="summary-label">失败与异常</span>
          <strong class="summary-value">
            {{ report.summary.failed_count + report.summary.error_count }}
          </strong>
          <span class="summary-note">
            失败 {{ report.summary.failed_count }} / 异常 {{ report.summary.error_count }}
          </span>
        </article>
        <article class="summary-card">
          <span class="summary-label">平均响应</span>
          <strong class="summary-value">
            {{ report.summary.avg_response_time !== null ? `${report.summary.avg_response_time.toFixed(2)} ms` : '-' }}
          </strong>
          <span class="summary-note">用于观察近期整体接口响应水平</span>
        </article>
      </section>

      <section class="report-card">
        <div class="card-head">
          <div>
            <div class="card-head__title">请求方法分布</div>
            <div class="card-head__desc">按方法维度查看执行量、失败量和平均响应时长。</div>
          </div>
        </div>
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
        <div class="card-head">
          <div>
            <div class="card-head__title">目录维度统计</div>
            <div class="card-head__desc">定位哪些接口目录在当前周期里最活跃。</div>
          </div>
        </div>
        <a-table :data="report.collection_breakdown" :pagination="false" row-key="request__collection__name" size="small">
          <template #columns>
            <a-table-column title="目录" :width="220">
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
        <div class="card-head">
          <div>
            <div class="card-head__title">高频失败接口</div>
            <div class="card-head__desc">优先处理重复失败次数高的接口。</div>
          </div>
        </div>
        <a-table :data="report.failing_requests" :pagination="false" row-key="request_name" size="small">
          <template #columns>
            <a-table-column title="接口" data-index="request_name" ellipsis tooltip />
            <a-table-column title="目录" :width="160">
              <template #cell="{ record }">{{ record.request__collection__name || '未分组' }}</template>
            </a-table-column>
            <a-table-column title="失败次数" data-index="total" :width="100" />
            <a-table-column title="最近状态码" data-index="latest_status_code" :width="110" />
          </template>
        </a-table>
      </section>

      <section class="report-card report-card-full">
        <div class="card-head">
          <div>
            <div class="card-head__title">最近执行记录</div>
            <div class="card-head__desc">展示最近一批接口执行结果，便于直接追踪。</div>
          </div>
        </div>
        <a-table :data="report.recent_records" :pagination="false" row-key="id" size="small">
          <template #columns>
            <a-table-column title="接口" data-index="request_name" :width="220" ellipsis tooltip />
            <a-table-column title="目录" :width="140">
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
                  {{ record.passed ? '通过' : record.status === 'error' ? '异常' : '失败' }}
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

    <div v-else-if="loading" class="state-card">
      <a-spin size="large" />
    </div>

    <div v-else class="state-card">
      <a-empty description="暂无测试报告数据" />
    </div>
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

.report-hero {
  display: grid;
  grid-template-columns: minmax(280px, 1.1fr) minmax(300px, 0.9fr);
  gap: 22px;
  align-items: end;
  padding: 26px 28px;
  border-radius: 28px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(248, 250, 252, 0.92));
  box-shadow: 0 20px 44px rgba(15, 23, 42, 0.08);
}

.report-hero__copy,
.report-hero__actions,
.range-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
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
  line-height: 1.06;
  color: #0f172a;
}

.report-hero__desc {
  max-width: 720px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.report-hero__actions {
  justify-content: flex-end;
  align-items: center;
}

.range-selector {
  align-items: center;
  padding: 12px 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.range-selector__label,
.range-selector__value {
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
.report-card,
.state-card {
  border-radius: 26px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.summary-card,
.report-card {
  padding: 22px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-card--primary {
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.16), rgba(14, 165, 233, 0.1)),
    rgba(255, 255, 255, 0.96);
}

.summary-card--success {
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.16), rgba(16, 185, 129, 0.08)),
    rgba(255, 255, 255, 0.96);
}

.summary-label {
  font-size: 13px;
  color: #64748b;
}

.summary-value {
  font-size: 30px;
  font-weight: 800;
  color: #0f172a;
}

.summary-note {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.card-head__title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.card-head__desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.report-card-full {
  grid-column: 1 / -1;
}

.report-card :deep(.arco-table-container) {
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.state-card {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

@media (max-width: 1200px) {
  .report-hero,
  .report-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .report-hero__actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .report-hero {
    padding: 22px 20px;
  }

  .report-hero__title {
    font-size: 26px;
  }

  .range-selector {
    width: 100%;
  }
}
</style>
