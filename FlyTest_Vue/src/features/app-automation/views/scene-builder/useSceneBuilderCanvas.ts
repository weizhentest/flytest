import { Message } from '@arco-design/web-vue'
import type { ComputedRef, Ref } from 'vue'
import type { AppComponent, AppCustomComponent, AppSceneStep } from '../../types'
import type { StepChildGroupKey } from './sceneBuilderDraft'
import type {
  SceneBuilderContainerChecker,
  SceneBuilderCustomStepChecker,
  SceneBuilderFlowContainerTypeChecker,
  SceneBuilderRecordClearer,
  SceneBuilderStepGroupReader,
  SceneBuilderStepNormalizer,
  SceneBuilderStepsNormalizer,
  SceneBuilderStepSanitizer,
  SceneBuilderStepTitleResolver,
  SceneBuilderSubStepSelectionKeyGetter,
  SceneBuilderSyncStepEditor,
  SceneBuilderValueCloner,
} from './sceneBuilderComposableModels'

interface UseSceneBuilderCanvasOptions {
  steps: Ref<AppSceneStep[]>
  selectedStepIndex: Ref<number | null>
  selectedSubStepIndex: Ref<number | null>
  selectedSubStepGroupKey: Ref<StepChildGroupKey | null>
  subStepSelections: Record<string, string | undefined>
  componentMap: ComputedRef<Map<string, AppComponent>>
  clearRecord: SceneBuilderRecordClearer
  clone: SceneBuilderValueCloner
  isContainerStep: SceneBuilderContainerChecker
  isCustomStep: SceneBuilderCustomStepChecker
  isFlowContainerType: SceneBuilderFlowContainerTypeChecker
  normalizeStep: SceneBuilderStepNormalizer
  normalizeSteps: SceneBuilderStepsNormalizer
  resolveStepTitle: SceneBuilderStepTitleResolver
  sanitizeStep: SceneBuilderStepSanitizer
  getStepGroupSteps: SceneBuilderStepGroupReader
  getSubStepSelectionKey: SceneBuilderSubStepSelectionKeyGetter
  syncStepEditor: SceneBuilderSyncStepEditor
  onCustomPaletteActivated?: () => void
}

