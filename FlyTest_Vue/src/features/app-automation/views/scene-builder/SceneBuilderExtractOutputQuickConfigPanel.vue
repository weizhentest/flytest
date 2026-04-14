<template>
  <div class="quick-config-panel">
    <div class="quick-config-title">提取输出配置</div>
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
        <a-form-item label="保存作用域">
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
