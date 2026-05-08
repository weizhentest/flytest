<template>
  <div class="quick-config-panel">
    <div class="quick-config-head">
      <span class="quick-config-kicker">API Request</span>
      <div class="quick-config-title">接口请求配置</div>
    </div>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="请求方法">
          <a-select
            :model-value="readSelectedConfigString('method', 'GET')"
            @change="value => updateSelectedStepConfig('method', value || 'GET')"
          >
            <a-option v-for="item in httpMethodOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="请求地址">
          <a-input
            :model-value="readSelectedConfigString('url')"
            placeholder="例如：https://example.com/api/health"
            @input="value => updateSelectedStepConfig('url', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="超时（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('timeout', 10)"
            :min="0.1"
            :max="300"
            :step="0.5"
            @change="value => updateSelectedStepConfig('timeout', value ?? 10)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="响应类型">
          <a-select
            :model-value="readSelectedConfigString('response_type', 'auto')"
            @change="value => updateSelectedStepConfig('response_type', value || 'auto')"
          >
            <a-option v-for="item in responseTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="期望状态码">
          <a-input
            :model-value="readSelectedConfigString('expected_status')"
            placeholder="可留空，例如：200"
            @input="value => handleLooseConfigTextChange('expected_status', String(value || ''))"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="完整响应保存名">
          <a-input
            :model-value="readSelectedConfigString('save_as')"
            placeholder="例如：response"
            @input="value => updateSelectedStepConfig('save_as', value)"
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

    <a-form-item label="请求头 JSON">
      <a-textarea
        :model-value="formatQuickConfigValue(readSelectedConfigValue('headers', {}))"
        :auto-size="{ minRows: 4, maxRows: 8 }"
        placeholder='例如：{"Authorization":"Bearer {{token}}"}'
        @change="value => handleJsonConfigTextChange('headers', String(value || ''), {})"
      />
    </a-form-item>
    <a-form-item label="查询参数 JSON">
      <a-textarea
        :model-value="formatQuickConfigValue(readSelectedConfigValue('params', {}))"
        :auto-size="{ minRows: 4, maxRows: 8 }"
        placeholder='例如：{"page":1,"size":20}'
        @change="value => handleJsonConfigTextChange('params', String(value || ''), {})"
      />
    </a-form-item>
    <a-form-item label="JSON 请求体">
      <a-textarea
        :model-value="formatQuickConfigValue(readSelectedConfigValue('json'))"
        :auto-size="{ minRows: 4, maxRows: 10 }"
        placeholder='留空则不发送 JSON 请求体，例如：{"username":"admin"}'
        @change="value => handleJsonConfigTextChange('json', String(value || ''), undefined)"
      />
    </a-form-item>
    <a-form-item label="表单或原始请求体">
      <a-textarea
        :model-value="formatQuickConfigValue(readSelectedConfigValue('data'))"
        :auto-size="{ minRows: 3, maxRows: 8 }"
        placeholder="可填写文本、数字或 JSON 对象"
        @change="value => handleLooseConfigTextChange('data', String(value || ''))"
      />
    </a-form-item>
    <a-form-item label="字段提取 JSON 数组">
      <a-textarea
        :model-value="formatQuickConfigValue(readSelectedConfigValue('extracts', []))"
        :auto-size="{ minRows: 4, maxRows: 10 }"
        placeholder='例如：[{"path":"body.data.token","name":"token","scope":"local"}]'
        @change="value => handleJsonConfigTextChange('extracts', String(value || ''), [])"
      />
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import {
  httpMethodOptions,
  responseTypeOptions,
  variableScopeOptions,
} from './sceneBuilderQuickOptions'
import type {
  SceneBuilderJsonConfigTextChangeHandler,
  SceneBuilderLooseConfigTextChangeHandler,
  SceneBuilderQuickConfigFormatter,
  SceneBuilderQuickConfigValueNumericProps,
  SceneBuilderSelectedVariableScope,
} from './sceneBuilderQuickConfigModels'

interface Props
  extends SceneBuilderSelectedVariableScope,
    SceneBuilderQuickConfigValueNumericProps,
    SceneBuilderQuickConfigFormatter,
    SceneBuilderLooseConfigTextChangeHandler,
    SceneBuilderJsonConfigTextChangeHandler {}

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
:deep(.arco-input-number),
:deep(.arco-textarea-wrapper) {
  border-radius: 12px;
}
</style>
