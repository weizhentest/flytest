<template>
  <div class="quick-config-panel">
    <div class="quick-config-title">断言快捷配置</div>
    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="断言类型">
          <a-select :model-value="selectedAssertType" @change="value => handleAssertTypeChange(String(value || 'condition'))">
            <a-option v-for="item in assertTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="超时重试（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('timeout', 0)"
            :min="0"
            :max="300"
            :step="0.5"
            @change="value => updateSelectedStepConfig('timeout', value ?? 0)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="重试间隔（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('retry_interval', 0.5)"
            :min="0.1"
            :max="30"
            :step="0.1"
            @change="value => updateSelectedStepConfig('retry_interval', value ?? 0.5)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <template v-if="selectedAssertQuickMode === 'ocr'">
      <a-row :gutter="12">
        <a-col :span="8">
          <a-form-item label="OCR 区域类型">
            <a-input :model-value="'region'" disabled />
          </a-form-item>
        </a-col>
        <a-col :span="16">
          <a-form-item label="OCR 区域">
            <a-input
              :model-value="readSelectedConfigString('selector')"
              placeholder="格式：x1,y1,x2,y2"
              @input="value => updateSelectedStepConfig('selector', value)"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-row v-if="selectedAssertType === 'text' || selectedAssertType === 'regex'" :gutter="12">
        <a-col v-if="selectedAssertType === 'text'" :span="8">
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
        <a-col :span="selectedAssertType === 'text' ? 16 : 24">
          <a-form-item :label="selectedAssertType === 'regex' ? '正则表达式' : '期望文本'">
            <a-input
              :model-value="readSelectedConfigString('expected')"
              :placeholder="selectedAssertType === 'regex' ? '请输入 OCR 正则表达式' : '请输入期望文本'"
              @input="value => updateSelectedStepConfig('expected', value)"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-row v-else-if="selectedAssertType === 'number'" :gutter="12">
        <a-col :span="12">
          <a-form-item label="期望数字">
            <a-input
              :model-value="readSelectedConfigString('expected')"
              placeholder="例如：100 或 3,000"
              @input="value => updateSelectedStepConfig('expected', value)"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-row v-else-if="selectedAssertType === 'range'" :gutter="12">
        <a-col :span="12">
          <a-form-item label="最小值">
            <a-input
              :model-value="readSelectedConfigString('min')"
              placeholder="可留空"
              @input="value => updateSelectedStepConfig('min', value)"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="最大值">
            <a-input
              :model-value="readSelectedConfigString('max')"
              placeholder="可留空"
              @input="value => updateSelectedStepConfig('max', value)"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </template>

    <template v-else-if="selectedAssertQuickMode === 'image'">
      <a-row :gutter="12">
        <a-col :span="16">
          <a-form-item label="期望图片路径">
            <a-input
              :model-value="readSelectedConfigString('expected')"
              placeholder="例如：common/login-button.png"
              @input="value => updateSelectedStepConfig('expected', value)"
            />
          </a-form-item>
        </a-col>
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
      </a-row>
      <a-row :gutter="12">
        <a-col :span="8">
          <a-form-item label="全屏找图">
            <a-switch
              :model-value="readSelectedConfigBoolean('search_full_screen', true)"
              @change="value => updateSelectedStepConfig('search_full_screen', value)"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </template>

    <template v-else-if="selectedAssertQuickMode === 'exists'">
      <a-row :gutter="12">
        <a-col :span="8">
          <a-form-item label="选择器类型">
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
          <a-form-item label="选择器内容">
            <a-input
              :model-value="readSelectedConfigString('selector')"
              placeholder="元素名、文本或图片路径"
              @input="value => updateSelectedStepConfig('selector', value)"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </template>

    <template v-else>
      <a-row :gutter="12">
        <a-col :span="10">
          <a-form-item label="断言来源">
            <a-input
              :model-value="readSelectedConfigString('source')"
              placeholder="例如：response.body.code"
              @input="value => updateSelectedStepConfig('source', value)"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item label="操作符">
            <a-select
              :model-value="readSelectedConfigString('operator', '==')"
              @change="value => updateSelectedStepConfig('operator', value || '==')"
            >
              <a-option v-for="item in assertOperatorOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="期望值">
            <a-input
              :model-value="readSelectedConfigString('expected')"
              placeholder="期望值或变量表达式"
              @input="value => updateSelectedStepConfig('expected', value)"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  assertOperatorOptions,
  assertTypeOptions,
  matchModeOptions,
  selectorTypeOptions,
} from './sceneBuilderQuickOptions'
import type {
  SceneBuilderAssertTypeChangeHandler,
  SceneBuilderQuickConfigBooleanProps,
  SceneBuilderSelectedAssertQuickMode,
  SceneBuilderSelectedPrimarySelectorType,
} from './sceneBuilderQuickConfigModels'

interface Props
  extends SceneBuilderSelectedAssertQuickMode,
    SceneBuilderSelectedPrimarySelectorType,
    SceneBuilderQuickConfigBooleanProps,
    SceneBuilderAssertTypeChangeHandler {}

defineProps<Props>()
</script>
