import type { AppSceneStep } from '../../types'
import type { SceneVariableDraft, StepChildGroupKey } from './sceneBuilderDraft'
import type { SceneBuilderDraftIdentityModel } from './sceneBuilderViewModels'

export type SceneBuilderErrorNormalizer = (error: any, fallback: string) => string
export type SceneBuilderRecordClearer = (record: Record<string, unknown>) => void
export type SceneBuilderValueCloner = <T>(value: T) => T

export type SceneBuilderContainerChecker = (step?: Partial<AppSceneStep> | null) => boolean
export type SceneBuilderCustomStepChecker = (step?: Partial<AppSceneStep> | null) => boolean
export type SceneBuilderFlowContainerTypeChecker = (value?: string | null) => boolean

export type SceneBuilderStepNormalizer = (
  input: Partial<AppSceneStep>,
  forcedKind?: 'base' | 'custom',
) => AppSceneStep

export type SceneBuilderStepsNormalizer = (
  items: unknown,
  forcedKind?: 'base' | 'custom',
) => AppSceneStep[]

export type SceneBuilderStepSanitizer = (step: AppSceneStep) => AppSceneStep
export type SceneBuilderStepTitleResolver = (step?: Partial<AppSceneStep>) => string
export type SceneBuilderStepMetaResolver = (step?: Partial<AppSceneStep>) => string
export type SceneBuilderContainsCustomStep = (step: AppSceneStep) => boolean

export type SceneBuilderVariableNormalizer = (items: unknown) => SceneVariableDraft[]
export type SceneBuilderVariableDraftMerger = (
  currentItems: SceneVariableDraft[],
  incomingItems: SceneVariableDraft[],
) => SceneVariableDraft[]
export type SceneBuilderVariablePayloadBuilder = () => Array<Record<string, unknown>>

export type SceneBuilderStepGroupReader = (
  step: AppSceneStep,
  groupKey: StepChildGroupKey,
) => AppSceneStep[]
export type SceneBuilderSubStepSelectionKeyGetter = (
  step: AppSceneStep,
  groupKey: StepChildGroupKey,
) => string

export type SceneBuilderSyncStepEditor = () => void
export type SceneBuilderGenerateStepId = () => string
export type SceneBuilderLoadData = () => Promise<void>
export type SceneBuilderDraftGetter = () => SceneBuilderDraftIdentityModel

export type SceneBuilderStepEditorPayloadBuilder = (
  step?: AppSceneStep | null,
) => Record<string, unknown>
export type SceneBuilderStepEditorPayloadApplier = (
  step: AppSceneStep,
  payload: Record<string, unknown>,
) => void

export interface SceneBuilderProjectStoreLike {
  currentProjectId?: number | null
}

export interface SceneBuilderAuthStoreLike {
  currentUser?: { username?: string | null } | null
}
