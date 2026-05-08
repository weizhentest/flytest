<template>
  <a-modal v-model:visible="visibleModel" width="560px">
    <template #title>导出组件包</template>

    <div class="dialog-shell">
      <div class="dialog-intro">
        <span class="dialog-kicker">Package Export</span>
        <strong>导出可复用的场景组件集合</strong>
        <p>补充组件包名称、版本和说明后，可以导出为 JSON 或 YAML，在其他环境中直接复用。</p>
      </div>

      <a-form layout="vertical" class="dialog-form">
        <div class="field-card">
          <a-form-item label="组件包名称">
            <a-input v-model="form.name" placeholder="例如 app-component-pack" />
          </a-form-item>
        </div>
        <div class="form-grid">
          <div class="field-card">
            <a-form-item label="版本">
              <a-input v-model="form.version" placeholder="例如 2026.05.08" />
            </a-form-item>
          </div>
          <div class="field-card">
            <a-form-item label="作者">
              <a-input v-model="form.author" placeholder="可选" />
            </a-form-item>
          </div>
        </div>
        <div class="field-card">
          <a-form-item label="描述">
            <a-textarea
              v-model="form.description"
              :auto-size="{ minRows: 3, maxRows: 5 }"
              placeholder="说明该组件包适用的业务场景和内容范围"
            />
          </a-form-item>
        </div>
        <div class="field-card">
          <a-form-item label="导出禁用组件">
            <a-switch v-model="includeDisabledModel" />
          </a-form-item>
        </div>
      </a-form>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">取消</a-button>
        <a-button type="outline" :loading="exporting" @click="emit('submit-json')">导出 JSON</a-button>
        <a-button type="primary" :loading="exporting" @click="emit('submit-yaml')">导出 YAML</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import type { SceneBuilderComponentPackageExportFormModel } from './sceneBuilderDialogModels'

interface Props {
  exporting: boolean
  form: SceneBuilderComponentPackageExportFormModel
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
const includeDisabledModel = defineModel<boolean>('includeDisabled', { required: true })

const emit = defineEmits<{
  'submit-json': []
  'submit-yaml': []
}>()
</script>

<style scoped>
.dialog-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dialog-intro {
  padding: 18px 20px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.12), rgba(var(--theme-accent-rgb), 0.04));
}

.dialog-kicker {
  display: inline-block;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dialog-intro strong {
  display: block;
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.dialog-intro p {
  margin: 8px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-grid {
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

.field-card :deep(.arco-input-wrapper),
.field-card :deep(.arco-textarea-wrapper) {
  border-radius: 12px;
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}

:deep(.arco-modal-title) {
  font-size: 18px;
}

:deep(.arco-modal-footer .arco-btn) {
  min-width: 96px;
  border-radius: 12px;
}
</style>
