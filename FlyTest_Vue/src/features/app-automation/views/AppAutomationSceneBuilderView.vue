<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再进行 APP 场景编排" />
    </div>
    <template v-else>
      <SceneBuilderHeaderBar
        :ai-generating="aiGenerating"
        :loading="loading"
        :saving="saving"
        :executing="executing"
        :has-steps="Boolean(steps.length)"
        @open-ai-plan="openAiPlanDialog"
        @reload-data="loadData"
        @open-testcase-workspace="openTestCaseWorkspace"
        @open-execution-workspace="openExecutionWorkspace()"
        @create-draft="createDraft"
        @open-create-custom-component="openCreateCustomComponent"
        @save-draft="saveDraft"
        @open-execute-dialog="openExecuteDialog"
      />

      <SceneBuilderAiStatusCard
        class="form-card"
        :ai-status-title="aiStatusTitle"
        :ai-status-description="aiStatusDescription"
        :ai-status-color="aiStatusColor"
        :ai-status-label="aiStatusLabel"
        :ai-status-has-config="aiStatus.has_config"
        :ai-status-supports-vision="aiStatus.supports_vision"
        :ai-status-loading="aiStatusLoading"
        :ai-capability-label="aiCapabilityLabel"
        :ai-status-checked-at="aiStatus.checked_at"
        :ai-config-display-name="aiConfigDisplayName"
        :ai-provider-display-name="aiProviderDisplayName"
        :ai-model-display-name="aiModelDisplayName"
        :ai-endpoint-display="aiEndpointDisplay"
        :last-ai-activity="lastAiActivity"
        :format-date-time="formatDateTime"
        :format-provider-label="formatProviderLabel"
        :get-ai-action-label="getAiActionLabel"
        :get-ai-activity-color="getAiActivityColor"
        :get-ai-activity-status-label="getAiActivityStatusLabel"
        @refresh-ai-status="refreshAiRuntimeStatus(true)"
        @open-llm-config="openLlmConfigManagement"
      />

      <SceneBuilderDraftFormCard
        v-model:selected-case-id="selectedCaseId"
        :draft="draft"
        :packages="packages"
        :test-cases="testCases"
        :variable-items="variableItems"
        @case-change="handleCaseChange"
        @add-variable="addVariable"
        @remove-variable="removeVariable"
      />

      <div class="builder-grid">
        <SceneBuilderLibraryPanel
          class="panel-card"
          :component-search="componentSearch"
          :palette-tab="paletteTab"
          :filtered-components="filteredComponents"
          :filtered-custom-components="filteredCustomComponents"
          @update:component-search="componentSearch = $event"
          @update:palette-tab="paletteTab = $event"
          @open-import-dialog="openComponentPackageDialog"
          @open-export-dialog="openComponentPackageExportDialog"
          @append-base="appendBaseComponent"
          @append-custom="appendCustomComponent"
          @edit-custom="openEditCustomComponent"
          @delete-custom="deleteCustomComponent"
        />

        <SceneBuilderCanvasPanel
          class="panel-card"
          :steps="steps"
          :selected-step-index="selectedStepIndex"
          :selected-sub-step-index="selectedSubStepIndex"
          :selected-sub-step-group-key="selectedSubStepGroupKey"
          :sub-step-selections="subStepSelections"
          :components="components"
          :resolve-step-title="resolveStepTitle"
          :resolve-step-meta="resolveStepMeta"
          @update:steps="steps = $event"
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
        />
        <SceneBuilderConfigPanel
          class="panel-card"
          v-model:step-config-text="stepConfigText"
          :selected-scene-step="selectedSceneStep"
          :selected-custom-parent-summary="selectedCustomParentSummary"
          :selected-parent-step="selectedParentStep"
          :count-child-steps="countChildSteps"
          :is-flow-container-step="isFlowContainerStep"
          :resolve-step-meta="resolveStepMeta"
          :ai-step-suggesting="aiStepSuggesting"
          :selected-step-action-type="selectedStepActionType"
          :uses-basic-selector-quick-config="usesBasicSelectorQuickConfig"
          :uses-swipe-to-quick-config="usesSwipeToQuickConfig"
          :uses-swipe-quick-config="usesSwipeQuickConfig"
          :uses-drag-quick-config="usesDragQuickConfig"
          :uses-variable-mutation-quick-config="usesVariableMutationQuickConfig"
          :uses-extract-output-quick-config="usesExtractOutputQuickConfig"
          :uses-api-request-quick-config="usesApiRequestQuickConfig"
          :uses-device-action-quick-config="usesDeviceActionQuickConfig"
          :uses-image-branch-quick-config="usesImageBranchQuickConfig"
          :uses-assert-quick-config="usesAssertQuickConfig"
          :uses-foreach-assert-quick-config="usesForeachAssertQuickConfig"
          :selected-assert-type="selectedAssertType"
          :selected-assert-quick-mode="selectedAssertQuickMode"
          :selected-primary-selector-type="selectedPrimarySelectorType"
          :selected-fallback-selector-type="selectedFallbackSelectorType"
          :selected-click-selector-type="selectedClickSelectorType"
          :selected-target-selector-type="selectedTargetSelectorType"
          :selected-variable-scope="selectedVariableScope"
          :expected-list-text="expectedListText"
          :config-keys="configKeys"
          :read-selected-config-value="readSelectedConfigValue"
          :read-selected-config-string="readSelectedConfigString"
          :read-selected-config-number="readSelectedConfigNumber"
          :read-selected-config-boolean="readSelectedConfigBoolean"
          :update-selected-step-config="updateSelectedStepConfig"
          :format-quick-config-value="formatQuickConfigValue"
          :handle-loose-config-text-change="handleLooseConfigTextChange"
          :handle-json-config-text-change="handleJsonConfigTextChange"
          :handle-expected-list-text-change="handleExpectedListTextChange"
          :handle-assert-type-change="handleAssertTypeChange"
          @open-ai-step-dialog="openAiStepDialog"
          @reset-selected-step-config="resetSelectedStepConfig"
          @apply-step-config="applyStepConfig"
        />
      </div>

      <SceneBuilderComponentPackageImportDialog
        v-model:visible="componentPackageVisible"
        v-model:overwrite="componentPackageOverwrite"
        :loading="componentPackageLoading"
        :uploading="componentPackageUploading"
        :file-list="componentPackageFileList"
        :records="componentPackageRecords"
        @file-change="handleComponentPackageFileChange"
        @delete-record="deleteComponentPackageRecord"
        @submit="submitComponentPackageImport"
      />

      <SceneBuilderComponentPackageExportDialog
        v-model:visible="componentPackageExportVisible"
        v-model:include-disabled="componentPackageIncludeDisabled"
        :exporting="componentPackageExporting"
        :form="componentPackageExportForm"
        @submit-json="downloadComponentPackage('json')"
        @submit-yaml="downloadComponentPackage('yaml')"
      />

      <SceneBuilderAiPlanDialog
        v-model:visible="aiPlanVisible"
        v-model:prompt="aiPlanForm.prompt"
        v-model:apply-mode="aiPlanForm.applyMode"
        :ai-dialog-engine-name="aiDialogEngineName"
        :ai-dialog-mode-text="aiDialogModeText"
        :checked-at-display="formatDateTime(aiStatus.checked_at)"
        :loading="aiGenerating"
        @submit="generateAiPlan"
      />

      <SceneBuilderAiStepDialog
        v-model:visible="aiStepVisible"
        v-model:prompt="aiStepForm.prompt"
        :ai-dialog-engine-name="aiDialogEngineName"
        :ai-dialog-mode-text="aiDialogModeText"
        :checked-at-display="formatDateTime(aiStatus.checked_at)"
        :loading="aiStepSuggesting"
        @submit="generateAiStepSuggestion"
      />

      <SceneBuilderExecuteDialog
        v-model:visible="executeVisible"
        :execution-case-name="executionCaseName"
        :available-devices="availableDevices"
        :form="executeForm"
        :saving="saving"
        :executing="executing"
        @reload-devices="reloadDevices"
        @submit="executeCurrentDraft"
      />

      <SceneBuilderCustomComponentDialog
        v-model:visible="customComponentVisible"
        :mode="customComponentMode"
        :form="customComponentForm"
        :saving="customComponentSaving"
        @submit="saveCustomComponent"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Modal } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import type {
  AppComponent,
  AppCustomComponent,
  AppDevice,
  AppExecution,
  AppPackage,
  AppSceneStep,
  AppTestCase,
} from '../types'
import {
  applyStepEditorPayload as applySceneStepEditorPayload,
  buildStepEditorPayload as buildSceneStepEditorPayload,
  buildVariablePayload as buildSceneVariablePayload,
  clearRecord,
  clone,
  containsCustomStep as containsSceneCustomStep,
  countChildSteps as countSceneChildSteps,
  formatVariableValue,
  getStepGroupSteps as getSceneStepGroupSteps,
  getStepType,
  getSubStepSelectionKey as getSceneSubStepSelectionKey,
  inferVariableType,
  isCustomStep,
  isFlowContainerStep,
  isFlowContainerType,
  isObjectValue,
  mergeVariableDrafts as mergeSceneVariableDrafts,
  normalizeStep as normalizeSceneStep,
  normalizeSteps as normalizeSceneSteps,
  normalizeVariables as normalizeSceneVariables,
  resolveStepMeta as resolveSceneStepMeta,
  resolveStepTitle as resolveSceneStepTitle,
  sanitizeStep as sanitizeSceneStep,
  stripNestedStepKeys,
  toComponentType,
  type SceneDraftOptions,
  type SceneVariableDraft,
  type StepChildGroupKey,
} from './scene-builder/sceneBuilderDraft'
import {
  useSceneBuilderAiRuntime,
} from './scene-builder/useSceneBuilderAiRuntime'
import { useSceneBuilderAiPlanning, type AiApplyMode } from './scene-builder/useSceneBuilderAiPlanning'
import { useSceneBuilderDraftBridge } from './scene-builder/useSceneBuilderDraftBridge'
import { useSceneBuilderComponentPackages } from './scene-builder/useSceneBuilderComponentPackages'
import {
  useSceneBuilderCustomComponents,
} from './scene-builder/useSceneBuilderCustomComponents'
import { useSceneBuilderStepConfig } from './scene-builder/useSceneBuilderStepConfig'
import { useSceneBuilderCanvas } from './scene-builder/useSceneBuilderCanvas'
import { useSceneBuilderSceneState } from './scene-builder/useSceneBuilderSceneState'
import { useSceneBuilderWorkflow } from './scene-builder/useSceneBuilderWorkflow'
import SceneBuilderAiStatusCard from './scene-builder/SceneBuilderAiStatusCard.vue'
import SceneBuilderAiPlanDialog from './scene-builder/SceneBuilderAiPlanDialog.vue'
import SceneBuilderAiStepDialog from './scene-builder/SceneBuilderAiStepDialog.vue'
import SceneBuilderCanvasPanel from './scene-builder/SceneBuilderCanvasPanel.vue'
import SceneBuilderDraftFormCard from './scene-builder/SceneBuilderDraftFormCard.vue'
import SceneBuilderHeaderBar from './scene-builder/SceneBuilderHeaderBar.vue'
import SceneBuilderComponentPackageExportDialog from './scene-builder/SceneBuilderComponentPackageExportDialog.vue'
import SceneBuilderComponentPackageImportDialog from './scene-builder/SceneBuilderComponentPackageImportDialog.vue'
import SceneBuilderConfigPanel from './scene-builder/SceneBuilderConfigPanel.vue'
import SceneBuilderCustomComponentDialog from './scene-builder/SceneBuilderCustomComponentDialog.vue'
import SceneBuilderExecuteDialog from './scene-builder/SceneBuilderExecuteDialog.vue'
import SceneBuilderLibraryPanel from './scene-builder/SceneBuilderLibraryPanel.vue'

