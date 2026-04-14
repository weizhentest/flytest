<template>
  <SceneBuilderComponentPackageImportDialog
    v-model:visible="componentPackageVisibleModel"
    v-model:overwrite="componentPackageOverwriteModel"
    :loading="componentPackageLoading"
    :uploading="componentPackageUploading"
    :file-list="componentPackageFileList"
    :records="componentPackageRecords"
    @file-change="(fileListParam, fileItem) => emit('file-change', fileListParam, fileItem)"
    @delete-record="emit('delete-record', $event)"
    @submit="emit('submit-component-package-import')"
  />

  <SceneBuilderComponentPackageExportDialog
    v-model:visible="componentPackageExportVisibleModel"
    v-model:include-disabled="componentPackageIncludeDisabledModel"
    :exporting="componentPackageExporting"
    :form="componentPackageExportForm"
    @submit-json="emit('submit-export-json')"
    @submit-yaml="emit('submit-export-yaml')"
  />

  <SceneBuilderAiPlanDialog
    v-model:visible="aiPlanVisibleModel"
    v-model:prompt="aiPlanPromptModel"
    v-model:apply-mode="aiPlanApplyModeModel"
    :ai-dialog-engine-name="aiDialogEngineName"
    :ai-dialog-mode-text="aiDialogModeText"
    :checked-at-display="aiCheckedAtDisplay"
    :loading="aiGenerating"
    @submit="emit('submit-ai-plan')"
  />

  <SceneBuilderAiStepDialog
    v-model:visible="aiStepVisibleModel"
    v-model:prompt="aiStepPromptModel"
    :ai-dialog-engine-name="aiDialogEngineName"
    :ai-dialog-mode-text="aiDialogModeText"
    :checked-at-display="aiCheckedAtDisplay"
    :loading="aiStepSuggesting"
    @submit="emit('submit-ai-step')"
  />

  <SceneBuilderExecuteDialog
    v-model:visible="executeVisibleModel"
    :execution-case-name="executionCaseName"
    :available-devices="availableDevices"
    :form="executeForm"
    :saving="saving"
    :executing="executing"
    @reload-devices="emit('reload-devices')"
    @submit="emit('submit-execute')"
  />

  <SceneBuilderCustomComponentDialog
    v-model:visible="customComponentVisibleModel"
    :mode="customComponentMode"
    :form="customComponentForm"
    :saving="customComponentSaving"
    @submit="emit('submit-custom-component')"
  />
</template>

<script setup lang="ts">
import type { AiApplyMode } from './useSceneBuilderAiPlanning'
import type { SceneBuilderDialogsHostProps } from './sceneBuilderDialogModels'
import type { SceneBuilderDialogsHostEmits } from './sceneBuilderEventModels'
import SceneBuilderAiPlanDialog from './SceneBuilderAiPlanDialog.vue'
import SceneBuilderAiStepDialog from './SceneBuilderAiStepDialog.vue'
import SceneBuilderComponentPackageExportDialog from './SceneBuilderComponentPackageExportDialog.vue'
import SceneBuilderComponentPackageImportDialog from './SceneBuilderComponentPackageImportDialog.vue'
import SceneBuilderCustomComponentDialog from './SceneBuilderCustomComponentDialog.vue'
import SceneBuilderExecuteDialog from './SceneBuilderExecuteDialog.vue'

defineProps<SceneBuilderDialogsHostProps>()

const componentPackageVisibleModel = defineModel<boolean>('componentPackageVisible', { required: true })
const componentPackageOverwriteModel = defineModel<boolean>('componentPackageOverwrite', { required: true })
const componentPackageExportVisibleModel = defineModel<boolean>('componentPackageExportVisible', { required: true })
const componentPackageIncludeDisabledModel = defineModel<boolean>('componentPackageIncludeDisabled', { required: true })
const aiPlanVisibleModel = defineModel<boolean>('aiPlanVisible', { required: true })
const aiPlanPromptModel = defineModel<string>('aiPlanPrompt', { required: true })
const aiPlanApplyModeModel = defineModel<AiApplyMode>('aiPlanApplyMode', { required: true })
const aiStepVisibleModel = defineModel<boolean>('aiStepVisible', { required: true })
const aiStepPromptModel = defineModel<string>('aiStepPrompt', { required: true })
const executeVisibleModel = defineModel<boolean>('executeVisible', { required: true })
const customComponentVisibleModel = defineModel<boolean>('customComponentVisible', { required: true })

const emit = defineEmits<SceneBuilderDialogsHostEmits>()
</script>
