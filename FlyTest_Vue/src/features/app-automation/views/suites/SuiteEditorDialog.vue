<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="form.id ? '编辑测试套件' : '新建测试套件'"
    width="860px"
    @ok="emit('save')"
  >
    <a-form :model="form" layout="vertical">
      <a-form-item field="name" label="套件名称">
        <a-input v-model="form.name" />
      </a-form-item>
      <a-form-item field="description" label="描述">
        <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
      </a-form-item>
      <a-form-item field="test_case_ids" label="选择用例">
        <a-select v-model="form.test_case_ids" multiple allow-clear placeholder="选择要加入套件的测试用例">
          <a-option v-for="item in testCases" :key="item.id" :value="item.id">
            {{ item.name }}
          </a-option>
        </a-select>
      </a-form-item>
      <div v-if="selectedCases.length" class="selected-preview">
        <div class="preview-title">当前顺序</div>
        <div class="preview-list">
          <div v-for="(item, index) in selectedCases" :key="item.id" class="preview-item">
            <div class="stack">
              <strong>{{ index + 1 }}. {{ item.name }}</strong>
              <small>{{ item.description || '暂无用例描述' }}</small>
            </div>
            <a-space>
              <a-button size="mini" type="text" :disabled="index === 0" @click="emit('move-case', index, -1)">上移</a-button>
              <a-button size="mini" type="text" :disabled="index === selectedCases.length - 1" @click="emit('move-case', index, 1)">下移</a-button>
            </a-space>
          </div>
        </div>
      </div>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import type { SuiteEditorDialogEmits } from './suiteEventModels'
import type { SuiteEditorDialogProps } from './suiteViewModels'

defineProps<SuiteEditorDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<SuiteEditorDialogEmits>()
</script>

<style scoped>
.selected-preview {
  margin-top: 8px;
  border-radius: 16px;
  border: 1px dashed rgba(var(--theme-accent-rgb), 0.24);
  padding: 16px;
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.06), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.9));
}

.preview-title {
  margin-bottom: 10px;
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.preview-list,
.stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.stack strong {
  color: var(--theme-text);
}

.stack small {
  color: var(--theme-text-secondary);
}

:deep(.arco-modal-content) {
  border-radius: 20px;
  overflow: hidden;
}

:deep(.arco-modal-header) {
  padding: 18px 24px;
  border-bottom: 1px solid rgba(149, 161, 187, 0.14);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.08), transparent 26%),
    linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(255, 255, 255, 0.94));
}

:deep(.arco-modal-body) {
  padding: 22px 24px 24px;
}

:deep(.arco-input-wrapper),
:deep(.arco-select-view),
:deep(.arco-textarea-wrapper),
:deep(.arco-btn) {
  border-radius: 10px;
}

@media (max-width: 960px) {
  .preview-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
