<template>
  <a-modal
    v-model:visible="visibleModel"
    title="执行详情"
    width="920px"
    :footer="false"
  >
    <div v-if="currentExecution" class="detail-shell">
      <div class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">执行状态</span>
          <strong>{{ getExecutionStatusMeta(currentExecution).label }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">通过率</span>
          <strong>{{ formatRate(currentExecution.pass_rate) }}%</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">步骤统计</span>
          <strong>{{ currentExecution.passed_steps || 0 }}/{{ currentExecution.total_steps || 0 }}</strong>
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
          <span>触发人：{{ currentExecution.triggered_by || '-' }}</span>
          <span>触发方式：{{ currentExecution.trigger_mode || '-' }}</span>
          <span>开始时间：{{ formatDateTime(currentExecution.started_at || currentExecution.created_at) }}</span>
          <span>结束时间：{{ formatDateTime(currentExecution.finished_at) }}</span>
        </div>
        <a-space wrap>
          <a-button v-if="canOpenReport(currentExecution)" type="primary" @click="emit('open-report', currentExecution)">
            打开执行报告
          </a-button>
          <a-button @click="emit('open-workspace', currentExecution.id, currentExecution.test_suite_id || selectedSuiteId || null)">
            在执行记录页打开
          </a-button>
        </a-space>
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
        <div v-else class="empty-note">暂无执行日志</div>
      </a-card>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { AppExecution } from '../../types'

interface StatusMeta {
  label: string
  color: string
}

interface ExecutionArtifact {
  key: string
  relativePath: string
  message: string
  level: string
}

interface Props {
  currentExecution: AppExecution | null
  selectedSuiteId: number | null
  executionArtifacts: ExecutionArtifact[]
  formatDateTime: (value?: string | null) => string
  formatRate: (value?: number | null) => number
  formatDuration: (value?: number | null) => string
  getExecutionStatusMeta: (record: AppExecution) => StatusMeta
  canOpenReport: (record: AppExecution) => boolean
  getLogLevelColor: (value?: string) => string
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  'open-report': [record: AppExecution]
  'open-workspace': [executionId?: number, suiteId?: number | null]
  'open-artifact': [record: AppExecution, relativePath: string]
}>()
</script>

<style scoped>
.detail-shell,
.artifact-list,
.log-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.detail-card,
.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.detail-label,
.meta-row,
.log-meta {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.detail-card strong,
.artifact-meta,
.log-message {
  color: var(--theme-text);
}

.summary-text {
  color: var(--theme-text);
  line-height: 1.7;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-top: 12px;
}

.artifact-item,
.log-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.artifact-item {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.14);
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.artifact-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.log-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.empty-note {
  color: var(--theme-text-secondary);
}

.empty-note.compact {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed rgba(var(--theme-accent-rgb), 0.14);
  border-radius: 14px;
}

@media (max-width: 1200px) {
  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .artifact-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
