import { computed, type Ref } from 'vue'
import type {
  AppComponent,
  AppCustomComponent,
  AppScenePlanResponse,
  AppSceneStep,
  AppStepSuggestionResponse,
} from '../../types'
import type { SceneVariableDraft, StepChildGroupKey } from './sceneBuilderDraft'
import type { AiApplyMode } from './useSceneBuilderAiPlanning'

interface DraftModel {
  name: string
  description: string
  package_id?: number | null
}

interface UseSceneBuilderSceneStateOptions {
  componentSearch: Ref<string>
  components: Ref<AppComponent[]>
  customComponents: Ref<AppCustomComponent[]>
  steps: Ref<AppSceneStep[]>
  variableItems: Ref<SceneVariableDraft[]>
  getDraft: () => DraftModel
  selectedStepIndex: Ref<number | null>
  selectedSubStepIndex: Ref<number | null>
  selectedSubStepGroupKey: Ref<StepChildGroupKey | null>
  getStepGroupSteps: (step: AppSceneStep, groupKey: StepChildGroupKey) => AppSceneStep[]
  isCustomStep: (step?: Partial<AppSceneStep> | null) => boolean
  normalizeStep: (input: Partial<AppSceneStep>, forcedKind?: 'base' | 'custom') => AppSceneStep
  normalizeSteps: (items: unknown, forcedKind?: 'base' | 'custom') => AppSceneStep[]
  normalizeVariables: (items: unknown) => SceneVariableDraft[]
  mergeVariableDrafts: (currentItems: SceneVariableDraft[], incomingItems: SceneVariableDraft[]) => SceneVariableDraft[]
  syncStepEditor: () => void
  generateStepId: () => string
}

export const useSceneBuilderSceneState = ({
  componentSearch,
  components,
  customComponents,
  steps,
  variableItems,
  getDraft,
  selectedStepIndex,
  selectedSubStepIndex,
  selectedSubStepGroupKey,
  getStepGroupSteps,
  isCustomStep,
  normalizeStep,
  normalizeSteps,
  normalizeVariables,
  mergeVariableDrafts,
  syncStepEditor,
  generateStepId,
}: UseSceneBuilderSceneStateOptions) => {
  const filteredComponents = computed(() => {
    const keyword = componentSearch.value.trim().toLowerCase()
    if (!keyword) {
      return components.value
    }
    return components.value.filter(item =>
      [item.name, item.type, item.description, item.category]
        .join(' ')
        .toLowerCase()
        .includes(keyword),
    )
  })

  const filteredCustomComponents = computed(() => {
    const keyword = componentSearch.value.trim().toLowerCase()
    if (!keyword) {
      return customComponents.value
    }
    return customComponents.value.filter(item =>
      [item.name, item.type, item.description]
        .join(' ')
        .toLowerCase()
        .includes(keyword),
    )
  })

  const selectedParentStep = computed(() => {
    if (selectedStepIndex.value === null) {
      return null
    }
    return steps.value[selectedStepIndex.value] || null
  })

  const selectedSceneStep = computed(() => {
    const parentStep = selectedParentStep.value
    if (!parentStep) {
      return null
    }
    if (selectedSubStepIndex.value === null) {
      return parentStep
    }
    if (!selectedSubStepGroupKey.value) {
      return null
    }
    return getStepGroupSteps(parentStep, selectedSubStepGroupKey.value)[selectedSubStepIndex.value] || null
  })

  const selectedCustomParentSummary = computed(
    () => Boolean(selectedParentStep.value && selectedSubStepIndex.value === null && isCustomStep(selectedParentStep.value)),
  )

  const applyGeneratedScenePlan = (plan: AppScenePlanResponse, applyMode: AiApplyMode) => {
    const draft = getDraft()
    const normalizedPlanSteps = normalizeSteps(plan.steps)
    const normalizedPlanVariables = normalizeVariables(plan.variables)

    if (applyMode === 'replace') {
      steps.value = normalizedPlanSteps
      variableItems.value = normalizedPlanVariables
      draft.name = plan.name || draft.name
      draft.description = plan.description || draft.description
      draft.package_id = plan.package_id ?? undefined
      selectedStepIndex.value = steps.value.length ? 0 : null
    } else {
      const startIndex = steps.value.length
      steps.value = [...steps.value, ...normalizedPlanSteps]
      variableItems.value = mergeVariableDrafts(variableItems.value, normalizedPlanVariables)

      if (!draft.name.trim() && plan.name) {
        draft.name = plan.name
      }
      if (!draft.description.trim() && plan.description) {
        draft.description = plan.description
      }
      if (draft.package_id === undefined && plan.package_id !== null) {
        draft.package_id = plan.package_id
      }

      selectedStepIndex.value = steps.value.length ? startIndex : null
    }

    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
    syncStepEditor()
  }

  const replaceSelectedSceneStep = (nextStep: AppSceneStep) => {
    const currentStep = selectedSceneStep.value
    if (!currentStep) {
      return
    }

    const preservedId = currentStep.id ?? generateStepId()
    const preservedExpanded = Boolean(currentStep._expanded)
    const normalized = normalizeStep({
      ...nextStep,
      id: preservedId,
      _expanded: preservedExpanded || Boolean(nextStep._expanded),
    })

    const currentRecord = currentStep as Record<string, unknown>
    Object.keys(currentRecord).forEach(key => {
      delete currentRecord[key]
    })
    Object.assign(currentRecord, normalized)
  }

  const applyStepSuggestion = (suggestion: AppStepSuggestionResponse) => {
    const normalizedStep = normalizeStep(suggestion.step)
    replaceSelectedSceneStep(normalizedStep)
    variableItems.value = mergeVariableDrafts(variableItems.value, normalizeVariables(suggestion.variables))
    syncStepEditor()
  }

  return {
    filteredComponents,
    filteredCustomComponents,
    selectedParentStep,
    selectedSceneStep,
    selectedCustomParentSummary,
    applyGeneratedScenePlan,
    applyStepSuggestion,
  }
}
