<template>
  <div class="quick-config-panel">
    <div class="quick-config-head">
      <span class="quick-config-kicker">Action Setup</span>
      <div class="quick-config-title">基础动作配置</div>
    </div>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="定位方式">
          <a-select
            :model-value="selectedPrimarySelectorType"
            @change="value => updateSelectedStepConfig('selector_type', value || 'element')"
          >
            <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="定位内容">
          <a-input
            :model-value="readSelectedConfigString('selector')"
            placeholder="输入元素名称、文本、XPath、图片路径或区域坐标"
            @input="value => updateSelectedStepConfig('selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row v-if="selectedPrimarySelectorType === 'image'" :gutter="12">
      <a-col :span="8">
        <a-form-item label="图片阈值">
          <a-input-number
            :model-value="readSelectedConfigNumber('threshold', 0.7)"
            :min="0.1"
            :max="1"
            :step="0.05"
            @change="value => updateSelectedStepConfig('threshold', value ?? 0.7)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="全屏查找">
          <a-switch
            :model-value="readSelectedConfigBoolean('search_full_screen', true)"
            @change="value => updateSelectedStepConfig('search_full_screen', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col v-if="selectedStepActionType === 'text'" :span="24">
        <a-form-item label="输入内容">
          <a-input
            :model-value="readSelectedConfigString('text')"
            placeholder="输入文本，支持变量表达式"
            @input="value => updateSelectedStepConfig('text', value)"
          />
        </a-form-item>
      </a-col>
      <a-col v-if="selectedStepActionType === 'wait' || selectedStepActionType === 'assert_exists'" :span="8">
        <a-form-item label="等待超时（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('timeout', 10)"
            :min="0"
            :max="300"
            :step="0.5"
            @change="value => updateSelectedStepConfig('timeout', value ?? 10)"
          />
        </a-form-item>
      </a-col>
      <a-col v-if="selectedStepActionType === 'double_click'" :span="8">
        <a-form-item label="双击间隔（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('interval', 0.12)"
            :min="0"
            :max="5"
            :step="0.05"
            @change="value => updateSelectedStepConfig('interval', value ?? 0.12)"
          />
        </a-form-item>
      </a-col>
      <a-col v-if="selectedStepActionType === 'long_press'" :span="8">
        <a-form-item label="长按时长（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('duration', 1)"
            :min="0.1"
            :max="20"
            :step="0.1"
            @change="value => updateSelectedStepConfig('duration', value ?? 1)"
          />
        </a-form-item>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { selectorTypeOptions } from './sceneBuilderQuickOptions'
import type {
  SceneBuilderQuickConfigBooleanProps,
  SceneBuilderSelectedPrimarySelectorType,
  SceneBuilderSelectedStepActionType,
} from './sceneBuilderQuickConfigModels'

interface Props
  extends SceneBuilderSelectedStepActionType,
    SceneBuilderSelectedPrimarySelectorType,
    SceneBuilderQuickConfigBooleanProps {}

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
