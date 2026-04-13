<template>
  <a-modal
    :visible="visible"
    title="AI 执行报告"
    width="920px"
    :footer="false"
    unmount-on-close
    @update:visible="emit('update:visible', $event)"
  >
    <a-spin :loading="loading" style="width: 100%">
      <template v-if="report">
        <div class="report-toolbar">
          <a-radio-group :model-value="reportType" type="button" size="small" @change="emit('change-report-type', $event)">
            <a-radio v-for="option in reportTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</a-radio>
          </a-radio-group>
          <a-space>
            <a-button type="outline" size="small" :loading="exporting" @click="emit('export')">
              <template #icon><icon-file /></template>
              导出 PDF
            </a-button>
            <a-button type="outline" size="small" @click="emit('reload')">
              <template #icon><icon-refresh /></template>
              刷新报告
            </a-button>
          </a-space>
        </div>
        <div class="report-summary">
          <div v-for="item in reportStats" :key="item.label" class="summary-card">
            <span class="summary-label">{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="任务名称">{{ report.case_name }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="statusColors[report.status]">{{ AI_STATUS_LABELS[report.status] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="执行模式">
            <a-tag :color="modeColors[report.execution_mode]">{{ AI_MODE_LABELS[report.execution_mode] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="执行后端">
            <a-tag :color="backendColors[report.execution_backend]">{{ AI_BACKEND_LABELS[report.execution_backend] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="模型配置">{{ report.model_config_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行时长">{{ formatDuration(report.duration) }}</a-descriptions-item>
        </a-descriptions>
        <a-alert
          v-if="statusAlert"
          class="status-alert"
          :type="statusAlert.type"
          show-icon
          :title="statusAlert.title"
        >
          {{ statusAlert.content }}
        </a-alert>
        <a-divider>任务描述</a-divider>
        <div class="block-card">{{ report.task_description }}</div>
        <template v-if="reportType === 'summary'">
          <template v-if="overviewCards.length">
            <a-divider>执行概览</a-divider>
            <div class="metric-grid">
              <div v-for="item in overviewCards" :key="item.label" class="metric-card">
                <span class="summary-label">{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </template>
          <template v-if="report.timeline?.length">
            <a-divider>任务时间线</a-divider>
            <div class="timeline-list">
              <div v-for="item in report.timeline" :key="item.id" class="timeline-card">
                <div class="item-head">
                  <span class="item-title">{{ item.title }}</span>
                  <a-tag :color="taskStatusColor(item.status)">{{ item.status_display }}</a-tag>
                </div>
                <div class="item-desc">{{ item.description || '-' }}</div>
                <div v-if="item.expected_result" class="item-meta">预期结果：{{ item.expected_result }}</div>
              </div>
            </div>
          </template>
          <template v-if="report.planned_tasks?.length">
            <a-divider>规划任务</a-divider>
            <div class="item-list">
              <div v-for="task in report.planned_tasks" :key="task.id" class="item-card">
                <div class="item-head">
                  <span class="item-title">{{ task.title }}</span>
                  <a-tag :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</a-tag>
                </div>
                <div class="item-desc">{{ task.description }}</div>
                <div v-if="task.expected_result" class="item-meta">预期结果：{{ task.expected_result }}</div>
              </div>
            </div>
          </template>
          <template v-if="reportActionDistribution.length">
            <a-divider>动作分布</a-divider>
            <div class="distribution-list">
              <div v-for="item in reportActionDistribution" :key="item.action" class="distribution-item">
                <span class="distribution-label">{{ item.action }}</span>
                <div class="distribution-bar">
                  <div class="distribution-bar__fill" :style="{ width: `${distributionWidth(item.count)}%` }" />
                </div>
                <strong class="distribution-count">{{ item.count }}</strong>
              </div>
            </div>
          </template>
          <template v-if="report.error_message">
            <a-divider>错误信息</a-divider>
            <a-alert type="error" :title="report.error_message" />
          </template>
        </template>
        <template v-else-if="reportType === 'detailed'">
          <template v-if="reportErrors.length">
            <a-divider>错误信息</a-divider>
            <div class="error-list">
              <a-alert
                v-for="(item, index) in reportErrors"
                :key="`${item.message}-${index}`"
                :title="item.step_number ? `步骤 ${item.step_number}：${item.message}` : item.message"
                type="error"
              />
            </div>
          </template>
          <a-divider>步骤明细</a-divider>
          <div v-if="detailedSteps.length" class="item-list">
            <div v-for="step in detailedSteps" :key="step.step_number" class="item-card">
              <div class="item-head">
                <span class="item-title">步骤 {{ step.step_number }} - {{ step.title }}</span>
                <a-tag :color="stepStatusColor(step.status)">{{ stepStatusLabel(step.status) }}</a-tag>
              </div>
              <div class="item-desc"><strong>动作：</strong>{{ step.action || '-' }}</div>
              <div class="item-meta"><strong>描述：</strong>{{ step.description || '-' }}</div>
              <div v-if="step.expected_result" class="item-meta"><strong>预期结果：</strong>{{ step.expected_result }}</div>
              <div v-if="step.element" class="item-meta"><strong>元素：</strong>{{ step.element }}</div>
              <div v-if="step.thinking" class="item-meta"><strong>AI 思考：</strong>{{ step.thinking }}</div>
              <div v-if="step.message" class="item-meta"><strong>执行信息：</strong>{{ step.message }}</div>
              <div v-if="step.browser_step_count" class="item-meta"><strong>浏览器步骤：</strong>{{ step.browser_step_count }}</div>
              <div class="item-meta">
                <strong>耗时：</strong>{{ formatDuration(step.duration) }}
                <span v-if="step.completed_at"> - {{ formatTime(step.completed_at) }}</span>
              </div>
              <div v-if="step.screenshots?.length" class="step-media">
                <a-image-preview-group>
                  <div class="media-grid">
                    <a-image
                      v-for="(item, index) in step.screenshots"
                      :key="`${step.step_number}-${item}-${index}`"
                      :src="resolveMediaUrl(item)"
                      width="168"
                      height="108"
                      fit="cover"
                    />
                  </div>
                </a-image-preview-group>
              </div>
            </div>
          </div>
          <a-empty v-else description="暂无步骤明细" />
        </template>
        <template v-else>
          <template v-if="performanceCards.length">
            <a-divider>性能指标</a-divider>
            <div class="metric-grid">
              <div v-for="item in performanceCards" :key="item.label" class="metric-card">
                <span class="summary-label">{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </template>
          <template v-if="reportActionDistribution.length">
            <a-divider>动作分布</a-divider>
            <div class="distribution-list">
              <div v-for="item in reportActionDistribution" :key="item.action" class="distribution-item">
                <span class="distribution-label">{{ item.action }}</span>
                <div class="distribution-bar">
                  <div class="distribution-bar__fill" :style="{ width: `${distributionWidth(item.count)}%` }" />
                </div>
                <strong class="distribution-count">{{ item.count }}</strong>
              </div>
            </div>
          </template>
          <template v-if="report.bottlenecks?.length">
            <a-divider>性能瓶颈</a-divider>
            <div class="item-list">
              <div v-for="item in report.bottlenecks" :key="`${item.step_number}-${item.action}`" class="item-card">
                <div class="item-head">
                  <span class="item-title">步骤 {{ item.step_number }} - {{ item.action }}</span>
                  <a-tag color="orange">{{ item.duration.toFixed(2) }}s</a-tag>
                </div>
                <div class="item-meta">高于平均耗时 {{ item.slower_than_avg_by.toFixed(2) }}%</div>
              </div>
            </div>
          </template>
          <template v-if="report.recommendations?.length">
            <a-divider>优化建议</a-divider>
            <div class="error-list">
              <a-alert v-for="(item, index) in report.recommendations" :key="`${item}-${index}`" :title="item" type="info" />
            </div>
          </template>
        </template>
        <template v-if="report.screenshots_sequence?.length">
          <a-divider>执行截图</a-divider>
          <a-image-preview-group>
            <div class="media-grid">
              <a-image
                v-for="(item, index) in report.screenshots_sequence"
                :key="`${item}-${index}`"
                :src="resolveMediaUrl(item)"
                width="168"
                height="108"
                fit="cover"
              />
            </div>
          </a-image-preview-group>
        </template>
        <template v-if="report.gif_path">
          <a-divider>执行回放</a-divider>
          <div class="gif-preview"><img :src="resolveMediaUrl(report.gif_path)" alt="AI execution replay" /></div>
        </template>
        <template v-if="report.logs">
          <a-divider>执行日志</a-divider>
          <pre class="log-panel">{{ report.logs }}</pre>
        </template>
      </template>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  AI_BACKEND_LABELS,
  AI_MODE_LABELS,
  AI_STATUS_LABELS,
  type UiAIExecutionBackend,
  type UiAIExecutionMode,
  type UiAIExecutionReport,
  type UiAIExecutionStatus,
  type UiAIReportDetailedStep,
  type UiAIReportError,
  type UiAIReportType,
} from '../types'

type StatusAlert = {
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  content: string
} | null

type SummaryItem = {
  label: string
  value: string | number
}

const props = defineProps<{
  visible: boolean
  loading: boolean
  exporting: boolean
  report: UiAIExecutionReport | null
  reportType: UiAIReportType
  reportTypeOptions: Array<{ label: string; value: UiAIReportType }>
  reportStats: SummaryItem[]
  statusAlert: StatusAlert
  overviewCards: SummaryItem[]
  performanceCards: SummaryItem[]
  reportErrors: UiAIReportError[]
  detailedSteps: UiAIReportDetailedStep[]
  reportActionDistribution: Array<{ action: string; count: number }>
  statusColors: Record<UiAIExecutionStatus, string>
  modeColors: Record<UiAIExecutionMode, string>
  backendColors: Record<UiAIExecutionBackend, string>
  formatTime: (value?: string) => string
  formatDuration: (value?: number) => string
  resolveMediaUrl: (value?: string) => string
  taskStatusColor: (status: string) => string
  taskStatusLabel: (status: string) => string
  stepStatusColor: (status: string) => string
  stepStatusLabel: (status: string) => string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'reload'): void
  (e: 'export'): void
  (e: 'change-report-type', value: string | number | boolean): void
}>()

const {
  reportType,
  reportStats,
  overviewCards,
  performanceCards,
  reportErrors,
  detailedSteps,
  reportActionDistribution,
  statusColors,
  modeColors,
  backendColors,
  formatTime,
  formatDuration,
  resolveMediaUrl,
  taskStatusColor,
  taskStatusLabel,
  stepStatusColor,
  stepStatusLabel,
} = props

const distributionWidth = computed(() => {
  const counts = reportActionDistribution.map(item => item.count)
  const max = counts.length ? Math.max(...counts) : 1
  return (count: number) => (max > 0 ? (count / max) * 100 : 0)
})
</script>

<style scoped>
.report-toolbar,
.status-alert {
  margin-bottom: 16px;
}

.report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.report-summary,
.metric-grid,
.media-grid {
  display: grid;
  gap: 12px;
}

.report-summary,
.metric-grid {
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  margin-bottom: 16px;
}

.media-grid {
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
}

.summary-card,
.metric-card,
.block-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--color-fill-2);
}

.summary-card strong,
.metric-card strong {
  display: block;
  margin-top: 6px;
  font-size: 22px;
  color: var(--color-text-1);
}

.summary-label,
.item-meta {
  margin-top: 8px;
  color: var(--color-text-3);
  font-size: 12px;
}

.block-card,
.item-desc {
  color: var(--color-text-1);
  line-height: 1.6;
  white-space: pre-wrap;
}

.item-list,
.timeline-list,
.error-list,
.distribution-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.item-card,
.timeline-card {
  padding: 14px;
  border-radius: 10px;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-2);
}

.item-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.item-title {
  font-weight: 600;
  color: var(--color-text-1);
}

.distribution-item {
  display: grid;
  grid-template-columns: 72px 1fr 40px;
  align-items: center;
  gap: 12px;
}

.distribution-label,
.distribution-count {
  color: var(--color-text-1);
}

.distribution-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--color-fill-2);
  overflow: hidden;
}

.distribution-bar__fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #165dff, #36cfc9);
}

.step-media {
  margin-top: 12px;
}

.gif-preview {
  overflow: hidden;
  border-radius: 10px;
  border: 1px solid var(--color-border-2);
  background: var(--color-fill-1);
}

.gif-preview img {
  display: block;
  width: 100%;
  max-height: 360px;
  object-fit: contain;
}

.log-panel {
  margin: 0;
  padding: 14px;
  border-radius: 8px;
  background: var(--color-fill-2);
  color: var(--color-text-1);
  font-size: 12px;
  line-height: 1.6;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 768px) {
  .report-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .distribution-item {
    grid-template-columns: 1fr;
  }
}
</style>
