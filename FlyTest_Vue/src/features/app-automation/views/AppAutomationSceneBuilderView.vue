<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再进行 APP 场景编排" />
    </div>
    <template v-else>
      <SceneBuilderTopSection
        :header="headerSectionProps"
        :ai-status-card="aiStatusSectionProps"
        :draft-form="draftSectionProps"
        :selected-case-id="selectedCaseId"
        @open-ai-plan="openAiPlanDialog"
        @reload-data="loadData"
        @open-testcase-workspace="openTestCaseWorkspace"
        @open-execution-workspace="openExecutionWorkspace()"
        @create-draft="createDraft"
        @open-create-custom-component="openCreateCustomComponent"
        @save-draft="saveDraft"
        @open-execute-dialog="openExecuteDialog"
        @refresh-ai-status="refreshAiRuntimeStatus(true)"
        @open-llm-config="openLlmConfigManagement"
        @update:selected-case-id="selectedCaseId = $event"
        @case-change="handleCaseChange"
        @add-variable="addVariable"
        @remove-variable="removeVariable"
      />

      <SceneBuilderWorkspaceLayout
        v-model:component-search="componentSearch"
        v-model:palette-tab="paletteTab"
        v-model:steps="steps"
        v-model:step-config-text="stepConfigText"
        :library-panel="libraryPanelProps"
        :canvas-panel="canvasPanelProps"
        :config-panel="configPanelProps"
        @open-import-dialog="openComponentPackageDialog"
        @open-export-dialog="openComponentPackageExportDialog"
        @append-base="appendBaseComponent"
        @append-custom="appendCustomComponent"
        @edit-custom="openEditCustomComponent"
        @delete-custom="deleteCustomComponent"
        @select-step="selectStep"
        @toggle-expand="toggleExpand"
        @duplicate-step="duplicateStep"
        @remove-step="removeStep"
        @clear-steps="clearSteps"
        @select-sub-step="payload => selectSubStep(payload.index, payload.groupKey, payload.subIndex)"
        @update-sub-step-selection="payload => (subStepSelections[payload.key] = payload.value)"
        @add-sub-step="payload => addSubStep(payload.index, payload.groupKey)"
        @duplicate-sub-step="payload => duplicateSubStep(payload.index, payload.groupKey, payload.subIndex)"
        @remove-sub-step="payload => removeSubStep(payload.index, payload.groupKey, payload.subIndex)"
        @update-step-group-items="payload => updateStepGroupItems(payload.step, payload.groupKey, payload.items)"
        @open-ai-step-dialog="openAiStepDialog"
        @reset-selected-step-config="resetSelectedStepConfig"
        @apply-step-config="applyStepConfig"
      />

      <SceneBuilderDialogsHost
        v-model:component-package-visible="componentPackageVisible"
        v-model:component-package-overwrite="componentPackageOverwrite"
        v-model:component-package-export-visible="componentPackageExportVisible"
        v-model:component-package-include-disabled="componentPackageIncludeDisabled"
        v-model:ai-plan-visible="aiPlanVisible"
        v-model:ai-plan-prompt="aiPlanForm.prompt"
        v-model:ai-plan-apply-mode="aiPlanForm.applyMode"
        v-model:ai-step-visible="aiStepVisible"
        v-model:ai-step-prompt="aiStepForm.prompt"
        v-model:execute-visible="executeVisible"
        v-model:custom-component-visible="customComponentVisible"
        :component-package-loading="componentPackageLoading"
        :component-package-uploading="componentPackageUploading"
        :component-package-file-list="componentPackageFileList"
        :component-package-records="componentPackageRecords"
        :component-package-exporting="componentPackageExporting"
        :component-package-export-form="componentPackageExportForm"
        :ai-dialog-engine-name="aiDialogEngineName"
        :ai-dialog-mode-text="aiDialogModeText"
        :ai-checked-at-display="formatDateTime(aiStatus.checked_at)"
        :ai-generating="aiGenerating"
        :ai-step-suggesting="aiStepSuggesting"
        :execution-case-name="executionCaseName"
        :available-devices="availableDevices"
        :execute-form="executeForm"
        :saving="saving"
        :executing="executing"
        :custom-component-mode="customComponentMode"
        :custom-component-form="customComponentForm"
        :custom-component-saving="customComponentSaving"
        @file-change="handleComponentPackageFileChange"
        @delete-record="deleteComponentPackageRecord"
        @submit-component-package-import="submitComponentPackageImport"
        @submit-export-json="downloadComponentPackage('json')"
        @submit-export-yaml="downloadComponentPackage('yaml')"
        @submit-ai-plan="generateAiPlan"
        @submit-ai-step="generateAiStepSuggestion"
        @reload-devices="reloadDevices"
        @submit-execute="executeCurrentDraft"
        @submit-custom-component="saveCustomComponent"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  SceneBuilderDialogsHost,
  SceneBuilderTopSection,
  SceneBuilderWorkspaceLayout,
  useAppAutomationSceneBuilder,
} from './scene-builder'

const {
  projectStore,
  aiGenerating,
  saving,
  executing,
  steps,
  headerSectionProps,
  aiStatusSectionProps,
  draftSectionProps,
  openAiPlanDialog,
  loadData,
  openTestCaseWorkspace,
  openExecutionWorkspace,
  createDraft,
  openCreateCustomComponent,
  saveDraft,
  openExecuteDialog,
  formatDateTime,
  refreshAiRuntimeStatus,
  openLlmConfigManagement,
  selectedCaseId,
  handleCaseChange,
  addVariable,
  removeVariable,
  componentSearch,
  paletteTab,
  libraryPanelProps,
  canvasPanelProps,
  configPanelProps,
  subStepSelections,
  stepConfigText,
  openComponentPackageDialog,
  openComponentPackageExportDialog,
  appendBaseComponent,
  appendCustomComponent,
  openEditCustomComponent,
  deleteCustomComponent,
  selectStep,
  toggleExpand,
  duplicateStep,
  removeStep,
  clearSteps,
  selectSubStep,
  addSubStep,
  duplicateSubStep,
  removeSubStep,
  updateStepGroupItems,
  openAiStepDialog,
  resetSelectedStepConfig,
  applyStepConfig,
  componentPackageVisible,
  componentPackageOverwrite,
  componentPackageLoading,
  componentPackageUploading,
  componentPackageFileList,
  componentPackageRecords,
  handleComponentPackageFileChange,
  deleteComponentPackageRecord,
  submitComponentPackageImport,
  componentPackageExportVisible,
  componentPackageIncludeDisabled,
  componentPackageExporting,
  componentPackageExportForm,
  downloadComponentPackage,
  aiStatus,
  aiPlanVisible,
  aiPlanForm,
  aiDialogEngineName,
  aiDialogModeText,
  generateAiPlan,
  aiStepVisible,
  aiStepForm,
  aiStepSuggesting,
  generateAiStepSuggestion,
  executeVisible,
  executionCaseName,
  availableDevices,
  executeForm,
  reloadDevices,
  executeCurrentDraft,
  customComponentVisible,
  customComponentMode,
  customComponentForm,
  customComponentSaving,
  saveCustomComponent,
} = useAppAutomationSceneBuilder()
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-shell {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}
</style>




