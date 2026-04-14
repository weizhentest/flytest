<template>
  <a-alert v-if="selectedSceneStep && isFlowContainerStep(selectedSceneStep)" class="config-flow-alert">
    流程容器步骤的 JSON 同时支持维护 `steps`、`else_steps`、`catch_steps`、`finally_steps`。
  </a-alert>

  <a-form-item label="步骤名称">
    <a-input v-model="selectedSceneStep!.name" placeholder="请输入步骤名称" />
  </a-form-item>
  <a-form-item label="步骤类型">
    <a-input :model-value="resolveStepMeta(selectedSceneStep)" disabled />
  </a-form-item>
  <div class="config-toolbar">
    <a-button
      type="outline"
      size="small"
      :disabled="!selectedSceneStep"
      :loading="aiStepSuggesting"
      @click="emit('open-ai-step-dialog')"
    >
      AI 补全当前步骤
    </a-button>
  </div>

  <a-alert v-if="showQuickConfigHelper" class="config-helper-alert">
    常用图片、OCR 和断言参数可以直接在下方快捷配置；更复杂的字段仍然可以继续在 JSON 中补充。
  </a-alert>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { AppSceneStep } from '../../types'

interface Props {
  selectedSceneStep: AppSceneStep | null
  resolveStepMeta: (step?: Partial<AppSceneStep>) => string
  isFlowContainerStep: (step?: Partial<AppSceneStep> | null) => boolean
  aiStepSuggesting: boolean
  selectedStepActionType: string
  usesBasicSelectorQuickConfig: (action?: string | null) => boolean
  usesSwipeToQuickConfig: (action?: string | null) => boolean
  usesSwipeQuickConfig: (action?: string | null) => boolean
  usesDragQuickConfig: (action?: string | null) => boolean
  usesVariableMutationQuickConfig: (action?: string | null) => boolean
  usesExtractOutputQuickConfig: (action?: string | null) => boolean
  usesApiRequestQuickConfig: (action?: string | null) => boolean
  usesDeviceActionQuickConfig: (action?: string | null) => boolean
  usesImageBranchQuickConfig: (action?: string | null) => boolean
  usesAssertQuickConfig: (action?: string | null) => boolean
  usesForeachAssertQuickConfig: (action?: string | null) => boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'open-ai-step-dialog': []
}>()

const showQuickConfigHelper = computed(() => {
  const action = props.selectedStepActionType
  return (
    props.usesBasicSelectorQuickConfig(action) ||
    props.usesSwipeToQuickConfig(action) ||
    props.usesSwipeQuickConfig(action) ||
    props.usesDragQuickConfig(action) ||
    props.usesVariableMutationQuickConfig(action) ||
    props.usesExtractOutputQuickConfig(action) ||
    props.usesApiRequestQuickConfig(action) ||
    props.usesDeviceActionQuickConfig(action) ||
    props.usesImageBranchQuickConfig(action) ||
    props.usesAssertQuickConfig(action) ||
    props.usesForeachAssertQuickConfig(action)
  )
})
</script>

<style scoped>
.config-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-top: -6px;
}

.config-flow-alert {
  margin-bottom: 4px;
}

.config-helper-alert {
  margin-bottom: 4px;
}
</style>
