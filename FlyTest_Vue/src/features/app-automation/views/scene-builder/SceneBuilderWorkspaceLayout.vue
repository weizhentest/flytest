<template>
  <div class="builder-grid">
    <SceneBuilderLibraryPanel
      :component-search="componentSearch"
      :palette-tab="paletteTab"
      :filtered-components="libraryPanel.filteredComponents"
      :filtered-custom-components="libraryPanel.filteredCustomComponents"
      @update:component-search="emit('update:componentSearch', $event)"
      @update:palette-tab="emit('update:paletteTab', $event)"
      @open-import-dialog="emit('open-import-dialog')"
      @open-export-dialog="emit('open-export-dialog')"
      @append-base="emit('append-base', $event)"
      @append-custom="emit('append-custom', $event)"
      @edit-custom="emit('edit-custom', $event)"
      @delete-custom="emit('delete-custom', $event)"
    />

    <SceneBuilderCanvasPanel
      :steps="steps"
      :selected-step-index="canvasPanel.selectedStepIndex"
      :selected-sub-step-index="canvasPanel.selectedSubStepIndex"
      :selected-sub-step-group-key="canvasPanel.selectedSubStepGroupKey"
      :sub-step-selections="canvasPanel.subStepSelections"
      :components="canvasPanel.components"
      :resolve-step-title="canvasPanel.resolveStepTitle"
      :resolve-step-meta="canvasPanel.resolveStepMeta"
      @update:steps="emit('update:steps', $event)"
      @select-step="emit('select-step', $event)"
      @toggle-expand="emit('toggle-expand', $event)"
      @duplicate-step="emit('duplicate-step', $event)"
      @remove-step="emit('remove-step', $event)"
      @clear-steps="emit('clear-steps')"
      @select-sub-step="emit('select-sub-step', $event)"
      @update-sub-step-selection="emit('update-sub-step-selection', $event)"
      @add-sub-step="emit('add-sub-step', $event)"
      @duplicate-sub-step="emit('duplicate-sub-step', $event)"
      @remove-sub-step="emit('remove-sub-step', $event)"
      @update-step-group-items="emit('update-step-group-items', $event)"
    />

    <SceneBuilderConfigPanel
      :step-config-text="stepConfigText"
      :selected-scene-step="configPanel.selectedSceneStep"
      :selected-custom-parent-summary="configPanel.selectedCustomParentSummary"
      :selected-parent-step="configPanel.selectedParentStep"
      :count-child-steps="configPanel.countChildSteps"
      :is-flow-container-step="configPanel.isFlowContainerStep"
      :resolve-step-meta="configPanel.resolveStepMeta"
      :ai-step-suggesting="configPanel.aiStepSuggesting"
      :selected-step-action-type="configPanel.selectedStepActionType"
      :uses-basic-selector-quick-config="configPanel.usesBasicSelectorQuickConfig"
      :uses-swipe-to-quick-config="configPanel.usesSwipeToQuickConfig"
      :uses-swipe-quick-config="configPanel.usesSwipeQuickConfig"
      :uses-drag-quick-config="configPanel.usesDragQuickConfig"
      :uses-variable-mutation-quick-config="configPanel.usesVariableMutationQuickConfig"
      :uses-extract-output-quick-config="configPanel.usesExtractOutputQuickConfig"
      :uses-api-request-quick-config="configPanel.usesApiRequestQuickConfig"
      :uses-device-action-quick-config="configPanel.usesDeviceActionQuickConfig"
      :uses-image-branch-quick-config="configPanel.usesImageBranchQuickConfig"
      :uses-assert-quick-config="configPanel.usesAssertQuickConfig"
      :uses-foreach-assert-quick-config="configPanel.usesForeachAssertQuickConfig"
      :selected-assert-type="configPanel.selectedAssertType"
      :selected-assert-quick-mode="configPanel.selectedAssertQuickMode"
      :selected-primary-selector-type="configPanel.selectedPrimarySelectorType"
      :selected-fallback-selector-type="configPanel.selectedFallbackSelectorType"
      :selected-click-selector-type="configPanel.selectedClickSelectorType"
      :selected-target-selector-type="configPanel.selectedTargetSelectorType"
      :selected-variable-scope="configPanel.selectedVariableScope"
      :expected-list-text="configPanel.expectedListText"
      :config-keys="configPanel.configKeys"
      :read-selected-config-value="configPanel.readSelectedConfigValue"
      :read-selected-config-string="configPanel.readSelectedConfigString"
      :read-selected-config-number="configPanel.readSelectedConfigNumber"
      :read-selected-config-boolean="configPanel.readSelectedConfigBoolean"
      :update-selected-step-config="configPanel.updateSelectedStepConfig"
      :format-quick-config-value="configPanel.formatQuickConfigValue"
      :handle-loose-config-text-change="configPanel.handleLooseConfigTextChange"
      :handle-json-config-text-change="configPanel.handleJsonConfigTextChange"
      :handle-expected-list-text-change="configPanel.handleExpectedListTextChange"
      :handle-assert-type-change="configPanel.handleAssertTypeChange"
      @update:step-config-text="emit('update:stepConfigText', $event)"
      @open-ai-step-dialog="emit('open-ai-step-dialog')"
      @reset-selected-step-config="emit('reset-selected-step-config')"
      @apply-step-config="emit('apply-step-config')"
    />
  </div>
</template>

<script setup lang="ts">
import type { AppComponent, AppCustomComponent, AppSceneStep } from '../../types'
import SceneBuilderCanvasPanel from './SceneBuilderCanvasPanel.vue'
import SceneBuilderConfigPanel from './SceneBuilderConfigPanel.vue'
import SceneBuilderLibraryPanel from './SceneBuilderLibraryPanel.vue'
import type { SceneBuilderWorkspaceLayoutEmits } from './sceneBuilderEventModels'
import type {
  SceneBuilderCanvasPanelBindings,
  SceneBuilderConfigPanelBindings,
  SceneBuilderIndexedSubStepPayload,
  SceneBuilderLibraryPanelBindings,
  SceneBuilderPaletteTab,
  SceneBuilderUpdateStepGroupItemsPayload,
  SceneBuilderUpdateSubStepSelectionPayload,
} from './sceneBuilderViewModels'

interface Props {
  componentSearch: string
  paletteTab: SceneBuilderPaletteTab
  steps: AppSceneStep[]
  stepConfigText: string
  libraryPanel: SceneBuilderLibraryPanelBindings
  canvasPanel: SceneBuilderCanvasPanelBindings
  configPanel: SceneBuilderConfigPanelBindings
}

defineProps<Props>()

const emit = defineEmits<SceneBuilderWorkspaceLayoutEmits>()
</script>

<style scoped>
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
}
</style>
