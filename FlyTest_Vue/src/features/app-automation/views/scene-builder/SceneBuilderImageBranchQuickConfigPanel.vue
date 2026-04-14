<template>
  <div class="quick-config-panel">
    <div class="quick-config-title">图片分支点击配置</div>
    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="主选择器类型">
          <a-select
            :model-value="selectedPrimarySelectorType"
            @change="value => updateSelectedStepConfig('selector_type', value || 'image')"
          >
            <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="主选择器">
          <a-input
            :model-value="readSelectedConfigString('selector')"
            placeholder="主定位元素或图片路径"
            @input="value => updateSelectedStepConfig('selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-row v-if="selectedPrimarySelectorType === 'image'" :gutter="12">
      <a-col :span="8">
        <a-form-item label="主阈值">
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
        <a-form-item label="主全屏找图">
          <a-switch
            :model-value="readSelectedConfigBoolean('search_full_screen', true)"
            @change="value => updateSelectedStepConfig('search_full_screen', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="备用选择器类型">
          <a-select
            :model-value="selectedFallbackSelectorType"
            @change="value => updateSelectedStepConfig('fallback_selector_type', value || 'element')"
          >
            <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="备用选择器">
          <a-input
            :model-value="readSelectedConfigString('fallback_selector')"
            placeholder="备用元素或图片路径"
            @input="value => updateSelectedStepConfig('fallback_selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-row :gutter="12">
      <a-col v-if="selectedFallbackSelectorType === 'image'" :span="8">
        <a-form-item label="备用阈值">
          <a-input-number
            :model-value="readSelectedConfigNumber('fallback_threshold', 0.7)"
            :min="0.1"
            :max="1"
            :step="0.05"
            @change="value => updateSelectedStepConfig('fallback_threshold', value ?? 0.7)"
          />
        </a-form-item>
      </a-col>
      <a-col v-if="selectedFallbackSelectorType === 'image'" :span="8">
        <a-form-item label="备用全屏找图">
          <a-switch
            :model-value="readSelectedConfigBoolean('fallback_search_full_screen', true)"
            @change="value => updateSelectedStepConfig('fallback_search_full_screen', value)"
          />
        </a-form-item>
      </a-col>
      <a-col v-if="selectedStepActionType === 'image_exists_click_chain'" :span="8">
        <a-form-item label="主备间隔（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('interval', 0.5)"
            :min="0"
            :max="10"
            :step="0.1"
            @change="value => updateSelectedStepConfig('interval', value ?? 0.5)"
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
  SceneBuilderSelectedFallbackSelectorType,
  SceneBuilderSelectedPrimarySelectorType,
  SceneBuilderSelectedStepActionType,
} from './sceneBuilderQuickConfigModels'

interface Props
  extends SceneBuilderSelectedStepActionType,
    SceneBuilderSelectedPrimarySelectorType,
    SceneBuilderSelectedFallbackSelectorType,
    SceneBuilderQuickConfigBooleanProps {}

defineProps<Props>()
</script>