type PaletteTab = 'base' | 'custom'

const authStore = useAuthStore()
const projectStore = useProjectStore()
const route = useRoute()
const router = useRouter()

const selectedStepIndex = ref<number | null>(null)
const selectedSubStepIndex = ref<number | null>(null)
const selectedSubStepGroupKey = ref<StepChildGroupKey | null>(null)
const componentSearch = ref('')
const paletteTab = ref<PaletteTab>('base')
const executeVisible = ref(false)

const components = ref<AppComponent[]>([])
const customComponents = ref<AppCustomComponent[]>([])
const steps = ref<AppSceneStep[]>([])
const variableItems = ref<SceneVariableDraft[]>([])

const subStepSelections = reactive<Record<string, string | undefined>>({})

let stepSeed = 0

const generateStepId = () => `scene-step-${Date.now()}-${stepSeed++}`

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const normalizeErrorMessage = (error: any, fallback: string) => error?.message || error?.error || fallback

const {
  aiStatusLoading,
  activeLlmSnapshot,
  lastAiActivity,
  aiStatus,
  aiStatusColor,
  aiStatusLabel,
  aiCapabilityLabel,
  aiConfigDisplayName,
  aiProviderDisplayName,
  aiModelDisplayName,
  aiEndpointDisplay,
  aiStatusTitle,
  aiStatusDescription,
  aiDialogEngineName,
  aiDialogModeText,
  rememberAiActivity,
  refreshAiRuntimeStatus,
  buildLlmConfigSnapshot,
  openLlmConfigManagement,
  formatProviderLabel,
  getAiActionLabel,
  getAiActivityColor,
  getAiActivityStatusLabel,
} = useSceneBuilderAiRuntime({
  router,
  normalizeErrorMessage,
})

