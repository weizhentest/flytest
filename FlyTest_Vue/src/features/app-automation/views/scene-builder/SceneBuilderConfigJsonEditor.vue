<template>
  <div class="json-editor-shell">
    <div class="editor-summary-card">
      <div class="editor-summary-copy">
        <span class="editor-kicker">Step Config</span>
        <strong>配置字段与 JSON 编辑</strong>
      </div>
      <div class="config-keys">
        <a-tag v-for="item in configKeys" :key="item" size="small">{{ item }}</a-tag>
        <span v-if="!configKeys.length" class="config-empty-text">当前步骤还没有配置字段</span>
      </div>
    </div>

    <div class="editor-field-card">
      <a-form-item label="配置 JSON">
        <a-textarea
          v-model="stepConfigTextModel"
          :auto-size="{ minRows: 10, maxRows: 18 }"
          placeholder="请输入步骤配置 JSON"
        />
      </a-form-item>
    </div>

    <div class="config-actions">
      <a-button @click="emit('reset-selected-step-config')">恢复默认配置</a-button>
      <a-button type="primary" @click="emit('apply-step-config')">应用到当前步骤</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  configKeys: string[]
}

defineProps<Props>()

const stepConfigTextModel = defineModel<string>('stepConfigText', { required: true })

const emit = defineEmits<{
  'reset-selected-step-config': []
  'apply-step-config': []
}>()
</script>

<style scoped>
.json-editor-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.editor-summary-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 20px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.1), rgba(var(--theme-accent-rgb), 0.04));
}

.editor-summary-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.editor-kicker {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.editor-summary-copy strong {
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.config-empty-text {
  color: var(--theme-text-secondary);
}

.config-keys {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.editor-field-card {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.editor-field-card :deep(.arco-form-item) {
  margin-bottom: 0;
}

.editor-field-card :deep(.arco-textarea-wrapper) {
  border-radius: 12px;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.config-actions :deep(.arco-btn) {
  min-width: 108px;
  border-radius: 12px;
}

@media (max-width: 900px) {
  .config-actions {
    justify-content: stretch;
    flex-direction: column;
  }
}
</style>
