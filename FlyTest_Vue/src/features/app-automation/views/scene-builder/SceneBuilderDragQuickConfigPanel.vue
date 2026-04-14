<template>
  <div class="quick-config-panel">
    <div class="quick-config-title">拖拽配置</div>
    <a-alert class="quick-config-subtle-alert">
      当前快捷配置按坐标拖拽；如果需要按元素、图片或 OCR 区域定位拖拽起终点，可继续在下方 JSON 中补充
      `start_selector_type`、`start_selector`、`end_selector_type`、`end_selector` 等高级字段。
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
