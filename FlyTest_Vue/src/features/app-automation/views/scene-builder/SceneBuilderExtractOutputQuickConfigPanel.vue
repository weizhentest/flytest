<template>
  <div class="quick-config-panel">
    <div class="quick-config-head">
      <span class="quick-config-kicker">Output</span>
      <div class="quick-config-title">提取输出配置</div>
    </div>

    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="来源变量">
          <a-input
            :model-value="readSelectedConfigString('source')"
            placeholder="例如：response 或 response.body"
            @input="value => updateSelectedStepConfig('source', value)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="提取路径">
          <a-input
            :model-value="readSelectedConfigString('path')"
            placeholder="例如：body.data.token"
            @input="value => updateSelectedStepConfig('path', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="保存变量名">
          <a-input
            :model-value="readSelectedConfigString('variable_name')"
            placeholder="例如：token"
            @input="value => updateSelectedStepConfig('variable_name', value)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="保存范围">
          <a-select
            :model-value="selectedVariableScope"
            @change="value => updateSelectedStepConfig('scope', value || 'local')"
          >
            <a-option v-for="item in variableScopeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { variableScopeOptions } from './sceneBuilderQuickOptions'
import type {
  SceneBuilderQuickConfigStringProps,
  SceneBuilderSelectedVariableScope,
} from './sceneBuilderQuickConfigModels'

interface Props extends SceneBuilderSelectedVariableScope, SceneBuilderQuickConfigStringProps {}

defineProps<Props>()
</script>

<style scoped>
.quick-config-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.quick-config-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quick-config-kicker {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.quick-config-title {
  color: var(--theme-text);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
}

:deep(.arco-form-item) {
  margin-bottom: 0;
}

:deep(.arco-input-wrapper),
:deep(.arco-select-view),
:deep(.arco-input-number) {
  border-radius: 12px;
}
</style>
