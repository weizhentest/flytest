import { Message } from '@arco-design/web-vue'
import { reactive, ref, watch, type ComputedRef, type Ref } from 'vue'
import { AppAutomationService } from '../../services/appAutomationService'
import type {
  AppLlmConfigSnapshot,
  AppScenePlanResponse,
  AppSceneStep,
  AppStepSuggestionResponse,
} from '../../types'
import type {
  SceneBuilderAiPlanFormModel,
  SceneBuilderAiStepFormModel,
} from './sceneBuilderDialogModels'
import type {
  SceneBuilderErrorNormalizer,
  SceneBuilderStepMetaResolver,
  SceneBuilderStepSanitizer,
  SceneBuilderStepTitleResolver,
  SceneBuilderVariablePayloadBuilder,
} from './sceneBuilderComposableModels'
import type { SceneBuilderDraftIdentityModel } from './sceneBuilderViewModels'
import type { AiActivityRecord } from './useSceneBuilderAiRuntime'

export type AiApplyMode = 'replace' | 'append'

interface UseSceneBuilderAiPlanningOptions {
  currentProjectId: ComputedRef<number | null | undefined>
  selectedSceneStep: ComputedRef<AppSceneStep | null>
  selectedCustomParentSummary: ComputedRef<boolean>
  steps: Ref<AppSceneStep[]>
  draft: SceneBuilderDraftIdentityModel
  sanitizeStep: SceneBuilderStepSanitizer
  buildVariablePayload: SceneBuilderVariablePayloadBuilder
  buildLlmConfigSnapshot: () => Promise<AppLlmConfigSnapshot | null>
  activeLlmSnapshot: Ref<AppLlmConfigSnapshot | null>
  rememberAiActivity: (payload: Omit<AiActivityRecord, 'executed_at'>) => void
  normalizeErrorMessage: SceneBuilderErrorNormalizer
  resolveStepMeta: SceneBuilderStepMetaResolver
  resolveStepTitle: SceneBuilderStepTitleResolver
  applyGeneratedScenePlan: (plan: AppScenePlanResponse, applyMode: AiApplyMode) => void
  applyStepSuggestion: (suggestion: AppStepSuggestionResponse) => void
}

