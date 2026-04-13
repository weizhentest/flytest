<template>
  <a-drawer
    :visible="visible"
    title="AI 执行详情"
    width="820px"
    unmount-on-close
    @update:visible="emit('update:visible', $event)"
  >
    <a-spin :loading="loading" style="width: 100%">
      <template v-if="record">
        <div class="drawer-actions">
          <a-space>
            <a-button type="outline" size="small" @click="emit('open-report', record.id)">
              <template #icon><icon-file /></template>
              查看报告
            </a-button>
            <a-button
              v-if="isRunningStatus(record.status)"
              type="outline"
              size="small"
              status="warning"
              @click="emit('stop-record', record.id)"
            >
              <template #icon><icon-stop /></template>
              停止任务
            </a-button>
          </a-space>
        </div>
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="任务名称">{{ record.case_name }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ record.executed_by_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行模式">
            <a-tag :color="modeColors[record.execution_mode]">{{ AI_MODE_LABELS[record.execution_mode] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="执行后端">
            <a-tag :color="backendColors[record.execution_backend]">{{ AI_BACKEND_LABELS[record.execution_backend] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="statusColors[record.status]">{{ AI_STATUS_LABELS[record.status] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="模型配置">{{ record.model_config_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="GIF 录制">{{ record.enable_gif ? '已开启' : '已关闭' }}</a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ formatTime(record.start_time) }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ record.end_time ? formatTime(record.end_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行时长">{{ record.duration != null ? `${record.duration.toFixed(2)}s` : '-' }}</a-descriptions-item>
          <a-descriptions-item label="任务进度">{{ formatProgress(record) }}</a-descriptions-item>
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
        <div class="block-card">{{ record.task_description }}</div>
        <template v-if="record.error_message">
          <a-divider>错误信息</a-divider>
          <a-alert type="error" :title="record.error_message" />
        </template>
        <template v-if="record.planned_tasks?.length">
          <a-divider>规划任务</a-divider>
          <div class="item-list">
            <div v-for="task in record.planned_tasks" :key="task.id" class="item-card">
              <div class="item-head">
                <span class="item-title">{{ task.title }}</span>
                <a-tag :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</a-tag>
              </div>
              <div class="item-desc">{{ task.description }}</div>
              <div v-if="task.expected_result" class="item-meta">预期结果：{{ task.expected_result }}</div>
            </div>
          </div>
        </template>
        <template v-if="record.steps_completed?.length">
          <a-divider>已完成步骤</a-divider>
          <div class="item-list">
            <div
              v-for="step in record.steps_completed"
              :key="`${step.step}-${step.completed_at}`"
              class="item-card"
            >
              <div class="item-head">
                <span class="item-title">步骤 {{ step.step }} - {{ step.title }}</span>
                <a-tag :color="stepStatusColor(step.status)">{{ stepStatusLabel(step.status) }}</a-tag>
              </div>
              <div class="item-desc">{{ step.description || '-' }}</div>
              <div v-if="step.expected_result" class="item-meta"><strong>预期结果：</strong>{{ step.expected_result }}</div>
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
                      :key="`${step.step}-${item}-${index}`"
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
        </template>
        <template v-if="record.screenshots_sequence?.length">
          <a-divider>执行截图</a-divider>
          <a-image-preview-group>
            <div class="media-grid">
              <a-image
                v-for="(item, index) in record.screenshots_sequence"
                :key="`${item}-${index}`"
                :src="resolveMediaUrl(item)"
                width="168"
                height="108"
                fit="cover"
              />
            </div>
          </a-image-preview-group>
        </template>
        <template v-if="record.gif_path">
          <a-divider>执行回放</a-divider>
          <div class="gif-preview"><img :src="resolveMediaUrl(record.gif_path)" alt="AI execution replay" /></div>
        </template>
        <template v-if="record.logs">
          <a-divider>执行日志</a-divider>
          <pre class="log-panel">{{ record.logs }}</pre>
        </template>
      </template>
    </a-spin>
  </a-drawer>
</template>

<script setup lang="ts">
import { AI_BACKEND_LABELS, AI_MODE_LABELS, AI_STATUS_LABELS, type UiAIExecutionBackend, type UiAIExecutionMode, type UiAIExecutionRecord, type UiAIExecutionStatus } from '../types'

type StatusAlert = {
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  content: string
} | null

const props = defineProps<{
  visible: boolean
  loading: boolean
  record: UiAIExecutionRecord | null
  statusAlert: StatusAlert
  statusColors: Record<UiAIExecutionStatus, string>
  modeColors: Record<UiAIExecutionMode, string>
  backendColors: Record<UiAIExecutionBackend, string>
  formatTime: (value?: string) => string
  formatDuration: (value?: number) => string
  formatProgress: (record: Pick<UiAIExecutionRecord, 'planned_task_count' | 'completed_task_count' | 'planned_tasks' | 'steps_completed'>) => string
  taskStatusColor: (status: string) => string
  taskStatusLabel: (status: string) => string
  stepStatusColor: (status: string) => string
  stepStatusLabel: (status: string) => string
  resolveMediaUrl: (value?: string) => string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'open-report', id: number): void
  (e: 'stop-record', id: number): void
}>()

const isRunningStatus = (status: UiAIExecutionStatus) => status === 'running' || status === 'pending'

const {
  statusColors,
  modeColors,
  backendColors,
  formatTime,
  formatDuration,
  formatProgress,
  taskStatusColor,
  taskStatusLabel,
  stepStatusColor,
  stepStatusLabel,
  resolveMediaUrl,
} = props
</script>

<style scoped>
.drawer-actions,
.status-alert {
  margin-bottom: 16px;
}

.block-card,
.item-card {
  border-radius: 10px;
}

.block-card {
  padding: 12px 14px;
  background: var(--color-fill-2);
  color: var(--color-text-1);
  line-height: 1.6;
  white-space: pre-wrap;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.item-card {
  padding: 14px;
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

.item-desc,
.item-meta {
  color: var(--color-text-1);
  line-height: 1.6;
}

.item-meta {
  margin-top: 8px;
  color: var(--color-text-3);
  font-size: 12px;
}

.step-media {
  margin-top: 12px;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 12px;
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
</style>
