<template>
<a-card class="config-panel">
          <template #title>步骤配置</template>
          <div v-if="!selectedSceneStep" class="config-empty">请选择一个步骤进行配置</div>

          <SceneBuilderCustomParentSummary
            v-else-if="selectedCustomParentSummary"
            :selected-parent-step="selectedParentStep"
            :count-child-steps="countChildSteps"
          />

          <div v-else class="config-form">
            <a-form layout="vertical">
              <SceneBuilderConfigHeaderSection
                :selected-scene-step="selectedSceneStep"
                :resolve-step-meta="resolveStepMeta"
                :is-flow-container-step="isFlowContainerStep"
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
                @open-ai-step-dialog="emit('open-ai-step-dialog')"
              />

              <SceneBuilderBasicSelectorQuickConfigPanel
                v-if="usesBasicSelectorQuickConfig(selectedStepActionType)"
                :selected-step-action-type="selectedStepActionType"
                :selected-primary-selector-type="selectedPrimarySelectorType"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :read-selected-config-boolean="readSelectedConfigBoolean"
                :update-selected-step-config="updateSelectedStepConfig"
              />

              <SceneBuilderSwipeToQuickConfigPanel
                v-if="usesSwipeToQuickConfig(selectedStepActionType)"
                :selected-target-selector-type="selectedTargetSelectorType"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :read-selected-config-boolean="readSelectedConfigBoolean"
                :update-selected-step-config="updateSelectedStepConfig"
              />

              <SceneBuilderSwipeQuickConfigPanel
                v-if="usesSwipeQuickConfig(selectedStepActionType)"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :update-selected-step-config="updateSelectedStepConfig"
              />

              <SceneBuilderDragQuickConfigPanel
                v-if="usesDragQuickConfig(selectedStepActionType)"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :update-selected-step-config="updateSelectedStepConfig"
              />

              <SceneBuilderVariableMutationQuickConfigPanel
                v-if="usesVariableMutationQuickConfig(selectedStepActionType)"
                :selected-step-action-type="selectedStepActionType"
                :selected-variable-scope="selectedVariableScope"
                :read-selected-config-value="readSelectedConfigValue"
                :read-selected-config-string="readSelectedConfigString"
                :update-selected-step-config="updateSelectedStepConfig"
                :format-quick-config-value="formatQuickConfigValue"
                :handle-loose-config-text-change="handleLooseConfigTextChange"
              />

              <SceneBuilderExtractOutputQuickConfigPanel
                v-if="usesExtractOutputQuickConfig(selectedStepActionType)"
                :selected-variable-scope="selectedVariableScope"
                :read-selected-config-string="readSelectedConfigString"
                :update-selected-step-config="updateSelectedStepConfig"
              />

              <SceneBuilderApiRequestQuickConfigPanel
                v-if="usesApiRequestQuickConfig(selectedStepActionType)"
                :selected-variable-scope="selectedVariableScope"
                :read-selected-config-value="readSelectedConfigValue"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :update-selected-step-config="updateSelectedStepConfig"
                :format-quick-config-value="formatQuickConfigValue"
                :handle-loose-config-text-change="handleLooseConfigTextChange"
                :handle-json-config-text-change="handleJsonConfigTextChange"
              />

              <SceneBuilderDeviceActionQuickConfigPanel
                v-if="usesDeviceActionQuickConfig(selectedStepActionType)"
                :selected-step-action-type="selectedStepActionType"
                :read-selected-config-string="readSelectedConfigString"
                :update-selected-step-config="updateSelectedStepConfig"
              />

              <SceneBuilderAssertQuickConfigPanel
                v-if="usesAssertQuickConfig(selectedStepActionType)"
                :selected-assert-type="selectedAssertType"
                :selected-assert-quick-mode="selectedAssertQuickMode"
                :selected-primary-selector-type="selectedPrimarySelectorType"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :read-selected-config-boolean="readSelectedConfigBoolean"
                :update-selected-step-config="updateSelectedStepConfig"
                :handle-assert-type-change="handleAssertTypeChange"
              />

              <SceneBuilderImageBranchQuickConfigPanel
                v-if="usesImageBranchQuickConfig(selectedStepActionType)"
                :selected-step-action-type="selectedStepActionType"
                :selected-primary-selector-type="selectedPrimarySelectorType"
                :selected-fallback-selector-type="selectedFallbackSelectorType"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :read-selected-config-boolean="readSelectedConfigBoolean"
                :update-selected-step-config="updateSelectedStepConfig"
              />

              <SceneBuilderForeachAssertQuickConfigPanel
                v-if="usesForeachAssertQuickConfig(selectedStepActionType)"
                :selected-click-selector-type="selectedClickSelectorType"
                :expected-list-text="expectedListText"
                :read-selected-config-string="readSelectedConfigString"
                :read-selected-config-number="readSelectedConfigNumber"
                :read-selected-config-boolean="readSelectedConfigBoolean"
                :update-selected-step-config="updateSelectedStepConfig"
                :handle-expected-list-text-change="handleExpectedListTextChange"
              />
              <SceneBuilderConfigJsonEditor
                v-model:step-config-text="stepConfigTextModel"
                :config-keys="configKeys"
                @reset-selected-step-config="emit('reset-selected-step-config')"
                @apply-step-config="emit('apply-step-config')"
              />
            </a-form>
          </div>
        </a-card>
</template>


<script setup lang="ts">
import {
  SceneBuilderApiRequestQuickConfigPanel,
  SceneBuilderAssertQuickConfigPanel,
  SceneBuilderBasicSelectorQuickConfigPanel,
  SceneBuilderConfigHeaderSection,
  SceneBuilderConfigJsonEditor,
  SceneBuilderCustomParentSummary,
  SceneBuilderDragQuickConfigPanel,
  SceneBuilderDeviceActionQuickConfigPanel,
  SceneBuilderExtractOutputQuickConfigPanel,
  SceneBuilderForeachAssertQuickConfigPanel,
  SceneBuilderImageBranchQuickConfigPanel,
  SceneBuilderSwipeQuickConfigPanel,
  SceneBuilderSwipeToQuickConfigPanel,
  SceneBuilderVariableMutationQuickConfigPanel,
} from './sceneBuilderConfigParts'
import type { SceneBuilderConfigPanelEmits } from './sceneBuilderEventModels'
import type { SceneBuilderConfigPanelBindings } from './sceneBuilderViewModels'

defineProps<SceneBuilderConfigPanelBindings>()

const stepConfigTextModel = defineModel<string>('stepConfigText', { required: true })

const emit = defineEmits<SceneBuilderConfigPanelEmits>()

</script>


<style scoped>
.config-panel {
  min-height: 560px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.config-empty,
.config-empty-text {
  color: var(--theme-text-secondary);
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.quick-config-panel {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.quick-config-title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--theme-text);
}

.quick-config-subtle-alert {
  margin-bottom: 12px;
  background: rgba(var(--theme-surface-rgb), 0.72);
}

</style>