const {
  componentMap,
  getStepGroupSteps,
  getSubStepSelectionKey,
  countChildSteps,
  resolveStepTitle,
  resolveStepMeta,
  normalizeStep,
  normalizeSteps,
  sanitizeStep,
  containsCustomStep,
  buildStepEditorPayload,
  applyStepEditorPayload,
  normalizeVariables,
  buildVariablePayload,
  mergeVariableDrafts,
} = useSceneBuilderDraftBridge({
  components,
  customComponents,
  variableItems,
})

const executionCaseName = computed(() => draft.name.trim() || '未命名测试用例')


const isContainerStep = (step?: Partial<AppSceneStep> | null) => Boolean(step && (isCustomStep(step) || isFlowContainerStep(step)))

const setNormalizedGroupSteps = (step: AppSceneStep, groupKey: StepChildGroupKey, items: unknown) => {
  step[groupKey] = normalizeSteps(items)
}

const {
  filteredComponents,
  filteredCustomComponents,
  selectedParentStep,
  selectedSceneStep,
  selectedCustomParentSummary,
  applyGeneratedScenePlan,
  applyStepSuggestion,
} = useSceneBuilderSceneState({
  componentSearch,
  components,
  customComponents,
  steps,
  variableItems,
  getDraft: () => draft,
  selectedStepIndex,
  selectedSubStepIndex,
  selectedSubStepGroupKey,
  getStepGroupSteps,
  isCustomStep,
  normalizeStep,
  normalizeSteps,
  normalizeVariables,
  mergeVariableDrafts,
  syncStepEditor: () => syncStepEditor(),
  generateStepId,
})

