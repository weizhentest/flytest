<template>
  <div class="quick-config-panel">
    <div class="quick-config-title">滑动配置</div>
    <a-row :gutter="12">
      <a-col :span="12">
        <a-form-item label="起点坐标">
          <a-input
            :model-value="readSelectedConfigString('start')"
            placeholder="例如：540,1600"
            @input="value => updateSelectedStepConfig('start', value)"
          />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="终点坐标">
          <a-input
            :model-value="readSelectedConfigString('end')"
            placeholder="例如：540,600"
            @input="value => updateSelectedStepConfig('end', value)"
          />
        </a-form-item>
      </a-col>
    </a-row>
    <a-row :gutter="12">
      <a-col :span="8">
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
  </div>
</template>

<script setup lang="ts">
import type { SceneBuilderQuickConfigNumericProps } from './sceneBuilderQuickConfigModels'

interface Props extends SceneBuilderQuickConfigNumericProps {}

defineProps<Props>()
</script>
