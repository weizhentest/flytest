<template>
  <a-card class="ai-status-card">
    <div class="ai-status-header">
      <div class="ai-status-copy">
        <span class="ai-status-kicker">AI 智能模式</span>
        <strong>{{ aiStatusTitle }}</strong>
        <p>{{ aiStatusDescription }}</p>
      </div>
      <a-space wrap class="ai-status-actions">
        <a-tag :color="aiStatusColor">{{ aiStatusLabel }}</a-tag>
        <a-tag v-if="aiStatusHasConfig" :color="aiStatusSupportsVision ? 'arcoblue' : 'purple'">
          {{ aiStatusSupportsVision ? '视觉 + 文本' : '文本模式' }}
        </a-tag>
        <a-button size="mini" :loading="aiStatusLoading" @click="emit('refresh-ai-status')">刷新 AI 状态</a-button>
        <a-button size="mini" type="outline" @click="emit('open-llm-config')">模型配置</a-button>
      </a-space>
    </div>

    <div class="ai-status-grid">
      <div class="ai-status-item">
        <span>当前能力</span>
        <strong>{{ aiCapabilityLabel }}</strong>
        <small>{{ aiStatusCheckedAt ? `最近检测：${formatDateTime(aiStatusCheckedAt)}` : '尚未检测' }}</small>
      </div>
      <div class="ai-status-item">
        <span>激活配置</span>
        <strong>{{ aiConfigDisplayName }}</strong>
        <small>{{ aiProviderDisplayName }}</small>
      </div>
      <div class="ai-status-item">
        <span>模型名称</span>
        <strong>{{ aiModelDisplayName }}</strong>
        <small>{{ aiEndpointDisplay }}</small>
      </div>
    </div>

    <div v-if="lastAiActivity" class="ai-activity-panel">
      <div class="ai-activity-header">
        <div class="ai-activity-copy">
          <span class="ai-activity-kicker">最近一次 AI 结果</span>
          <strong>{{ getAiActionLabel(lastAiActivity.action) }}</strong>
        </div>
        <a-tag :color="getAiActivityColor(lastAiActivity)">{{ getAiActivityStatusLabel(lastAiActivity) }}</a-tag>
      </div>

      <div class="ai-activity-meta">
        <span>时间：{{ formatDateTime(lastAiActivity.executed_at) }}</span>
        <span v-if="lastAiActivity.target_name">对象：{{ lastAiActivity.target_name }}</span>
        <span v-if="lastAiActivity.model">模型：{{ lastAiActivity.model }}</span>
        <span v-if="lastAiActivity.provider">提供方：{{ formatProviderLabel(lastAiActivity.provider) }}</span>
      </div>

      <div class="ai-activity-summary">{{ lastAiActivity.summary }}</div>
      <div v-if="lastAiActivity.prompt" class="ai-activity-prompt">提示词：{{ lastAiActivity.prompt }}</div>

      <div v-if="lastAiActivity.warnings.length" class="ai-warning-list">
        <div
          v-for="(warning, index) in lastAiActivity.warnings"
          :key="`${lastAiActivity.executed_at}-${index}`"
          class="ai-warning-item"
        >
          {{ warning }}
        </div>
      </div>
    </div>
    <div v-else class="ai-activity-empty">还没有触发 AI 场景生成或步骤补全，执行后会在这里保留结果摘要与回退原因。</div>
  </a-card>
</template>

<script setup lang="ts">
import type { AiActivityRecord } from './useSceneBuilderAiRuntime'

interface Props {
  aiStatusTitle: string
  aiStatusDescription: string
  aiStatusColor: string
  aiStatusLabel: string
  aiStatusHasConfig: boolean
  aiStatusSupportsVision: boolean
  aiStatusLoading: boolean
  aiCapabilityLabel: string
  aiStatusCheckedAt?: string | null
  aiConfigDisplayName: string
  aiProviderDisplayName: string
  aiModelDisplayName: string
  aiEndpointDisplay: string
  lastAiActivity: AiActivityRecord | null
  formatDateTime: (value?: string | null) => string
  formatProviderLabel: (value?: string | null) => string
  getAiActionLabel: (action: AiActivityRecord['action']) => string
  getAiActivityColor: (record: AiActivityRecord) => string
  getAiActivityStatusLabel: (record: AiActivityRecord) => string
}

defineProps<Props>()

const emit = defineEmits<{
  'refresh-ai-status': []
  'open-llm-config': []
}>()
</script>

<style scoped>
.ai-status-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.ai-status-header,
.ai-activity-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ai-status-copy,
.ai-activity-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-status-kicker,
.ai-activity-kicker {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--theme-text-secondary);
}

.ai-status-copy strong,
.ai-activity-copy strong {
  color: var(--theme-text);
  font-size: 18px;
}

.ai-status-copy p {
  margin: 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.ai-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.ai-status-item,
.ai-activity-panel {
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.ai-status-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
}

.ai-status-item span {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.ai-status-item strong {
  color: var(--theme-text);
  word-break: break-word;
  overflow-wrap: anywhere;
}

.ai-status-item small {
  color: var(--theme-text-secondary);
  line-height: 1.6;
}

.ai-activity-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-activity-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.ai-activity-summary {
  color: var(--theme-text);
  line-height: 1.7;
  font-weight: 500;
}

.ai-activity-prompt {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(var(--theme-surface-rgb), 0.72);
  color: var(--theme-text-secondary);
  line-height: 1.7;
  word-break: break-word;
}

.ai-warning-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-warning-item,
.ai-activity-empty {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(var(--warning-6), 0.24);
  background: rgba(var(--warning-6), 0.08);
  color: rgb(var(--warning-6));
  line-height: 1.7;
}

.ai-activity-empty {
  border-color: rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.05);
  color: var(--theme-text-secondary);
}

@media (max-width: 1480px) {
  .ai-status-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .ai-status-header,
  .ai-activity-header {
    flex-direction: column;
  }
}
</style>