const {
  stepConfigText,
  selectedStepActionType,
  usesBasicSelectorQuickConfig,
  usesSwipeToQuickConfig,
  usesSwipeQuickConfig,
  usesDragQuickConfig,
  usesImageBranchQuickConfig,
  usesAssertQuickConfig,
  usesForeachAssertQuickConfig,
  usesVariableMutationQuickConfig,
  usesExtractOutputQuickConfig,
  usesApiRequestQuickConfig,
  usesDeviceActionQuickConfig,
  readSelectedConfigValue,
  readSelectedConfigString,
  readSelectedConfigNumber,
  readSelectedConfigBoolean,
  updateSelectedStepConfig,
  formatQuickConfigValue,
  handleLooseConfigTextChange,
  handleJsonConfigTextChange,
  selectedAssertType,
  selectedAssertQuickMode,
  selectedPrimarySelectorType,
  selectedFallbackSelectorType,
  selectedClickSelectorType,
  selectedTargetSelectorType,
  selectedVariableScope,
  expectedListText,
  handleExpectedListTextChange,
  handleAssertTypeChange,
  configKeys,
  syncStepEditor,
  applyStepConfig,
  resetSelectedStepConfig,
} = useSceneBuilderStepConfig({
  selectedSceneStep,
  selectedCustomParentSummary,
  componentMap,
  buildStepEditorPayload,
  applyStepEditorPayload,
})

