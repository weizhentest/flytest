<template>
  <div class="config-summary">
    <a-form layout="vertical">
      <a-form-item label="组件名称">
        <a-input v-model="selectedParentStep!.name" />
      </a-form-item>
      <a-form-item label="组件类型">
        <a-input :model-value="selectedParentStep!.component_type || selectedParentStep!.type || 'custom'" disabled />
      </a-form-item>
      <a-form-item label="子步骤数量">
        <a-input :model-value="String(countChildSteps(selectedParentStep))" disabled />
      </a-form-item>
    </a-form>
    <a-alert>
      当前选中的是自定义组件父步骤，请展开后编辑子步骤；这里可以直接修改组件在当前场景中的显示名称。
    </a-alert>
  </div>
</template>

<script setup lang="ts">
import type { AppSceneStep } from '../../types'

interface Props {
  selectedParentStep: AppSceneStep | null
  countChildSteps: (step?: Partial<AppSceneStep> | null) => number
}

defineProps<Props>()
</script>

<style scoped>
.config-summary {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>
