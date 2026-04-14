<template>
  <div class="quick-config-panel">
    <div class="quick-config-title">循环点击断言配置</div>
    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="点击选择器类型">
          <a-select
            :model-value="selectedClickSelectorType"
            @change="value => updateSelectedStepConfig('click_selector_type', value || 'element')"
          >
            <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="点击选择器">
          <a-input
            :model-value="readSelectedConfigString('click_selector')"
            placeholder="点击按钮元素、文本或图片路径"
            @input="value => updateSelectedStepConfig('click_selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-row v-if="selectedClickSelectorType === 'image'" :gutter="12">
      <a-col :span="8">
        <a-form-item label="点击阈值">
          <a-input-number
            :model-value="readSelectedConfigNumber('click_threshold', 0.7)"
            :min="0.1"
            :max="1"
            :step="0.05"
            @change="value => updateSelectedStepConfig('click_threshold', value ?? 0.7)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="点击全屏找图">
          <a-switch
            :model-value="readSelectedConfigBoolean('click_search_full_screen', true)"
            @change="value => updateSelectedStepConfig('click_search_full_screen', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="断言类型">
          <a-select
            :model-value="readSelectedConfigString('assert_type', 'text')"
            @change="value => updateSelectedStepConfig('assert_type', value || 'text')"
          >
            <a-option value="text">OCR 文本</a-option>
            <a-option value="number">OCR 数字</a-option>
            <a-option value="regex">OCR 正则</a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="OCR 区域">
          <a-input
            :model-value="readSelectedConfigString('ocr_selector')"
            placeholder="格式：x1,y1,x2,y2"
            @input="value => updateSelectedStepConfig('ocr_selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="匹配方式">
          <a-select
            :model-value="readSelectedConfigString('match_mode', 'contains')"
            @change="value => updateSelectedStepConfig('match_mode', value || 'contains')"
          >
            <a-option v-for="item in matchModeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="最大循环次数">
          <a-input-number
            :model-value="readSelectedConfigNumber('max_loops', 3)"
            :min="1"
            :max="100"
            @change="value => updateSelectedStepConfig('max_loops', value ?? 3)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="最少命中次数">
          <a-input-number
            :model-value="readSelectedConfigNumber('min_match', 1)"
            :min="0"
            :max="100"
            @change="value => updateSelectedStepConfig('min_match', value ?? 1)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="点击后等待（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('interval', 0.5)"
            :min="0"
            :max="10"
            :step="0.1"
            @change="value => updateSelectedStepConfig('interval', value ?? 0.5)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="单次 OCR 超时（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('timeout', 1.5)"
            :min="0"
            :max="30"
            :step="0.1"
            @change="value => updateSelectedStepConfig('timeout', value ?? 1.5)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-form-item label="期望列表">
      <a-textarea
        :model-value="expectedListText"
        :auto-size="{ minRows: 4, maxRows: 8 }"
        placeholder="每行一个期望值，也可以直接填写 JSON 数组"
        @input="value => handleExpectedListTextChange(String(value || ''))"
      />
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { matchModeOptions, selectorTypeOptions } from './sceneBuilderQuickOptions'
import type {
  SceneBuilderExpectedListBindings,
  SceneBuilderQuickConfigBooleanProps,
  SceneBuilderSelectedClickSelectorType,
} from './sceneBuilderQuickConfigModels'

interface Props
  extends SceneBuilderSelectedClickSelectorType,
    SceneBuilderExpectedListBindings,
    SceneBuilderQuickConfigBooleanProps {}

defineProps<Props>()
</script>