const {
  loading,
  saving,
  executing,
  selectedCaseId,
  devices,
  packages,
  testCases,
  draft,
  executeForm,
  availableDevices,
  resetDraft,
  createDraft,
  applyCase,
  reloadDevices,
  loadData,
  persistDraft,
  handleCaseChange,
  openTestCaseWorkspace,
  openExecutionWorkspace,
  openExecuteDialog: openWorkflowExecuteDialog,
  executeCurrentDraft: runWorkflowExecuteCurrentDraft,
} = useSceneBuilderWorkflow({
  route,
  router,
  projectStore,
  authStore,
  components,
  customComponents,
  steps,
  variableItems,
  selectedStepIndex,
  selectedSubStepIndex,
  selectedSubStepGroupKey,
  subStepSelections,
  clearRecord,
  normalizeVariables,
  normalizeSteps,
  sanitizeStep,
  buildVariablePayload,
  syncStepEditor,
  refreshAiRuntimeStatus,
})

const {
  componentPackageLoading,
  componentPackageUploading,
  componentPackageExporting,
  componentPackageVisible,
  componentPackageExportVisible,
  componentPackageRecords,
  componentPackageFileList,
  componentPackageFile,
  componentPackageOverwrite,
  componentPackageIncludeDisabled,
  componentPackageExportForm,
  loadComponentPackageRecords,
  handleComponentPackageFileChange,
  openComponentPackageDialog,
  openComponentPackageExportDialog,
  submitComponentPackageImport,
  deleteComponentPackageRecord,
  downloadComponentPackage,
} = useSceneBuilderComponentPackages({
  reloadData: loadData,
})

const {
  aiGenerating,
  aiStepSuggesting,
  aiPlanVisible,
  aiStepVisible,
  aiPlanForm,
  aiStepForm,
  openAiPlanDialog,
  openAiStepDialog,
  generateAiPlan,
  generateAiStepSuggestion,
} = useSceneBuilderAiPlanning({
  currentProjectId: computed(() => projectStore.currentProjectId),
  selectedSceneStep,
  selectedCustomParentSummary,
  steps,
  draft,
  sanitizeStep,
  buildVariablePayload,
  buildLlmConfigSnapshot,
  activeLlmSnapshot,
  rememberAiActivity,
  normalizeErrorMessage,
  resolveStepMeta,
  resolveStepTitle,
  applyGeneratedScenePlan,
  applyStepSuggestion,
})

