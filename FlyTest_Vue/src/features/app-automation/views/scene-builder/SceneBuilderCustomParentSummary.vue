<template>
  <div class="config-summary">
    <div class="summary-hero">
      <div class="summary-copy">
        <span class="summary-kicker">Custom Component</span>
        <strong>{{ selectedParentStep?.name || '当前父组件' }}</strong>
      </div>
      <div class="summary-badge">{{ countChildSteps(selectedParentStep) }} 个子步骤</div>
    </div>

    <a-form layout="vertical" class="summary-form">
      <div class="field-card">
        <a-form-item label="组件名称">
          <a-input v-model="selectedParentStep!.name" />
        </a-form-item>
      </div>
      <div class="field-grid">
        <div class="field-card">
          <a-form-item label="组件类型">
            <a-input :model-value="selectedParentStep!.component_type || selectedParentStep!.type || 'custom'" disabled />
          </a-form-item>
        </div>
        <div class="field-card">
          <a-form-item label="子步骤数量">
            <a-input :model-value="String(countChildSteps(selectedParentStep))" disabled />
          </a-form-item>
        </div>
      </div>
    </a-form>

    <a-alert class="summary-alert">
      当前选中的是自定义组件父步骤，请展开后编辑子步骤；这里可以直接修改组件在当前场景中的显示名称。
    </a-alert>
  </div>
</template>

<script setup lang="ts">
import type { AppSceneStep } from '../../types'

interface Props {
  selectedParentStep: AppSceneStep | null
  countChildSteps: (step?: Partial<AppSceneStep> | null) => number
}

defineProps<Props>()
</script>

<style scoped>
.config-summary {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.1), rgba(var(--theme-accent-rgb), 0.04));
}

.summary-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-kicker {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.summary-copy strong {
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.summary-badge {
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(var(--theme-accent-rgb), 0.1);
  color: var(--theme-accent);
  font-size: 12px;
  font-weight: 600;
}

.summary-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.field-card {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.field-card :deep(.arco-form-item) {
  margin-bottom: 0;
}

.field-card :deep(.arco-input-wrapper) {
  border-radius: 12px;
}

.summary-alert {
  border-radius: 14px;
}

@media (max-width: 900px) {
  .summary-hero,
  .field-grid {
    grid-template-columns: 1fr;
  }

  .summary-hero {
    flex-direction: column;
  }
}
</style>
