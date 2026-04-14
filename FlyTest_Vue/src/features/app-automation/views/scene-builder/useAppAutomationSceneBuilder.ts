import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import type {
  AppComponent,
  AppCustomComponent,
  AppSceneStep,
} from '../../types'
import {
  clearRecord,
  clone,
  isCustomStep,
  isFlowContainerStep,
  isFlowContainerType,
  normalizeStep as normalizeSceneStep,
  normalizeSteps as normalizeSceneSteps,
  normalizeVariables as normalizeSceneVariables,
  toComponentType,
  type SceneVariableDraft,
  type StepChildGroupKey,
} from './sceneBuilderDraft'
import {
  useSceneBuilderAiPlanning,
  useSceneBuilderAiRuntime,
  useSceneBuilderCanvas,
  useSceneBuilderComponentPackages,
  useSceneBuilderCustomComponents,
  useSceneBuilderDraftBridge,
  useSceneBuilderSceneState,
  useSceneBuilderStepConfig,
  useSceneBuilderWorkflow,
} from './sceneBuilderComposables'
import type {
  SceneBuilderAiStatusSectionProps,
  SceneBuilderCanvasPanelBindings,
  SceneBuilderConfigPanelBindings,
  SceneBuilderPaletteTab,
  SceneBuilderDraftSectionProps,
  SceneBuilderHeaderSectionProps,
  SceneBuilderLibraryPanelBindings,
} from './sceneBuilderViewModels'