export const useSceneBuilderAiPlanning = ({
  currentProjectId,
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
}: UseSceneBuilderAiPlanningOptions) => {
  const aiGenerating = ref(false)
  const aiStepSuggesting = ref(false)
  const aiPlanVisible = ref(false)
  const aiStepVisible = ref(false)

  const aiPlanForm = reactive<SceneBuilderAiPlanFormModel>({
    prompt: '',
    applyMode: 'replace' as AiApplyMode,
  })

  const aiStepForm = reactive<SceneBuilderAiStepFormModel>({
    prompt: '',
  })

  const resetAiPlanState = () => {
    aiPlanForm.prompt = ''
    aiPlanForm.applyMode = 'replace'
  }

  const resetAiStepState = () => {
    aiStepForm.prompt = ''
  }

  const readCurrentVariables = () => {
    try {
      return buildVariablePayload()
    } catch {
      return []
    }
  }

  const openAiStepDialog = () => {
    const step = selectedSceneStep.value
    if (!step || selectedCustomParentSummary.value) {
      Message.warning('请先选择一个可编辑的步骤')
      return
    }

    const promptParts = [step.name?.trim(), resolveStepMeta(step), draft.description.trim()].filter(Boolean)
    aiStepForm.prompt = aiStepForm.prompt.trim() || promptParts.join('，')
    aiStepVisible.value = true
  }

  const generateAiStepSuggestion = async () => {
    if (!currentProjectId.value) {
      Message.warning('请先选择项目')
      return
    }

    const step = selectedSceneStep.value
    if (!step || selectedCustomParentSummary.value) {
      Message.warning('请先选择一个可编辑的步骤')
      return
    }

    if (!aiStepForm.prompt.trim()) {
      Message.warning('请输入步骤补全说明')
      return
    }

    aiStepSuggesting.value = true
    try {
      const promptText = aiStepForm.prompt.trim()
      const currentVariables = readCurrentVariables()
      const llmConfig = await buildLlmConfigSnapshot()
      const suggestion = await AppAutomationService.suggestStep({
        project_id: currentProjectId.value,
        prompt: promptText,
        package_id: draft.package_id ?? null,
        current_case_name: draft.name.trim(),
        current_description: draft.description.trim(),
        current_step: sanitizeStep(step),
        current_steps: steps.value.map(item => sanitizeStep(item)),
        current_variables: currentVariables,
        llm_config: llmConfig,
      })

      applyStepSuggestion(suggestion)
      aiStepVisible.value = false
      rememberAiActivity({
        action: 'step',
        status: 'success',
        mode: suggestion.mode,
        summary: suggestion.summary || '当前步骤已补全',
        prompt: promptText,
        target_name: step.name || resolveStepTitle(step),
        warnings: suggestion.warnings || [],
        provider: suggestion.provider || llmConfig?.provider || '',
        model: suggestion.model || llmConfig?.name || '',
      })

      if (suggestion.mode === 'fallback') {
        Message.warning(suggestion.warnings?.[0] || 'AI 模型不可用，已回退到规则补全。')
      } else {
        Message.success(suggestion.summary || '当前步骤已补全')
        if (suggestion.warnings?.length) {
          Message.warning(suggestion.warnings[0])
        }
      }
    } catch (error: any) {
      rememberAiActivity({
        action: 'step',
        status: 'error',
        mode: 'fallback',
        summary: normalizeErrorMessage(error, 'AI 步骤补全失败'),
        prompt: aiStepForm.prompt.trim(),
        target_name: step.name || resolveStepTitle(step),
        warnings: [],
        provider: activeLlmSnapshot.value?.provider || '',
        model: activeLlmSnapshot.value?.name || '',
      })
      Message.error(error.message || 'AI 步骤补全失败')
    } finally {
      aiStepSuggesting.value = false
    }
  }

  const openAiPlanDialog = () => {
    const promptParts = [draft.name.trim(), draft.description.trim()].filter(Boolean)
    aiPlanForm.prompt = aiPlanForm.prompt.trim() || promptParts.join('，')
    aiPlanForm.applyMode = steps.value.length ? 'append' : 'replace'
    aiPlanVisible.value = true
  }

  const generateAiPlan = async () => {
    if (!currentProjectId.value) {
      Message.warning('请先选择项目')
      return
    }

    if (!aiPlanForm.prompt.trim()) {
      Message.warning('请输入场景描述')
      return
    }

    aiGenerating.value = true
    try {
      const promptText = aiPlanForm.prompt.trim()
      const currentVariables = readCurrentVariables()
      const llmConfig = await buildLlmConfigSnapshot()
      const plan = await AppAutomationService.generateScenePlan({
        project_id: currentProjectId.value,
        prompt: promptText,
        package_id: draft.package_id ?? null,
        current_case_name: draft.name.trim(),
        current_description: draft.description.trim(),
        current_steps: steps.value.map(item => sanitizeStep(item)),
        current_variables: currentVariables,
        llm_config: llmConfig,
      })

      applyGeneratedScenePlan(plan, aiPlanForm.applyMode)
      aiPlanVisible.value = false
      rememberAiActivity({
        action: 'scene',
        status: 'success',
        mode: plan.mode,
        summary: plan.summary || 'AI 场景已生成',
        prompt: promptText,
        target_name: draft.name.trim() || plan.name || '当前场景草稿',
        warnings: plan.warnings || [],
        provider: plan.provider || llmConfig?.provider || '',
        model: plan.model || llmConfig?.name || '',
      })

      if (plan.mode === 'fallback') {
        Message.warning(plan.warnings?.[0] || 'AI 模型不可用，已回退到规则规划。')
      } else {
        Message.success(plan.summary || 'AI 场景已生成')
        if (plan.warnings?.length) {
          Message.warning(plan.warnings[0])
        }
      }
    } catch (error: any) {
      rememberAiActivity({
        action: 'scene',
        status: 'error',
        mode: 'fallback',
        summary: normalizeErrorMessage(error, 'AI 场景生成失败'),
        prompt: aiPlanForm.prompt.trim(),
        target_name: draft.name.trim() || '当前场景草稿',
        warnings: [],
        provider: activeLlmSnapshot.value?.provider || '',
        model: activeLlmSnapshot.value?.name || '',
      })
      Message.error(error.message || 'AI 场景生成失败')
    } finally {
      aiGenerating.value = false
    }
  }

  watch(
    () => aiPlanVisible.value,
    value => {
      if (!value && !aiGenerating.value) {
        resetAiPlanState()
      }
    },
  )

  watch(
    () => aiStepVisible.value,
    value => {
      if (!value && !aiStepSuggesting.value) {
        resetAiStepState()
      }
    },
  )

  return {
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
  }
}
