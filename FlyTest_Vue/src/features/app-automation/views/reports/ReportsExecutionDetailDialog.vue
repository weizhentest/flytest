<template>
  <a-modal
    v-model:visible="visibleModel"
    title="执行详情"
    width="960px"
    :footer="false"
  >
    <div v-if="currentExecution" class="detail-shell">
      <div class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">执行状态</span>
          <strong>{{ getExecutionStatus(currentExecution).label }}</strong>
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
          {{ currentExecution.report_summary || currentExecution.error_message || '暂无执行摘要。' }}
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
        </a-space>
      </a-card>

      <a-card class="detail-panel" title="步骤统计">
        <div class="metric-row">
          <div class="metric-chip success-chip">通过 {{ currentExecution.passed_steps || 0 }}</div>
          <div class="metric-chip danger-chip">失败 {{ currentExecution.failed_steps || 0 }}</div>
          <div class="metric-chip neutral-chip">总计 {{ currentExecution.total_steps || 0 }}</div>
          <div class="metric-chip neutral-chip">进度 {{ formatRate(currentExecution.progress) }}%</div>
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
        <a-textarea
          :model-value="executionLogText"
          :auto-size="{ minRows: 12, maxRows: 20 }"
          readonly
        />
      </a-card>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { ReportsExecutionDetailDialogEmits } from './reportEventModels'
import type { ReportsExecutionDetailDialogProps } from './reportViewModels'

defineProps<ReportsExecutionDetailDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<ReportsExecutionDetailDialogEmits>()
</script>

<style scoped>
.detail-shell {
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

.detail-card strong {
  color: var(--theme-text);
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

.detail-label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--theme-text-secondary);
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
  font-size: 13px;
  color: var(--theme-text-secondary);
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

.empty-note {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-secondary);
}

.empty-note.compact {
  min-height: 0;
  justify-content: flex-start;
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
}
</style>
