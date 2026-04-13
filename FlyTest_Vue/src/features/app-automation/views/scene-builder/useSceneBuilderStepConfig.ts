import { Message } from '@arco-design/web-vue'
import { computed, ref, type ComputedRef } from 'vue'
import type { AppComponent, AppSceneStep } from '../../types'
import {
  clone,
  getStepChildGroups,
  getStepGroupSteps,
  getStepType,
  isFlowContainerStep,
  isObjectValue,
  sanitizeStep,
  stripNestedStepKeys,
} from './sceneBuilderDraft'

interface UseSceneBuilderStepConfigOptions {
  selectedSceneStep: ComputedRef<AppSceneStep | null>
  selectedCustomParentSummary: ComputedRef<boolean>
  componentMap: ComputedRef<Map<string, AppComponent>>
  buildStepEditorPayload: (step?: AppSceneStep | null) => Record<string, unknown>
  applyStepEditorPayload: (step: AppSceneStep, payload: Record<string, unknown>) => void
}

export const useSceneBuilderStepConfig = ({
  selectedSceneStep,
  selectedCustomParentSummary,
  componentMap,
  buildStepEditorPayload,
  applyStepEditorPayload,
}: UseSceneBuilderStepConfigOptions) => {
  const stepConfigText = ref('{}')

  const selectedStepActionType = computed(() => getStepType(selectedSceneStep.value))

  const usesBasicSelectorQuickConfig = (action?: string | null) =>
    ['touch', 'double_click', 'long_press', 'text', 'wait', 'assert_exists'].includes(String(action || ''))

  const usesSwipeToQuickConfig = (action?: string | null) => String(action || '') === 'swipe_to'
  const usesSwipeQuickConfig = (action?: string | null) => String(action || '') === 'swipe'
  const usesDragQuickConfig = (action?: string | null) => String(action || '') === 'drag'
  const usesImageBranchQuickConfig = (action?: string | null) =>
    ['image_exists_click', 'image_exists_click_chain'].includes(String(action || ''))
  const usesAssertQuickConfig = (action?: string | null) => String(action || '') === 'assert'
  const usesForeachAssertQuickConfig = (action?: string | null) => String(action || '') === 'foreach_assert'
  const usesVariableMutationQuickConfig = (action?: string | null) =>
    ['set_variable', 'unset_variable'].includes(String(action || ''))
  const usesExtractOutputQuickConfig = (action?: string | null) => String(action || '') === 'extract_output'
  const usesApiRequestQuickConfig = (action?: string | null) => String(action || '') === 'api_request'
  const usesDeviceActionQuickConfig = (action?: string | null) =>
    ['snapshot', 'launch_app', 'stop_app', 'keyevent'].includes(String(action || ''))

  const readSelectedConfigValue = (key: string, fallback: unknown = '') => {
    const step = selectedSceneStep.value
    if (!step || !isObjectValue(step.config)) {
      return fallback
    }
    return step.config[key] ?? fallback
  }

  const readSelectedConfigString = (key: string, fallback = '') => String(readSelectedConfigValue(key, fallback) ?? fallback)

  const readSelectedConfigNumber = (key: string, fallback = 0) => {
    const raw = readSelectedConfigValue(key, fallback)
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : fallback
  }

  const readSelectedConfigBoolean = (key: string, fallback = false) => {
    const raw = readSelectedConfigValue(key, fallback)
    return typeof raw === 'boolean' ? raw : Boolean(raw)
  }

  const syncStepEditor = () => {
    const step = selectedSceneStep.value
    if (!step || selectedCustomParentSummary.value) {
      stepConfigText.value = '{}'
      return
    }
    stepConfigText.value = JSON.stringify(buildStepEditorPayload(step), null, 2)
  }

  const updateSelectedStepConfig = (key: string, value: unknown) => {
    const step = selectedSceneStep.value
    if (!step || selectedCustomParentSummary.value) {
      return
    }
    const nextConfig = isObjectValue(step.config) ? clone(step.config) : {}
    if (value === undefined) {
      delete nextConfig[key]
    } else {
      nextConfig[key] = value
    }
    step.config = nextConfig
    syncStepEditor()
  }

  const formatQuickConfigValue = (value: unknown) => {
    if (value === undefined || value === null) {
      return ''
    }
    if (typeof value === 'string') {
      return value
    }
    if (typeof value === 'number' || typeof value === 'boolean') {
      return String(value)
    }
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }

  const parseLooseEditorValue = (value: string) => {
    const text = String(value || '')
    const trimmed = text.trim()
    if (!trimmed) {
      return ''
    }

    const shouldParseJson =
      trimmed.startsWith('{') ||
      trimmed.startsWith('[') ||
      trimmed.startsWith('"') ||
      trimmed === 'true' ||
      trimmed === 'false' ||
      trimmed === 'null' ||
      /^-?\d+(\.\d+)?$/.test(trimmed)

    if (shouldParseJson) {
      try {
        return JSON.parse(trimmed)
      } catch {
        return text
      }
    }

    return text
  }

  const handleLooseConfigTextChange = (key: string, value: string) => {
    const text = String(value || '')
    if (!text.trim()) {
      updateSelectedStepConfig(key, undefined)
      return
    }
    updateSelectedStepConfig(key, parseLooseEditorValue(text))
  }

  const handleJsonConfigTextChange = (key: string, value: string, emptyValue?: unknown) => {
    const text = String(value || '')
    if (!text.trim()) {
      updateSelectedStepConfig(key, emptyValue)
      return
    }

    try {
      updateSelectedStepConfig(key, JSON.parse(text))
    } catch {
      Message.warning(`${key} 需要填写合法 JSON`)
    }
  }

  const selectedAssertType = computed(() => readSelectedConfigString('assert_type', 'condition'))

  const selectedAssertQuickMode = computed(() => {
    const assertType = selectedAssertType.value
    if (['text', 'number', 'regex', 'range'].includes(assertType)) {
      return 'ocr'
    }
    if (assertType === 'image') {
      return 'image'
    }
    if (['exists', 'not_exists'].includes(assertType)) {
      return 'exists'
    }
    return 'condition'
  })

  const selectedPrimarySelectorType = computed(() => readSelectedConfigString('selector_type', 'element'))
  const selectedFallbackSelectorType = computed(() => readSelectedConfigString('fallback_selector_type', 'element'))
  const selectedClickSelectorType = computed(() => readSelectedConfigString('click_selector_type', 'element'))
  const selectedTargetSelectorType = computed(() => readSelectedConfigString('target_selector_type', 'text'))
  const selectedVariableScope = computed(() => readSelectedConfigString('scope', 'local'))

  const expectedListText = computed(() => {
    const raw = readSelectedConfigValue('expected_list', [])
    if (Array.isArray(raw)) {
      return raw.map(item => String(item ?? '')).join('\n')
    }
    return String(raw || '')
  })

  const handleExpectedListTextChange = (value: string) => {
    const text = String(value || '')
    const trimmed = text.trim()
    if (!trimmed) {
      updateSelectedStepConfig('expected_list', [])
      return
    }

    if (trimmed.startsWith('[')) {
      try {
        const parsed = JSON.parse(trimmed)
        if (Array.isArray(parsed)) {
          updateSelectedStepConfig('expected_list', parsed)
          return
        }
      } catch {
        // Fall back to newline parsing below.
      }
    }

    updateSelectedStepConfig(
      'expected_list',
      text
        .split(/\r?\n/)
        .map(item => item.trim())
        .filter(Boolean),
    )
  }

  const handleAssertTypeChange = (value: string) => {
    const nextType = String(value || 'condition')
    updateSelectedStepConfig('assert_type', nextType)

    if (['text', 'number', 'regex', 'range'].includes(nextType)) {
      updateSelectedStepConfig('selector_type', 'region')
      return
    }

    if (nextType === 'image') {
      updateSelectedStepConfig('selector_type', 'image')
      return
    }

    if (['exists', 'not_exists'].includes(nextType) && !readSelectedConfigString('selector_type', '')) {
      updateSelectedStepConfig('selector_type', 'element')
    }
  }

  const configKeys = computed(() => Object.keys(buildStepEditorPayload(selectedSceneStep.value)))

  const applyStepConfig = () => {
    const step = selectedSceneStep.value
    if (!step || selectedCustomParentSummary.value) {
      return
    }

    try {
      const parsed = JSON.parse(stepConfigText.value || '{}')
      if (!isObjectValue(parsed)) {
        throw new Error('配置 JSON 必须是对象')
      }
      applyStepEditorPayload(step, parsed)
      syncStepEditor()
      Message.success('当前步骤配置已更新')
    } catch (error: any) {
      Message.error(error.message || '步骤配置 JSON 格式不正确')
    }
  }

  const resetSelectedStepConfig = () => {
    const step = selectedSceneStep.value
    if (!step || selectedCustomParentSummary.value) {
      return
    }

    const template = componentMap.value.get(getStepType(step))
    const nextConfig = stripNestedStepKeys(clone(template?.default_config || {}))
    if (isFlowContainerStep(step)) {
      getStepChildGroups(step).forEach(group => {
        nextConfig[group.key] = getStepGroupSteps(step, group.key).map(item => sanitizeStep(item))
      })
    }
    applyStepEditorPayload(step, nextConfig)
    syncStepEditor()
    Message.success('已恢复默认配置')
  }

  return {
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
  }
}
