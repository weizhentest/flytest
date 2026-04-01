<template>
  <div v-if="showBadge || importTaskVisible" class="import-job-status">
    <button type="button" class="import-job-badge" @click="importTaskVisible = true">
      <span class="import-job-dot" :class="`is-${badgeTone}`"></span>
      <span class="import-job-title">{{ badgeTitle }}</span>
      <span v-if="activeCount" class="import-job-count">{{ activeCount }}</span>
    </button>

    <a-drawer v-model:visible="importTaskVisible" width="440px" title="文档解析状态" :footer="false">
      <div class="import-task-drawer">
        <a-alert v-if="activeImportJobs.length" type="info" class="import-task-alert">
          <template #title>关闭这个面板不会中断后台解析</template>
          任务会在服务端继续执行，完成后系统会自动通知你。
        </a-alert>

        <a-empty v-if="!visibleImportJobs.length" description="当前没有需要关注的解析任务" />

        <div v-else class="import-task-list">
          <div v-for="job in visibleImportJobs" :key="job.id" class="import-task-card">
            <div class="import-task-head">
              <div class="import-task-name">{{ job.source_name }}</div>
              <div class="import-task-head-actions">
                <a-tag :color="getJobStatusColor(job)">
                  {{ getJobStatusLabel(job) }}
                </a-tag>
                <a-button
                  v-if="canCancel(job)"
                  type="text"
                  size="mini"
                  status="danger"
                  @click="handleCancel(job)"
                >
                  停止解析
                </a-button>
              </div>
            </div>
            <div class="import-task-desc">{{ job.progress_message || '正在准备解析接口文档。' }}</div>
            <div class="import-task-progress">
              <a-progress :percent="Math.max(0, Math.min(job.progress_percent, 100)) / 100" :show-text="false" />
              <span class="import-task-progress-text">{{ Math.max(0, Math.min(job.progress_percent, 100)) }}%</span>
            </div>
            <div class="import-task-steps">
              <div
                v-for="step in importTaskSteps"
                :key="`${job.id}-${step.key}`"
                class="import-task-step"
                :class="`is-${getTaskStepState(job, step.key)}`"
              >
                <span class="import-task-step-dot"></span>
                <span class="import-task-step-label">{{ step.title }}</span>
              </div>
            </div>
            <div v-if="job.status === 'failed' && job.error_message" class="import-task-error">
              失败原因：{{ job.error_message }}
            </div>
          </div>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { useApiImportJobs } from '../state/importJobs'
import type { ApiImportJob } from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const { activeImportJobs, recentImportJobs, importTaskVisible, syncProject, cancelImportJob } = useApiImportJobs()

const importTaskSteps = [
  { key: 'uploaded', title: '文档已上传' },
  { key: 'queued', title: '进入后台队列' },
  { key: 'rule_parse', title: '规则解析' },
  { key: 'ai_parse', title: 'AI增强解析' },
  { key: 'save_requests', title: '写入接口' },
  { key: 'generate_cases', title: '生成脚本与用例' },
  { key: 'completed', title: '完成' },
]

const activeCount = computed(() => activeImportJobs.value.length)
const failedJobs = computed(() => recentImportJobs.value.filter(job => job.status === 'failed').slice(0, 4))
const canceledJobs = computed(() => recentImportJobs.value.filter(job => job.status === 'canceled').slice(0, 4))
const visibleImportJobs = computed(() => {
  const activeIds = new Set(activeImportJobs.value.map(job => job.id))
  const merged = [
    ...activeImportJobs.value,
    ...failedJobs.value.filter(job => !activeIds.has(job.id)),
    ...canceledJobs.value.filter(job => !activeIds.has(job.id)),
  ]
  return merged.slice(0, 8)
})

const showBadge = computed(() => activeImportJobs.value.length > 0 || failedJobs.value.length > 0 || canceledJobs.value.length > 0)
const badgeTone = computed(() => {
  if (failedJobs.value.length > 0 && activeImportJobs.value.length === 0) return 'error'
  if (canceledJobs.value.length > 0 && activeImportJobs.value.length === 0) return 'idle'
  return activeImportJobs.value.length > 0 ? 'active' : 'idle'
})
const badgeTitle = computed(() => {
  if (failedJobs.value.length > 0 && activeImportJobs.value.length === 0) {
    return '文档解析异常'
  }
  if (canceledJobs.value.length > 0 && activeImportJobs.value.length === 0) {
    return '文档解析已停止'
  }
  if (activeImportJobs.value.length > 1) {
    return `文档解析中 ${activeImportJobs.value.length} 项`
  }
  if (activeImportJobs.value.length === 1) {
    return '文档解析中'
  }
  return '文档解析'
})

