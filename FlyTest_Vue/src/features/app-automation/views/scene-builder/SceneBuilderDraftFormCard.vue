<template>
  <a-card class="draft-form-card">
    <a-form :model="draft" layout="vertical">
      <a-row :gutter="12">
        <a-col :span="8">
          <a-form-item field="caseId" label="加载已有用例">
            <a-select
              v-model="selectedCaseIdModel"
              allow-clear
              placeholder="选择已有用例"
              @change="emit('case-change', $event)"
            >
              <a-option v-for="item in testCases" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="name" label="用例名称">
            <a-input v-model="draft.name" placeholder="例如：登录并进入首页" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="package_id" label="应用包">
            <a-select v-model="draft.package_id" allow-clear placeholder="可选">
              <a-option v-for="item in packages" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="description" label="描述">
            <a-textarea
              v-model="draft.description"
              :auto-size="{ minRows: 3, maxRows: 5 }"
              placeholder="补充业务说明或前置条件"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="timeout" label="超时时间（秒）">
            <a-input-number v-model="draft.timeout" :min="1" :max="7200" />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="retry_count" label="失败重试">
            <a-input-number v-model="draft.retry_count" :min="0" :max="10" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="场景变量">
        <div class="variable-list">
          <div v-if="variableItems.length" class="variable-items">
            <div v-for="(item, index) in variableItems" :key="`variable-${index}`" class="variable-row">
              <a-input v-model="item.name" placeholder="变量名" />
              <a-select v-model="item.scope" placeholder="作用域">
                <a-option value="local">local</a-option>
                <a-option value="global">global</a-option>
              </a-select>
              <a-select v-model="item.type" placeholder="类型">
                <a-option value="string">string</a-option>
                <a-option value="number">number</a-option>
                <a-option value="boolean">boolean</a-option>
                <a-option value="array">array</a-option>
                <a-option value="object">object</a-option>
              </a-select>
              <a-input v-model="item.valueText" placeholder="默认值" />
              <a-input v-model="item.description" placeholder="说明" />
              <a-button status="danger" @click="emit('remove-variable', index)">删除</a-button>
            </div>
          </div>
          <a-empty v-else description="暂未配置场景变量" />
        </div>
        <div class="variable-actions">
          <a-button type="outline" size="small" @click="emit('add-variable')">添加变量</a-button>
        </div>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup lang="ts">
import type { AppPackage, AppTestCase } from '../../types'
import type { SceneVariableDraft } from './sceneBuilderDraft'

interface DraftFormModel {
  name: string
  description: string
  package_id?: number | null
  timeout: number
  retry_count: number
}

interface Props {
  draft: DraftFormModel
  packages: AppPackage[]
  testCases: AppTestCase[]
  variableItems: SceneVariableDraft[]
}

defineProps<Props>()

const selectedCaseIdModel = defineModel<number | undefined>('selectedCaseId', { required: true })

const emit = defineEmits<{
  'case-change': [value?: number]
  'add-variable': []
  'remove-variable': [index: number]
}>()
</script>

<style scoped>
.draft-form-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.variable-list {
  border: 1px dashed rgba(var(--theme-accent-rgb), 0.24);
  border-radius: 14px;
  padding: 14px;
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.variable-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.variable-row {
  display: grid;
  grid-template-columns: 1.1fr 120px 120px 1.2fr 1.1fr auto;
  gap: 10px;
  align-items: center;
}

.variable-actions {
  margin-top: 10px;
}

@media (max-width: 1480px) {
  .variable-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 960px) {
  .variable-row {
    grid-template-columns: 1fr;
  }
}
</style>
