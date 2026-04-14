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
  border-radius: 14px;
  border: 1px dashed var(--theme-card-border);
  padding: 14px;
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
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(var(--theme-accent-rgb), 0.06);
}

.stack strong {
  color: var(--theme-text);
}

.stack small {
  color: var(--theme-text-secondary);
}

@media (max-width: 960px) {
  .preview-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
