import type { AppComponent, AppCustomComponent, AppPackage, AppSceneStep, AppTestCase } from '../../types'
import type { SceneVariableDraft, StepChildGroupKey } from './sceneBuilderDraft'
import type { AiActivityRecord } from './useSceneBuilderAiRuntime'

export type SceneBuilderPaletteTab = 'base' | 'custom'

export interface SceneBuilderHeaderSectionProps {
  aiGenerating: boolean
  loading: boolean
  saving: boolean
  executing: boolean
  hasSteps: boolean
}

export interface SceneBuilderAiStatusSectionProps {
  aiStatusTitle: string
  aiStatusDescription: string
  aiStatusColor: string
  aiStatusLabel: string
  aiStatusHasConfig: boolean
  aiStatusSupportsVision: boolean
  aiStatusLoading: boolean
  aiCapabilityLabel: string
  aiStatusCheckedAt?: string | null
  aiConfigDisplayName: string
  aiProviderDisplayName: string
  aiModelDisplayName: string
  aiEndpointDisplay: string
  lastAiActivity: AiActivityRecord | null
  formatDateTime: (value?: string | null) => string
  formatProviderLabel: (value?: string | null) => string
  getAiActionLabel: (action: AiActivityRecord['action']) => string
  getAiActivityColor: (record: AiActivityRecord) => string
  getAiActivityStatusLabel: (record: AiActivityRecord) => string
}

export interface SceneBuilderDraftFormModel {
  name: string
  description: string
  package_id?: number | null
  timeout: number
  retry_count: number
}

export type SceneBuilderDraftIdentityModel = Pick<
  SceneBuilderDraftFormModel,
  'name' | 'description' | 'package_id'
>

export interface SceneBuilderDraftSectionProps {
  draft: SceneBuilderDraftFormModel
  packages: AppPackage[]
  testCases: AppTestCase[]
  variableItems: SceneVariableDraft[]
}

export interface SceneBuilderLibraryPanelBindings {
  filteredComponents: AppComponent[]
  filteredCustomComponents: AppCustomComponent[]
}

export interface SceneBuilderCanvasPanelBindings {
  selectedStepIndex: number | null
  selectedSubStepIndex: number | null
  selectedSubStepGroupKey: StepChildGroupKey | null
  subStepSelections: Record<string, string | undefined>
  components: AppComponent[]
  resolveStepTitle: (step?: Partial<AppSceneStep>) => string
  resolveStepMeta: (step?: Partial<AppSceneStep>) => string
}

export interface SceneBuilderConfigPanelBindings {
  selectedSceneStep: AppSceneStep | null
  selectedCustomParentSummary: boolean
  selectedParentStep: AppSceneStep | null
  countChildSteps: (step?: Partial<AppSceneStep> | null) => number
  isFlowContainerStep: (step?: Partial<AppSceneStep> | null) => boolean
  resolveStepMeta: (step?: Partial<AppSceneStep>) => string
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
  selectedAssertType: string
  selectedAssertQuickMode: string
  selectedPrimarySelectorType: string
  selectedFallbackSelectorType: string
  selectedClickSelectorType: string
  selectedTargetSelectorType: string
  selectedVariableScope: string
  expectedListText: string
  configKeys: string[]
  readSelectedConfigValue: (key: string, fallback?: unknown) => unknown
  readSelectedConfigString: (key: string, fallback?: string) => string
  readSelectedConfigNumber: (key: string, fallback?: number) => number
  readSelectedConfigBoolean: (key: string, fallback?: boolean) => boolean
  updateSelectedStepConfig: (key: string, value: unknown) => void
  formatQuickConfigValue: (value: unknown) => string
  handleLooseConfigTextChange: (key: string, value: string) => void
  handleJsonConfigTextChange: (key: string, value: string, emptyValue?: unknown) => void
  handleExpectedListTextChange: (value: string) => void
  handleAssertTypeChange: (value: string) => void
}

export interface SceneBuilderIndexedSubStepPayload {
  index: number
  groupKey: StepChildGroupKey
  subIndex: number
}

export interface SceneBuilderAddSubStepPayload {
  index: number
  groupKey: StepChildGroupKey
}

export interface SceneBuilderUpdateStepGroupItemsPayload {
  step: AppSceneStep
  groupKey: StepChildGroupKey
  items: AppSceneStep[]
}

export interface SceneBuilderUpdateSubStepSelectionPayload {
  key: string
  value?: string
}