export const useSceneBuilderCanvas = ({
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
  onCustomPaletteActivated,
}: UseSceneBuilderCanvasOptions) => {
  const buildBaseStep = (component: AppComponent) =>
    normalizeStep(
      {
        name: component.name,
        kind: 'base',
        type: component.type,
        action: component.type,
        component_type: component.type,
        config: clone(component.default_config || {}),
        _expanded: isFlowContainerType(component.type),
      },
      'base',
    )

  const buildCustomStep = (component: AppCustomComponent) =>
    normalizeStep(
      {
        name: component.name,
        kind: 'custom',
        type: component.type,
        action: component.type,
        component_type: component.type,
        config: clone(component.default_config || {}),
        steps: normalizeSteps(component.steps || []),
        _expanded: true,
      },
      'custom',
    )

  const cloneSceneStep = (step: AppSceneStep) => {
    const duplicated = normalizeStep(clone(step), isCustomStep(step) ? 'custom' : 'base')
    duplicated.name = `${step.name || resolveStepTitle(step)} 副本`
    return duplicated
  }

  const selectStep = (index: number) => {
    selectedStepIndex.value = index
    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
  }

  const selectSubStep = (parentIndex: number, groupKey: StepChildGroupKey, subIndex: number) => {
    selectedStepIndex.value = parentIndex
    selectedSubStepGroupKey.value = groupKey
    selectedSubStepIndex.value = subIndex
  }

  const appendBaseComponent = (component: AppComponent) => {
    steps.value.push(buildBaseStep(component))
    selectedStepIndex.value = steps.value.length - 1
    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
  }

  const appendCustomComponent = (component: AppCustomComponent) => {
    steps.value.push(buildCustomStep(component))
    selectedStepIndex.value = steps.value.length - 1
    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
    onCustomPaletteActivated?.()
  }

  const toggleExpand = (index: number) => {
    const step = steps.value[index]
    if (!isContainerStep(step)) {
      return
    }

    step._expanded = !step._expanded
    if (!step._expanded && selectedStepIndex.value === index && selectedSubStepIndex.value !== null) {
      selectedSubStepIndex.value = null
      selectedSubStepGroupKey.value = null
    }
  }

  const duplicateStep = (index: number) => {
    const source = steps.value[index]
    if (!source) {
      return
    }

    steps.value.splice(index + 1, 0, cloneSceneStep(source))
    selectedStepIndex.value = index + 1
    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
  }

  const removeStep = (index: number) => {
    steps.value.splice(index, 1)

    if (!steps.value.length) {
      selectedStepIndex.value = null
      selectedSubStepIndex.value = null
      selectedSubStepGroupKey.value = null
      return
    }

    if (selectedStepIndex.value === index) {
      selectedStepIndex.value = Math.min(index, steps.value.length - 1)
      selectedSubStepIndex.value = null
      selectedSubStepGroupKey.value = null
    } else if (selectedStepIndex.value !== null && selectedStepIndex.value > index) {
      selectedStepIndex.value -= 1
    }
  }

  const clearSteps = () => {
    steps.value = []
    selectedStepIndex.value = null
    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
    clearRecord(subStepSelections)
    syncStepEditor()
  }

  const setNormalizedGroupSteps = (step: AppSceneStep, groupKey: StepChildGroupKey, items: unknown) => {
    step[groupKey] = normalizeSteps(items)
  }

  const addSubStep = (parentIndex: number, groupKey: StepChildGroupKey) => {
    const parentStep = steps.value[parentIndex]
    if (!isContainerStep(parentStep)) {
      return
    }

    const selectedType = subStepSelections[getSubStepSelectionKey(parentStep, groupKey)]
    if (!selectedType) {
      Message.warning('请先选择一个基础组件')
      return
    }

    const component = componentMap.value.get(selectedType)
    if (!component) {
      Message.warning('未找到对应的基础组件')
      return
    }

    const nextSteps = [...getStepGroupSteps(parentStep, groupKey), buildBaseStep(component)]
    setNormalizedGroupSteps(parentStep, groupKey, nextSteps)
    parentStep._expanded = true
    selectSubStep(parentIndex, groupKey, nextSteps.length - 1)
  }

  const duplicateSubStep = (parentIndex: number, groupKey: StepChildGroupKey, subIndex: number) => {
    const parentStep = steps.value[parentIndex]
    if (!parentStep) {
      return
    }

    const currentSteps = [...getStepGroupSteps(parentStep, groupKey)]
    const source = currentSteps[subIndex]
    if (!source) {
      return
    }

    currentSteps.splice(subIndex + 1, 0, cloneSceneStep(source))
    setNormalizedGroupSteps(parentStep, groupKey, currentSteps)
    selectSubStep(parentIndex, groupKey, subIndex + 1)
  }

  const removeSubStep = (parentIndex: number, groupKey: StepChildGroupKey, subIndex: number) => {
    const parentStep = steps.value[parentIndex]
    if (!parentStep) {
      return
    }

    const nextSteps = [...getStepGroupSteps(parentStep, groupKey)]
    nextSteps.splice(subIndex, 1)
    setNormalizedGroupSteps(parentStep, groupKey, nextSteps)

    if (
      selectedStepIndex.value === parentIndex &&
      selectedSubStepGroupKey.value === groupKey &&
      selectedSubStepIndex.value !== null
    ) {
      if (!nextSteps.length) {
        selectedSubStepIndex.value = null
        selectedSubStepGroupKey.value = null
      } else if (selectedSubStepIndex.value === subIndex) {
        selectedSubStepIndex.value = Math.min(subIndex, nextSteps.length - 1)
      } else if (selectedSubStepIndex.value > subIndex) {
        selectedSubStepIndex.value -= 1
      }
    }
  }

  return {
    buildBaseStep,
    buildCustomStep,
    cloneSceneStep,
    appendBaseComponent,
    appendCustomComponent,
    selectStep,
    selectSubStep,
    toggleExpand,
    duplicateStep,
    removeStep,
    clearSteps,
    setNormalizedGroupSteps,
    addSubStep,
    duplicateSubStep,
    removeSubStep,
  }
}
