<template>
  <div class="quick-config-panel">
    <div class="quick-config-head">
      <span class="quick-config-kicker">Branch</span>
      <div class="quick-config-title">图像分支点击配置</div>
    </div>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="主定位方式">
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
        <a-form-item label="主定位内容">
          <a-input
            :model-value="readSelectedConfigString('selector')"
            placeholder="输入主目标元素、文本或图片路径"
            @input="value => updateSelectedStepConfig('selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row v-if="selectedPrimarySelectorType === 'image'" :gutter="12">
      <a-col :span="8">
        <a-form-item label="主图片阈值">
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
        <a-form-item label="主目标全屏查找">
          <a-switch
            :model-value="readSelectedConfigBoolean('search_full_screen', true)"
            @change="value => updateSelectedStepConfig('search_full_screen', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="备用定位方式">
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
        <a-form-item label="备用定位内容">
          <a-input
            :model-value="readSelectedConfigString('fallback_selector')"
            placeholder="输入备用元素、文本或图片路径"
            @input="value => updateSelectedStepConfig('fallback_selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col v-if="selectedFallbackSelectorType === 'image'" :span="8">
        <a-form-item label="备用图片阈值">
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
        <a-form-item label="备用全屏查找">
          <a-switch
            :model-value="readSelectedConfigBoolean('fallback_search_full_screen', true)"
            @change="value => updateSelectedStepConfig('fallback_search_full_screen', value)"
          />
        </a-form-item>
      </a-col>
      <a-col v-if="selectedStepActionType === 'image_exists_click_chain'" :span="8">
        <a-form-item label="主备切换间隔（秒）">
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
