import { computed, type Ref } from 'vue'
import type { AppComponent, AppCustomComponent, AppSceneStep } from '../../types'
import {
  applyStepEditorPayload as applySceneStepEditorPayload,
  buildStepEditorPayload as buildSceneStepEditorPayload,
  buildVariablePayload as buildSceneVariablePayload,
  containsCustomStep as containsSceneCustomStep,
  countChildSteps as countSceneChildSteps,
  getStepGroupSteps as getSceneStepGroupSteps,
  getSubStepSelectionKey as getSceneSubStepSelectionKey,
  mergeVariableDrafts as mergeSceneVariableDrafts,
  normalizeStep as normalizeSceneStep,
  normalizeSteps as normalizeSceneSteps,
  normalizeVariables as normalizeSceneVariables,
  resolveStepMeta as resolveSceneStepMeta,
  resolveStepTitle as resolveSceneStepTitle,
  sanitizeStep as sanitizeSceneStep,
  type SceneDraftOptions,
  type SceneVariableDraft,
  type StepChildGroupKey,
} from './sceneBuilderDraft'

interface UseSceneBuilderDraftBridgeOptions {
  components: Ref<AppComponent[]>
  customComponents: Ref<AppCustomComponent[]>
  variableItems: Ref<SceneVariableDraft[]>
}

export const useSceneBuilderDraftBridge = ({
  components,
  customComponents,
  variableItems,
}: UseSceneBuilderDraftBridgeOptions) => {
  const componentMap = computed(() => new Map(components.value.map(item => [item.type, item])))

  const componentNameMap = computed(() => {
    const entries = [
      ...components.value.map(item => [item.type, item.name] as const),
      ...customComponents.value.map(item => [item.type, item.name] as const),
    ]
    return new Map(entries)
  })

  const sceneDraftOptions = (): SceneDraftOptions => ({
    resolveComponentName: componentType => componentNameMap.value.get(componentType),
  })

  const getStepGroupSteps = (step: AppSceneStep, groupKey: StepChildGroupKey) => getSceneStepGroupSteps(step, groupKey)

  const getSubStepSelectionKey = (step: AppSceneStep, groupKey: StepChildGroupKey) =>
    getSceneSubStepSelectionKey(step, groupKey)

  const countChildSteps = (step?: Partial<AppSceneStep> | null) => countSceneChildSteps(step)

  const resolveStepTitle = (step?: Partial<AppSceneStep>) => resolveSceneStepTitle(step, sceneDraftOptions())

  const resolveStepMeta = (step?: Partial<AppSceneStep>) => resolveSceneStepMeta(step, sceneDraftOptions())

  const normalizeStep = (input: Partial<AppSceneStep>, forcedKind?: 'base' | 'custom') =>
    normalizeSceneStep(input, forcedKind, sceneDraftOptions())

  const normalizeSteps = (items: unknown, forcedKind?: 'base' | 'custom') =>
    normalizeSceneSteps(items, forcedKind, sceneDraftOptions())

  const sanitizeStep = (step: AppSceneStep) => sanitizeSceneStep(step, sceneDraftOptions())

  const containsCustomStep = (step: AppSceneStep): boolean => containsSceneCustomStep(step)

  const buildStepEditorPayload = (step?: AppSceneStep | null) => buildSceneStepEditorPayload(step, sceneDraftOptions())

  const applyStepEditorPayload = (step: AppSceneStep, payload: Record<string, unknown>) =>
    applySceneStepEditorPayload(step, payload, sceneDraftOptions())

  const normalizeVariables = (items: unknown): SceneVariableDraft[] => normalizeSceneVariables(items)

  const buildVariablePayload = () => buildSceneVariablePayload(variableItems.value)

  const mergeVariableDrafts = (currentItems: SceneVariableDraft[], incomingItems: SceneVariableDraft[]) =>
    mergeSceneVariableDrafts(currentItems, incomingItems)

  return {
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
  }
}
