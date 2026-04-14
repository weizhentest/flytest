<template>
  <a-modal
    v-model:visible="visibleModel"
    title="执行详情"
    width="980px"
    :footer="false"
  >
    <div v-if="detailLoading" class="modal-state">正在加载执行详情...</div>
    <div v-else-if="currentExecution" class="detail-shell">
      <div class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">执行状态</span>
          <strong>{{ getExecutionStatusMeta(currentExecution).label }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">执行来源</span>
          <strong>{{ getExecutionSource(currentExecution) }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">步骤通过率</span>
          <strong>{{ formatRate(currentExecution.pass_rate) }}%</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">执行耗时</span>
          <strong>{{ formatDuration(currentExecution.duration) }}</strong>
        </div>
      </div>

      <a-card class="detail-panel" title="执行摘要">
        <div class="summary-text">
          {{ currentExecution.report_summary || currentExecution.error_message || '暂无执行摘要，可继续查看日志定位运行细节。' }}
        </div>
        <div class="meta-row">
          <span>用例：{{ currentExecution.case_name || `执行 #${currentExecution.id}` }}</span>
          <span>设备：{{ currentExecution.device_name || currentExecution.device_serial || '-' }}</span>
          <span>触发方式：{{ currentExecution.trigger_mode || '-' }}</span>
          <span>触发人：{{ currentExecution.triggered_by || '-' }}</span>
          <span>开始时间：{{ formatDateTime(currentExecution.started_at || currentExecution.created_at) }}</span>
          <span>结束时间：{{ formatDateTime(currentExecution.finished_at) }}</span>
        </div>
        <a-space wrap>
          <a-button
            v-if="canOpenReport(currentExecution)"
            type="primary"
            @click="emit('open-report', currentExecution)"
          >
            打开执行报告
          </a-button>
          <a-button
            v-if="isExecutionRunning(currentExecution)"
            status="danger"
            :loading="Boolean(stoppingIds[currentExecution.id])"
            @click="emit('stop-execution', currentExecution)"
          >
            停止执行
          </a-button>
        </a-space>
      </a-card>

      <a-card class="detail-panel" title="步骤统计与诊断">
        <div class="metric-row">
          <div class="metric-chip success-chip">通过 {{ currentExecution.passed_steps || 0 }}</div>
          <div class="metric-chip danger-chip">失败 {{ currentExecution.failed_steps || 0 }}</div>
          <div class="metric-chip neutral-chip">总计 {{ currentExecution.total_steps || 0 }}</div>
          <div class="metric-chip neutral-chip">进度 {{ formatProgress(currentExecution.progress) }}%</div>
        </div>
        <a-alert v-if="currentExecution.error_message" type="error" class="detail-alert">
          {{ currentExecution.error_message }}
        </a-alert>
      </a-card>

      <a-card class="detail-panel" title="执行证据">
        <div v-if="executionArtifacts.length" class="artifact-list">
          <div v-for="item in executionArtifacts" :key="item.key" class="artifact-item">
            <div class="artifact-meta">
              <a-tag :color="item.level === 'error' ? 'red' : item.level === 'warning' ? 'orange' : 'arcoblue'">
                {{ item.level }}
              </a-tag>
              <span>{{ item.message }}</span>
            </div>
            <a-button type="text" @click="emit('open-artifact', currentExecution, item.relativePath)">查看文件</a-button>
          </div>
        </div>
        <div v-else class="empty-note compact">当前执行暂无可查看的证据文件</div>
      </a-card>

      <a-card class="detail-panel" title="执行日志">
        <div v-if="currentExecution.logs?.length" class="log-list">
          <div v-for="(log, index) in currentExecution.logs" :key="`${log.timestamp}-${index}`" class="log-item">
            <div class="log-meta">
              <span>{{ formatDateTime(log.timestamp) }}</span>
              <a-tag size="small" :color="getLogLevelColor(log.level)">{{ log.level || 'info' }}</a-tag>
            </div>
            <div class="log-message">{{ log.message || '-' }}</div>
          </div>
        </div>
        <div v-else class="modal-state compact">暂无执行日志</div>
      </a-card>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { AppExecution } from '../../types'

interface ExecutionStatusMeta {
  label: string
  color: string
  hex: string
}

interface ExecutionArtifact {
  key: string
  relativePath: string
  message: string
  level: string
}

interface Props {
  detailLoading: boolean
  currentExecution: AppExecution | null
  executionArtifacts: ExecutionArtifact[]
  stoppingIds: Record<number, boolean>
  formatDateTime: (value?: string | null) => string
  formatDuration: (value?: number | null) => string
  formatRate: (value?: number | null) => number
  formatProgress: (value?: number | null) => number
  getExecutionSource: (record: AppExecution) => string
  getExecutionStatusMeta: (record: AppExecution) => ExecutionStatusMeta
  getLogLevelColor: (value?: string) => string
  canOpenReport: (record: AppExecution) => boolean
  isExecutionRunning: (record: AppExecution) => boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  'open-report': [record: AppExecution]
  'stop-execution': [record: AppExecution]
  'open-artifact': [record: AppExecution, relativePath: string]
}>()
</script>

<style scoped>
.modal-state,
.empty-note {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
  color: var(--theme-text-secondary);
}

.modal-state.compact,
.empty-note.compact {
  min-height: 120px;
}

.detail-shell,
.log-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-card strong,
.log-message {
  color: var(--theme-text);
}

.detail-label,
.meta-row,
.log-meta {
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.detail-label {
  display: block;
  margin-bottom: 8px;
}

.summary-text {
  color: var(--theme-text);
  line-height: 1.7;
  margin-bottom: 14px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-bottom: 14px;
}

.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.metric-chip {
  padding: 10px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.success-chip {
  background: rgba(76, 175, 80, 0.12);
  color: #4caf50;
}

.danger-chip {
  background: rgba(244, 67, 54, 0.12);
  color: #f44336;
}

.neutral-chip {
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: var(--theme-text);
}

.detail-alert {
  margin-top: 14px;
}

.artifact-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.artifact-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.artifact-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--theme-text);
}

.log-item {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.log-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.log-message {
  line-height: 1.7;
  word-break: break-word;
}

@media (max-width: 1280px) {
  .detail-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .artifact-item {
    justify-content: flex-start;
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
