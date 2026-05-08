<template>
  <div class="quick-config-panel">
    <div class="quick-config-head">
      <span class="quick-config-kicker">Gesture</span>
      <div class="quick-config-title">拖拽配置</div>
    </div>

    <a-alert class="quick-config-subtle-alert">
      当前快捷配置默认按坐标拖拽。如需按元素、图片或 OCR 区域定位起止点，可继续在下方 JSON 中补充
      <code>start_selector_type</code>、<code>start_selector</code>、<code>end_selector_type</code>、
      <code>end_selector</code> 等高级字段。
    </a-alert>

    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="起点坐标">
          <a-input
            :model-value="readSelectedConfigString('start')"
            placeholder="例如：200,800"
            @input="value => updateSelectedStepConfig('start', value)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="终点坐标">
          <a-input
            :model-value="readSelectedConfigString('end')"
            placeholder="例如：800,800"
            @input="value => updateSelectedStepConfig('end', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item label="拖拽时长（秒）">
          <a-input-number
            :model-value="readSelectedConfigNumber('duration', 0.6)"
            :min="0.1"
            :max="10"
            :step="0.1"
            @change="value => updateSelectedStepConfig('duration', value ?? 0.6)"
          />
        </a-form-item>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import type { SceneBuilderQuickConfigNumericProps } from './sceneBuilderQuickConfigModels'

interface Props extends SceneBuilderQuickConfigNumericProps {}

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

.quick-config-subtle-alert {
  border-radius: 14px;
  border: 1px solid rgba(var(--primary-6-rgb), 0.16);
  background: rgba(var(--primary-6-rgb), 0.08);
  color: var(--theme-text-secondary);
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
