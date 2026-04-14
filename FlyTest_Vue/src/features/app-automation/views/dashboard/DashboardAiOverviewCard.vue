<template>
  <a-card class="panel-card" title="AI 智能模式">
    <div class="ai-panel">
      <div class="ai-panel-head">
        <div class="ai-copy">
          <strong>{{ aiStatusTitle }}</strong>
          <p>{{ aiStatusDescription }}</p>
        </div>
        <a-tag :color="aiStatusTagColor">{{ aiStatusTagText }}</a-tag>
      </div>

      <div class="ai-grid">
        <div class="ai-item">
          <span>激活配置</span>
          <strong>{{ aiConfigDisplay }}</strong>
        </div>
        <div class="ai-item">
          <span>提供方</span>
          <strong>{{ aiProviderDisplay }}</strong>
        </div>
        <div class="ai-item">
          <span>模型</span>
          <strong>{{ aiModelDisplay }}</strong>
        </div>
        <div class="ai-item">
          <span>能力模式</span>
          <strong>{{ aiCapabilityDisplay }}</strong>
        </div>
      </div>

      <div class="ai-endpoint">{{ aiEndpointDisplay }}</div>

      <div class="ai-actions">
        <a-button type="primary" @click="emit('open-scene-builder')">进入 AI 编排</a-button>
        <a-button @click="emit('open-llm-config')">模型配置</a-button>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { DashboardAiOverviewCardEmits } from './dashboardEventModels'
import type { DashboardAiOverviewCardProps } from './dashboardViewModels'

defineProps<DashboardAiOverviewCardProps>()

const emit = defineEmits<DashboardAiOverviewCardEmits>()
</script>

<style scoped>
.panel-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 16px;
}

.ai-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ai-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-copy strong {
  color: var(--theme-text);
  font-size: 16px;
}

.ai-copy p,
.ai-endpoint {
  margin: 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.ai-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.ai-item {
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.05);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
}

.ai-item span {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.ai-item strong {
  color: var(--theme-text);
  word-break: break-word;
  overflow-wrap: anywhere;
}

.ai-endpoint {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(var(--theme-surface-rgb), 0.72);
  word-break: break-word;
}

.ai-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 1100px) {
  .ai-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .ai-panel-head {
    flex-direction: column;
  }
}
</style>
