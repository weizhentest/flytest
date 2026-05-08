<template>
  <div class="quick-config-panel">
    <div class="quick-config-head">
      <span class="quick-config-kicker">Locator</span>
      <div class="quick-config-title">滑动查找配置</div>
    </div>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="目标定位方式">
          <a-select
            :model-value="selectedTargetSelectorType"
            @change="value => updateSelectedStepConfig('target_selector_type', value || 'text')"
          >
            <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item label="目标内容">
          <a-input
            :model-value="readSelectedConfigString('target_selector')"
            placeholder="输入目标元素、文本或图片路径"
            @input="value => updateSelectedStepConfig('target_selector', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="6">
        <a-form-item label="滑动方向">
          <a-select
            :model-value="readSelectedConfigString('direction', 'up')"
            @change="value => updateSelectedStepConfig('direction', value || 'up')"
          >
            <a-option v-for="item in swipeDirectionOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :span="6">
        <a-form-item label="最大滑动次数">
          <a-input-number
            :model-value="readSelectedConfigNumber('max_swipes', 5)"
            :min="1"
            :max="100"
            @change="value => updateSelectedStepConfig('max_swipes', value ?? 5)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="6">
        <a-form-item label="每次间隔（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('interval', 0.5)"
            :min="0"
            :max="10"
            :step="0.1"
            @change="value => updateSelectedStepConfig('interval', value ?? 0.5)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="6">
        <a-form-item label="滑动时长（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('duration', 0.4)"
            :min="0.1"
            :max="10"
            :step="0.1"
            @change="value => updateSelectedStepConfig('duration', value ?? 0.4)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="起点坐标（可选）">
          <a-input
            :model-value="readSelectedConfigString('start')"
            placeholder="例如：540,1600"
            @input="value => updateSelectedStepConfig('start', value || undefined)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="终点坐标（可选）">
          <a-input
            :model-value="readSelectedConfigString('end')"
            placeholder="例如：540,600"
            @input="value => updateSelectedStepConfig('end', value || undefined)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row v-if="selectedTargetSelectorType === 'image'" :gutter="12">
      <a-col :span="8">
        <a-form-item label="图片阈值">
          <a-input-number
            :model-value="readSelectedConfigNumber('target_threshold', 0.7)"
            :min="0.1"
            :max="1"
            :step="0.05"
            @change="value => updateSelectedStepConfig('target_threshold', value ?? 0.7)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item label="全屏查找">
          <a-switch
            :model-value="readSelectedConfigBoolean('target_search_full_screen', true)"
            @change="value => updateSelectedStepConfig('target_search_full_screen', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { selectorTypeOptions, swipeDirectionOptions } from './sceneBuilderQuickOptions'
import type {
  SceneBuilderQuickConfigBooleanProps,
  SceneBuilderSelectedTargetSelectorType,
} from './sceneBuilderQuickConfigModels'

interface Props extends SceneBuilderSelectedTargetSelectorType, SceneBuilderQuickConfigBooleanProps {}

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