const {
  customComponentSaving,
  customComponentVisible,
  customComponentMode,
  editingCustomComponentId,
  customComponentForm,
  openCreateCustomComponent,
  openEditCustomComponent,
  saveCustomComponent,
  deleteCustomComponent,
} = useSceneBuilderCustomComponents({
  steps,
  customComponents,
  loadData,
  onSaved: () => {
    paletteTab.value = 'custom'
  },
  sanitizeStep,
  normalizeSteps,
  containsCustomStep,
  toComponentType,
})

const {
  appendBaseComponent,
  appendCustomComponent,
  selectStep,
  selectSubStep,
  toggleExpand,
  duplicateStep,
  removeStep,
  clearSteps,
  addSubStep,
  duplicateSubStep,
  removeSubStep,
} = useSceneBuilderCanvas({
  steps,
  selectedStepIndex,
  selectedSubStepIndex,
  selectedSubStepGroupKey,
  subStepSelections,
  componentMap,
  clearRecord,
  clone,
  isContainerStep,
  isCustomStep,
  isFlowContainerType,
  normalizeStep,
  normalizeSteps,
  resolveStepTitle,
  sanitizeStep,
  getStepGroupSteps,
  getSubStepSelectionKey,
  syncStepEditor,
  onCustomPaletteActivated: () => {
    paletteTab.value = 'custom'
  },
})

const addVariable = () => {
  variableItems.value.push({
    name: '',
    scope: 'local',
    type: 'string',
    valueText: '',
    description: '',
  })
}

const removeVariable = (index: number) => {
  variableItems.value.splice(index, 1)
}

const updateStepGroupItems = (step: AppSceneStep, groupKey: StepChildGroupKey, items: AppSceneStep[]) => {
  step[groupKey] = items
}

const openExecuteDialog = () => openWorkflowExecuteDialog(executeVisible)

const executeCurrentDraft = () => runWorkflowExecuteCurrentDraft(executeVisible)

const saveDraft = async () => {
  await persistDraft()
}

watch([selectedStepIndex, selectedSubStepIndex, selectedSubStepGroupKey], () => {
  syncStepEditor()
})
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

.ai-status-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-status-header,
.ai-activity-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ai-status-copy,
.ai-activity-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-status-kicker,
.ai-activity-kicker {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--theme-text-secondary);
}

.ai-status-copy strong,
.ai-activity-copy strong {
  color: var(--theme-text);
  font-size: 18px;
}

.ai-status-copy p {
  margin: 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.ai-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.ai-status-item,
.ai-activity-panel {
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.ai-status-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
}

.ai-status-item span {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.ai-status-item strong {
  color: var(--theme-text);
  word-break: break-word;
  overflow-wrap: anywhere;
}

.ai-status-item small {
  color: var(--theme-text-secondary);
  line-height: 1.6;
}

.ai-activity-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-activity-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.ai-activity-summary {
  color: var(--theme-text);
  line-height: 1.7;
  font-weight: 500;
}

.ai-activity-prompt {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(var(--theme-surface-rgb), 0.72);
  color: var(--theme-text-secondary);
  line-height: 1.7;
  word-break: break-word;
}

.ai-warning-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-warning-item,
.ai-activity-empty {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(var(--warning-6), 0.24);
  background: rgba(var(--warning-6), 0.08);
  color: rgb(var(--warning-6));
  line-height: 1.7;
}

.ai-activity-empty {
  border-color: rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.05);
  color: var(--theme-text-secondary);
}

.form-card,
.panel-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.builder-grid {
  display: grid;
  grid-template-columns: 1.05fr 1.2fr 0.95fr;
  gap: 16px;
  min-height: 560px;
}

@media (max-width: 1480px) {
  .builder-grid {
    grid-template-columns: 1fr;
  }

  .ai-status-grid {
    grid-template-columns: 1fr;
  }

}

@media (max-width: 960px) {
  .ai-status-header,
  .ai-activity-header {
    flex-direction: column;
  }
}
</style>