export function useAppAutomationSceneBuilder() {
  const authStore = useAuthStore()
  const projectStore = useProjectStore()
  const route = useRoute()
  const router = useRouter()

  const selectedStepIndex = ref<number | null>(null)
  const selectedSubStepIndex = ref<number | null>(null)
  const selectedSubStepGroupKey = ref<StepChildGroupKey | null>(null)
  const componentSearch = ref('')
  const paletteTab = ref<SceneBuilderPaletteTab>('base')
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

  const normalizeErrorMessage = (error: any, fallback: string) =>
    error?.message || error?.error || fallback

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

  const headerSectionProps = computed<SceneBuilderHeaderSectionProps>(() => ({
    aiGenerating: aiGenerating.value,
    loading: loading.value,
    saving: saving.value,
    executing: executing.value,
    hasSteps: Boolean(steps.value.length),
  }))

  const aiStatusSectionProps = computed<SceneBuilderAiStatusSectionProps>(() => ({
    aiStatusTitle: aiStatusTitle.value,
    aiStatusDescription: aiStatusDescription.value,
    aiStatusColor: aiStatusColor.value,
    aiStatusLabel: aiStatusLabel.value,
    aiStatusHasConfig: aiStatus.has_config,
    aiStatusSupportsVision: aiStatus.supports_vision,
    aiStatusLoading: aiStatusLoading.value,
    aiCapabilityLabel: aiCapabilityLabel.value,
    aiStatusCheckedAt: aiStatus.checked_at,
    aiConfigDisplayName: aiConfigDisplayName.value,
    aiProviderDisplayName: aiProviderDisplayName.value,
    aiModelDisplayName: aiModelDisplayName.value,
    aiEndpointDisplay: aiEndpointDisplay.value,
    lastAiActivity: lastAiActivity.value,
    formatDateTime,
    formatProviderLabel,
    getAiActionLabel,
    getAiActivityColor,
    getAiActivityStatusLabel,
  }))

  const draftSectionProps = computed<SceneBuilderDraftSectionProps>(() => ({
    draft,
    packages: packages.value,
    testCases: testCases.value,
    variableItems: variableItems.value,
  }))

  const isContainerStep = (step?: Partial<AppSceneStep> | null) =>
    Boolean(step && (isCustomStep(step) || isFlowContainerStep(step)))

  const setNormalizedGroupSteps = (
    step: AppSceneStep,
    groupKey: StepChildGroupKey,
    items: unknown,
  ) => {
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
    componentPackageOverwrite,
    componentPackageIncludeDisabled,
    componentPackageExportForm,
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

  const libraryPanelProps = computed<SceneBuilderLibraryPanelBindings>(() => ({
    filteredComponents: filteredComponents.value,
    filteredCustomComponents: filteredCustomComponents.value,
  }))

  const canvasPanelProps = computed<SceneBuilderCanvasPanelBindings>(() => ({
    selectedStepIndex: selectedStepIndex.value,
    selectedSubStepIndex: selectedSubStepIndex.value,
    selectedSubStepGroupKey: selectedSubStepGroupKey.value,
    subStepSelections,
    components: components.value,
    resolveStepTitle,
    resolveStepMeta,
  }))

  const configPanelProps = computed<SceneBuilderConfigPanelBindings>(() => ({
    selectedSceneStep: selectedSceneStep.value,
    selectedCustomParentSummary: selectedCustomParentSummary.value,
    selectedParentStep: selectedParentStep.value,
    countChildSteps,
    isFlowContainerStep,
    resolveStepMeta,
    aiStepSuggesting: aiStepSuggesting.value,
    selectedStepActionType: selectedStepActionType.value,
    usesBasicSelectorQuickConfig,
    usesSwipeToQuickConfig,
    usesSwipeQuickConfig,
    usesDragQuickConfig,
    usesVariableMutationQuickConfig,
    usesExtractOutputQuickConfig,
    usesApiRequestQuickConfig,
    usesDeviceActionQuickConfig,
    usesImageBranchQuickConfig,
    usesAssertQuickConfig,
    usesForeachAssertQuickConfig,
    selectedAssertType: selectedAssertType.value,
    selectedAssertQuickMode: selectedAssertQuickMode.value,
    selectedPrimarySelectorType: selectedPrimarySelectorType.value,
    selectedFallbackSelectorType: selectedFallbackSelectorType.value,
    selectedClickSelectorType: selectedClickSelectorType.value,
    selectedTargetSelectorType: selectedTargetSelectorType.value,
    selectedVariableScope: selectedVariableScope.value,
    expectedListText: expectedListText.value,
    configKeys: configKeys.value,
    readSelectedConfigValue,
    readSelectedConfigString,
    readSelectedConfigNumber,
    readSelectedConfigBoolean,
    updateSelectedStepConfig,
    formatQuickConfigValue,
    handleLooseConfigTextChange,
    handleJsonConfigTextChange,
    handleExpectedListTextChange,
    handleAssertTypeChange,
  }))

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

  const updateStepGroupItems = (
    step: AppSceneStep,
    groupKey: StepChildGroupKey,
    items: AppSceneStep[],
  ) => {
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

  return {
    projectStore,
    aiGenerating,
    loading,
    saving,
    executing,
    headerSectionProps,
    aiStatusSectionProps,
    draftSectionProps,
    steps,
    openAiPlanDialog,
    loadData,
    openTestCaseWorkspace,
    openExecutionWorkspace,
    createDraft,
    openCreateCustomComponent,
    saveDraft,
    openExecuteDialog,
    aiStatusTitle,
    aiStatusDescription,
    aiStatusColor,
    aiStatusLabel,
    aiStatus,
    aiStatusLoading,
    aiCapabilityLabel,
    aiConfigDisplayName,
    aiProviderDisplayName,
    aiModelDisplayName,
    aiEndpointDisplay,
    lastAiActivity,
    formatDateTime,
    formatProviderLabel,
    getAiActionLabel,
    getAiActivityColor,
    getAiActivityStatusLabel,
    refreshAiRuntimeStatus,
    openLlmConfigManagement,
    selectedCaseId,
    draft,
    packages,
    testCases,
    variableItems,
    handleCaseChange,
    addVariable,
    removeVariable,
    componentSearch,
    paletteTab,
    filteredComponents,
    filteredCustomComponents,
    libraryPanelProps,
    canvasPanelProps,
    configPanelProps,
    openComponentPackageDialog,
    openComponentPackageExportDialog,
    appendBaseComponent,
    appendCustomComponent,
    openEditCustomComponent,
    deleteCustomComponent,
    selectedStepIndex,
    selectedSubStepIndex,
    selectedSubStepGroupKey,
    subStepSelections,
    components,
    resolveStepTitle,
    resolveStepMeta,
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
    stepConfigText,
    selectedSceneStep,
    selectedCustomParentSummary,
    selectedParentStep,
    countChildSteps,
    isFlowContainerStep,
    aiStepSuggesting,
    selectedStepActionType,
    usesBasicSelectorQuickConfig,
    usesSwipeToQuickConfig,
    usesSwipeQuickConfig,
    usesDragQuickConfig,
    usesVariableMutationQuickConfig,
    usesExtractOutputQuickConfig,
    usesApiRequestQuickConfig,
    usesDeviceActionQuickConfig,
    usesImageBranchQuickConfig,
    usesAssertQuickConfig,
    usesForeachAssertQuickConfig,
    selectedAssertType,
    selectedAssertQuickMode,
    selectedPrimarySelectorType,
    selectedFallbackSelectorType,
    selectedClickSelectorType,
    selectedTargetSelectorType,
    selectedVariableScope,
    expectedListText,
    configKeys,
    readSelectedConfigValue,
    readSelectedConfigString,
    readSelectedConfigNumber,
    readSelectedConfigBoolean,
    updateSelectedStepConfig,
    formatQuickConfigValue,
    handleLooseConfigTextChange,
    handleJsonConfigTextChange,
    handleExpectedListTextChange,
    handleAssertTypeChange,
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
    aiPlanVisible,
    aiPlanForm,
    aiDialogEngineName,
    aiDialogModeText,
    generateAiPlan,
    aiStepVisible,
    aiStepForm,
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
  }
}
