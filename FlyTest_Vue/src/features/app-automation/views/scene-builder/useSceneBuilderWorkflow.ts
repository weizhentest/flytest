import { Message } from '@arco-design/web-vue'
import { computed, reactive, ref, watch, type Ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { AppAutomationService } from '../../services/appAutomationService'
import {
  pushAppAutomationExecutions,
  pushAppAutomationTab,
  replaceAppAutomationQuery,
} from '../appAutomationNavigation'
import type { AppComponent, AppCustomComponent, AppDevice, AppExecution, AppPackage, AppSceneStep, AppTestCase } from '../../types'
import type {
  SceneBuilderAuthStoreLike,
  SceneBuilderProjectStoreLike,
  SceneBuilderRecordClearer,
  SceneBuilderStepsNormalizer,
  SceneBuilderStepSanitizer,
  SceneBuilderSyncStepEditor,
  SceneBuilderVariableNormalizer,
  SceneBuilderVariablePayloadBuilder,
} from './sceneBuilderComposableModels'
import type { SceneVariableDraft, StepChildGroupKey } from './sceneBuilderDraft'
import type { SceneBuilderExecuteFormModel } from './sceneBuilderDialogModels'
import type { SceneBuilderDraftFormModel } from './sceneBuilderViewModels'

interface UseSceneBuilderWorkflowOptions {
  route: RouteLocationNormalizedLoaded
  router: Router
  projectStore: SceneBuilderProjectStoreLike
  authStore: SceneBuilderAuthStoreLike
  components: Ref<AppComponent[]>
  customComponents: Ref<AppCustomComponent[]>
  steps: Ref<AppSceneStep[]>
  variableItems: Ref<SceneVariableDraft[]>
  selectedStepIndex: Ref<number | null>
  selectedSubStepIndex: Ref<number | null>
  selectedSubStepGroupKey: Ref<StepChildGroupKey | null>
  subStepSelections: Record<string, string | undefined>
  clearRecord: SceneBuilderRecordClearer
  normalizeVariables: SceneBuilderVariableNormalizer
  normalizeSteps: SceneBuilderStepsNormalizer
  sanitizeStep: SceneBuilderStepSanitizer
  buildVariablePayload: SceneBuilderVariablePayloadBuilder
  syncStepEditor: SceneBuilderSyncStepEditor
  refreshAiRuntimeStatus: () => Promise<unknown>
}

export const useSceneBuilderWorkflow = ({
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
}: UseSceneBuilderWorkflowOptions) => {
  const loading = ref(false)
  const saving = ref(false)
  const executing = ref(false)
  const loadedProjectId = ref<number | null>(null)
  const selectedCaseId = ref<number | undefined>()
  const devices = ref<AppDevice[]>([])
  const packages = ref<AppPackage[]>([])
  const testCases = ref<AppTestCase[]>([])

  const draft = reactive<SceneBuilderDraftFormModel>({
    name: '',
    description: '',
    package_id: undefined,
    timeout: 300,
    retry_count: 0,
  })

  const executeForm = reactive<SceneBuilderExecuteFormModel>({
    device_id: undefined,
  })

  const availableDevices = computed(() =>
    devices.value.filter(device => device.status === 'available' || device.status === 'online'),
  )

  const readRouteCaseId = () => {
    const rawValue = Array.isArray(route.query.caseId) ? route.query.caseId[0] : route.query.caseId
    if (rawValue === undefined || rawValue === null || rawValue === '') {
      return undefined
    }

    const parsed = Number(rawValue)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
  }

  const syncRouteCaseId = (caseId?: number) => {
    const currentCaseId = readRouteCaseId()
    if (currentCaseId === caseId) {
      return
    }

    const nextQuery: Record<string, string> = {}
    Object.entries(route.query).forEach(([key, value]) => {
      if (key === 'caseId') {
        return
      }

      if (Array.isArray(value)) {
        if (value[0] !== undefined) {
          nextQuery[key] = String(value[0])
        }
        return
      }

      if (value !== undefined) {
        nextQuery[key] = String(value)
      }
    })

    if (caseId) {
      nextQuery.caseId = String(caseId)
    }

    void replaceAppAutomationQuery(
      { ...route, query: route.query } as RouteLocationNormalizedLoaded,
      router,
      Object.fromEntries(
        Object.keys({ ...route.query, ...nextQuery }).map(key => [key, key === 'caseId' ? nextQuery.caseId : (nextQuery[key] as string | undefined)]),
      ) as Record<string, string | undefined>,
    )
  }

  const resetDraft = () => {
    selectedCaseId.value = undefined
    selectedStepIndex.value = null
    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
    executeForm.device_id = undefined
    steps.value = []
    variableItems.value = []
    draft.name = ''
    draft.description = ''
    draft.package_id = undefined
    draft.timeout = 300
    draft.retry_count = 0
    clearRecord(subStepSelections)
    syncStepEditor()
  }

  const createDraft = () => {
    resetDraft()
    syncRouteCaseId()
  }

  const applyCase = (record?: AppTestCase) => {
    if (!record) {
      resetDraft()
      return
    }

    selectedCaseId.value = record.id
    draft.name = record.name
    draft.description = record.description
    draft.package_id = record.package_id ?? undefined
    draft.timeout = record.timeout
    draft.retry_count = record.retry_count
    variableItems.value = normalizeVariables(record.variables)
    steps.value = normalizeSteps(record.ui_flow?.steps)
    selectedStepIndex.value = steps.value.length ? 0 : null
    selectedSubStepIndex.value = null
    selectedSubStepGroupKey.value = null
    clearRecord(subStepSelections)
    syncStepEditor()
  }

  const reloadDevices = async () => {
    try {
      devices.value = await AppAutomationService.getDevices()
      return true
    } catch (error: any) {
      Message.error(error.message || '加载设备列表失败')
      return false
    }
  }

  const clearLoadedData = () => {
    components.value = []
    customComponents.value = []
    devices.value = []
    packages.value = []
    testCases.value = []
    loadedProjectId.value = null
  }

  const loadData = async () => {
    if (!projectStore.currentProjectId) {
      clearLoadedData()
      resetDraft()
      return
    }

    loading.value = true
    try {
      const [baseComponents, userComponents, deviceList, packageList, caseList] = await Promise.all([
        AppAutomationService.getComponents(),
        AppAutomationService.getCustomComponents(),
        AppAutomationService.getDevices(),
        AppAutomationService.getPackages(projectStore.currentProjectId),
        AppAutomationService.getTestCases(projectStore.currentProjectId),
        refreshAiRuntimeStatus(),
      ])

      components.value = baseComponents
      customComponents.value = userComponents
      devices.value = deviceList
      packages.value = packageList
      testCases.value = caseList
      loadedProjectId.value = projectStore.currentProjectId

      const activeCaseId = readRouteCaseId() ?? selectedCaseId.value
      if (activeCaseId) {
        const current = caseList.find(item => item.id === activeCaseId)
        if (current) {
          applyCase(current)
        } else if (readRouteCaseId()) {
          resetDraft()
          syncRouteCaseId()
        }
      }
    } catch (error: any) {
      Message.error(error.message || '加载场景编排数据失败')
    } finally {
      loading.value = false
    }
  }

  const validateDraftBeforeSave = () => {
    if (!projectStore.currentProjectId) {
      Message.warning('请先选择项目')
      return false
    }

    if (!draft.name.trim()) {
      Message.warning('请输入用例名称')
      return false
    }

    if (!steps.value.length) {
      Message.warning('请至少添加一个步骤')
      return false
    }

    return true
  }

  const buildTestCasePayload = () => ({
    project_id: projectStore.currentProjectId as number,
    name: draft.name.trim(),
    description: draft.description.trim(),
    package_id: draft.package_id ?? null,
    ui_flow: {
      steps: steps.value.map(item => sanitizeStep(item)),
    },
    variables: buildVariablePayload(),
    tags: [],
    timeout: draft.timeout,
    retry_count: draft.retry_count,
  })

  const persistDraft = async (options: { showMessage?: boolean } = {}) => {
    if (!validateDraftBeforeSave()) {
      return undefined
    }

    const { showMessage = true } = options
    saving.value = true
    try {
      const payload = buildTestCasePayload()

      if (selectedCaseId.value) {
        const updated = await AppAutomationService.updateTestCase(selectedCaseId.value, payload)
        selectedCaseId.value = updated.id
        syncRouteCaseId(updated.id)
        if (showMessage) {
          Message.success('测试用例已更新')
        }
      } else {
        const created = await AppAutomationService.createTestCase(payload)
        selectedCaseId.value = created.id
        syncRouteCaseId(created.id)
        if (showMessage) {
          Message.success('测试用例已创建')
        }
      }

      await loadData()
      return selectedCaseId.value
    } catch (error: any) {
      Message.error(error.message || '保存测试用例失败')
      return undefined
    } finally {
      saving.value = false
    }
  }

  const handleCaseChange = (value?: number) => {
    const record = testCases.value.find(item => item.id === value)
    applyCase(record)
    syncRouteCaseId(record?.id)
  }

  const openTestCaseWorkspace = async () => {
    await pushAppAutomationTab(router, 'test-cases')
  }

  const openExecutionWorkspace = async (executionId?: number) => {
    await pushAppAutomationExecutions(router, { executionId })
  }

  const openExecuteDialog = async (executeVisible: Ref<boolean>) => {
    if (!validateDraftBeforeSave()) {
      return
    }

    if (!availableDevices.value.length) {
      const loaded = await reloadDevices()
      if (!loaded) {
        return
      }
    }

    if (!availableDevices.value.length) {
      Message.warning('暂无可用设备，请先在设备管理中连接并解锁设备')
      return
    }

    if (!executeForm.device_id || !availableDevices.value.some(device => device.id === executeForm.device_id)) {
      executeForm.device_id = availableDevices.value[0]?.id
    }

    executeVisible.value = true
  }

  const executeCurrentDraft = async (executeVisible: Ref<boolean>): Promise<AppExecution | undefined> => {
    if (!executeForm.device_id) {
      Message.warning('请选择执行设备')
      return undefined
    }

    const caseId = await persistDraft({ showMessage: false })
    if (!caseId) {
      return undefined
    }

    executing.value = true
    try {
      const execution = await AppAutomationService.executeTestCase(caseId, {
        device_id: executeForm.device_id,
        trigger_mode: 'manual',
        triggered_by: authStore.currentUser?.username || 'FlyTest',
      })
      executeVisible.value = false
      Message.success('执行任务已启动，正在跳转到执行记录')
      await openExecutionWorkspace(execution.id)
      return execution
    } catch (error: any) {
      Message.error(error.message || '启动执行任务失败')
      return undefined
    } finally {
      executing.value = false
    }
  }

  watch(
    () => projectStore.currentProjectId,
    () => {
      resetDraft()
      clearLoadedData()
      if (route.query.tab === 'scene-builder' && projectStore.currentProjectId) {
        void loadData()
      }
    },
    { immediate: true },
  )

  watch(
    () => route.query.tab,
    tab => {
      if (
        tab === 'scene-builder' &&
        projectStore.currentProjectId &&
        loadedProjectId.value !== projectStore.currentProjectId
      ) {
        void loadData()
      }
    },
  )

  watch(
    () => [route.query.tab, route.query.caseId],
    () => {
      if (route.query.tab !== 'scene-builder') {
        return
      }

      if (!projectStore.currentProjectId) {
        return
      }

      const routeCaseId = readRouteCaseId()
      if (!routeCaseId) {
        if (selectedCaseId.value !== undefined) {
          resetDraft()
        }
        return
      }

      if (selectedCaseId.value === routeCaseId) {
        return
      }

      const record = testCases.value.find(item => item.id === routeCaseId)
      if (record) {
        applyCase(record)
        return
      }

      if (!loading.value) {
        void loadData()
      }
    },
  )

  return {
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
    validateDraftBeforeSave,
    buildTestCasePayload,
    persistDraft,
    handleCaseChange,
    openTestCaseWorkspace,
    openExecutionWorkspace,
    openExecuteDialog,
    executeCurrentDraft,
  }
}