const getJobStatusColor = (job: ApiImportJob) => {
  if (job.status === 'success') return 'green'
  if (job.status === 'failed') return 'red'
  if (job.status === 'canceled') return 'gray'
  if (job.cancel_requested) return 'orange'
  if (job.status === 'running') return 'arcoblue'
  return 'gold'
}

const getJobStatusLabel = (job: ApiImportJob) => {
  if (job.status === 'success') return '已完成'
  if (job.status === 'failed') return '已失败'
  if (job.status === 'canceled') return '已停止'
  if (job.cancel_requested) return '停止中'
  if (job.status === 'running') return '解析中'
  return '排队中'
}

const canCancel = (job: ApiImportJob) => {
  return (job.status === 'pending' || job.status === 'running') && !job.cancel_requested
}

const handleCancel = async (job: ApiImportJob) => {
  try {
    await cancelImportJob(job.id)
    Message.success('已发送停止解析请求')
  } catch (error) {
    console.error('[ImportJobStatusBadge] 停止解析失败:', error)
    Message.error('停止解析失败')
  }
}

const getTaskStepState = (job: ApiImportJob, stepKey: string) => {
  const sequence = importTaskSteps.map(item => item.key)
  const currentIndex = sequence.indexOf(job.progress_stage || '')
  const targetIndex = sequence.indexOf(stepKey)

  if (job.status === 'failed') {
    if (stepKey === job.progress_stage) return 'failed'
    if (targetIndex !== -1 && currentIndex !== -1 && targetIndex < currentIndex) return 'finished'
    return 'pending'
  }

  if (job.status === 'canceled') {
    if (targetIndex !== -1 && currentIndex !== -1 && targetIndex < currentIndex) return 'finished'
    if (stepKey === 'canceled' || stepKey === job.progress_stage) return 'failed'
    return 'pending'
  }

  if (job.status === 'success') {
    return 'finished'
  }

  if (stepKey === job.progress_stage) return 'active'
  if (targetIndex !== -1 && currentIndex !== -1 && targetIndex < currentIndex) return 'finished'
  return 'pending'
}

watch(
  () => projectId.value,
  value => {
    syncProject(value)
  },
  { immediate: true }
)
</script>

<style scoped>
.import-job-status {
  display: inline-flex;
  align-items: center;
}

.import-job-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: var(--theme-text-secondary);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.import-job-badge:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.14);
  border-color: rgba(59, 130, 246, 0.28);
}

.import-job-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #94a3b8, #64748b);
  box-shadow: 0 0 0 4px rgba(148, 163, 184, 0.12);
}

.import-job-dot.is-active {
  background: linear-gradient(135deg, #38bdf8, #2563eb);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.16);
}

.import-job-dot.is-error {
  background: linear-gradient(135deg, #fb7185, #ef4444);
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.14);
}

.import-job-title {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.import-job-count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.import-task-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-task-alert {
  border-radius: 18px;
}

.import-task-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.import-task-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
}

.import-task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.import-task-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.import-task-name {
  min-width: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--theme-text-primary);
  word-break: break-all;
}

.import-task-desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--theme-text-secondary);
}

.import-task-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}

.import-task-progress-text {
  min-width: 40px;
  font-size: 12px;
  font-weight: 700;
  color: var(--theme-text-secondary);
  text-align: right;
}

.import-task-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 12px;
}

.import-task-step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.import-task-step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.4);
}

.import-task-step.is-finished {
  color: #16a34a;
}

.import-task-step.is-finished .import-task-step-dot {
  background: #22c55e;
}

.import-task-step.is-active {
  color: #2563eb;
}

.import-task-step.is-active .import-task-step-dot {
  background: #3b82f6;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
}

.import-task-step.is-failed {
  color: #dc2626;
}

.import-task-step.is-failed .import-task-step-dot {
  background: #ef4444;
}

.import-task-error {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(254, 226, 226, 0.72);
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
</style>
