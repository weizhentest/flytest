<template>
  <div class="quick-config-panel">
    <div class="quick-config-title">
      {{ selectedStepActionType === 'set_variable' ? '设置变量配置' : '删除变量配置' }}
    </div>
    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="变量名">
          <a-input
            :model-value="readSelectedConfigString('variable_name')"
            placeholder="例如：token"
            @input="value => updateSelectedStepConfig('variable_name', value)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="作用域">
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
    <a-form-item v-if="selectedStepActionType === 'set_variable'" label="变量值">
      <a-textarea
        :model-value="formatQuickConfigValue(readSelectedConfigValue('value'))"
        :auto-size="{ minRows: 4, maxRows: 8 }"
        placeholder="支持普通文本、数字、布尔值，或 JSON 对象/数组"
        @change="value => handleLooseConfigTextChange('value', String(value || ''))"
      />
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { variableScopeOptions } from './sceneBuilderQuickOptions'
import type {
  SceneBuilderLooseConfigTextChangeHandler,
  SceneBuilderQuickConfigFormatter,
  SceneBuilderQuickConfigValueProps,
  SceneBuilderSelectedStepActionType,
  SceneBuilderSelectedVariableScope,
} from './sceneBuilderQuickConfigModels'

interface Props
  extends SceneBuilderSelectedStepActionType,
    SceneBuilderSelectedVariableScope,
    SceneBuilderQuickConfigValueProps,
    SceneBuilderQuickConfigFormatter,
    SceneBuilderLooseConfigTextChangeHandler {}

defineProps<Props>()
</script>
