import { Message } from '@arco-design/web-vue'
import { computed, reactive, ref } from 'vue'
import type { Router } from 'vue-router'
import { getActiveLlmConfig, getLlmConfigDetails } from '@/features/langgraph/services/llmConfigService'
import type { AppLlmConfigSnapshot } from '../../types'
import type { SceneBuilderErrorNormalizer } from './sceneBuilderComposableModels'

export interface AiRuntimeStatus {
  has_config: boolean
  ready: boolean
  config_name: string
  provider: string
  model: string
  api_url: string
  supports_vision: boolean
  checked_at: string
  error: string
}

export interface AiActivityRecord {
  action: 'scene' | 'step'
  status: 'success' | 'error'
  mode: 'llm' | 'fallback'
  summary: string
  prompt: string
  target_name: string
  warnings: string[]
  provider: string
  model: string
  executed_at: string
}

interface UseSceneBuilderAiRuntimeOptions {
  router: Router
  normalizeErrorMessage: SceneBuilderErrorNormalizer
}

export const createAiStatusState = (): AiRuntimeStatus => ({
  has_config: false,
  ready: false,
  config_name: '',
  provider: '',
  model: '',
  api_url: '',
  supports_vision: false,
  checked_at: '',
  error: '',
})

export const formatProviderLabel = (value?: string | null) => {
  const normalized = String(value || '').trim()
  if (!normalized) return '-'

  const providerMap: Record<string, string> = {
    openai: 'OpenAI',
    openai_compatible: 'OpenAI Compatible',
    anthropic: 'Anthropic',
    google: 'Google',
    gemini: 'Google Gemini',
    deepseek: 'DeepSeek',
    siliconflow: 'SiliconFlow',
    qwen: '通义千问',
    alibaba: '阿里云百炼',
  }

  return (
    providerMap[normalized.toLowerCase()] ||
    normalized
      .replace(/[_-]+/g, ' ')
      .replace(/\b\w/g, segment => segment.toUpperCase())
  )
}

export const formatEndpointDisplay = (value?: string | null) => {
  const text = String(value || '').trim()
  if (!text) return '未配置接口地址'

  try {
    const parsed = new URL(text)
    return `${parsed.origin}${parsed.pathname.replace(/\/$/, '') || '/'}`
  } catch {
    return text
  }
}

export const getAiActionLabel = (action: AiActivityRecord['action']) => (action === 'scene' ? '场景规划' : '步骤补全')

export const getAiActivityColor = (record: AiActivityRecord) => {
  if (record.status === 'error') return 'red'
  if (record.mode === 'fallback') return 'orange'
  return 'green'
}

export const getAiActivityStatusLabel = (record: AiActivityRecord) => {
  if (record.status === 'error') return '执行失败'
  if (record.mode === 'fallback') return '规则回退'
  return 'LLM 已生效'
}

export const useSceneBuilderAiRuntime = ({
  router,
  normalizeErrorMessage,
}: UseSceneBuilderAiRuntimeOptions) => {
  const aiStatusLoading = ref(false)
  const activeLlmSnapshot = ref<AppLlmConfigSnapshot | null>(null)
  const lastAiActivity = ref<AiActivityRecord | null>(null)
  const aiStatus = reactive<AiRuntimeStatus>(createAiStatusState())

  const resetAiStatus = () => {
    Object.assign(aiStatus, createAiStatusState())
  }

  const aiStatusColor = computed(() => {
    if (aiStatus.ready) return 'green'
    if (aiStatus.has_config) return 'orange'
    return 'gray'
  })

  const aiStatusLabel = computed(() => {
    if (aiStatus.ready) return 'AI 已就绪'
    if (aiStatus.has_config) return '规则回退待排查'
    return '未配置模型'
  })

  const aiCapabilityLabel = computed(() => {
    if (!aiStatus.has_config) return '规则规划兜底'
    return aiStatus.supports_vision ? '视觉 + 文本智能规划' : '文本智能规划'
  })

  const aiConfigDisplayName = computed(() => aiStatus.config_name || '未激活 LLM 配置')
  const aiProviderDisplayName = computed(() => formatProviderLabel(aiStatus.provider))
  const aiModelDisplayName = computed(() => aiStatus.model || '未配置模型名称')
  const aiEndpointDisplay = computed(() => formatEndpointDisplay(aiStatus.api_url))

  const aiStatusTitle = computed(() => {
    if (aiStatus.ready) {
      return `${aiConfigDisplayName.value} 已接入 APP 智能编排`
    }
    if (aiStatus.has_config) {
      return '已检测到模型配置，但当前会优先回退到规则规划'
    }
    return '当前未启用 LLM，系统会自动使用规则规划'
  })

  const aiStatusDescription = computed(() => {
    if (aiStatus.ready) {
      return 'AI 场景生成和步骤补全会优先走激活模型，失败时再自动回退到规则规划，保证编排不中断。'
    }
    if (aiStatus.error) {
      return aiStatus.error
    }
    if (aiStatus.has_config) {
      return '已存在激活配置，但模型名称或接口地址不完整，当前生成链路仍可继续使用规则规划。'
    }
    return '建议先配置并激活一个 LLM 模型，这样场景规划、步骤补全和变量生成会更稳定高效。'
  })

  const aiDialogEngineName = computed(() => {
    if (!aiStatus.has_config) return '未配置 LLM，将回退到规则规划'
    return `${aiModelDisplayName.value} · ${aiProviderDisplayName.value}`
  })

  const aiDialogModeText = computed(() => {
    if (!aiStatus.has_config) return '规则规划兜底'
    return aiStatus.supports_vision ? '视觉 + 文本联合规划' : '文本规划'
  })

  const rememberAiActivity = (payload: Omit<AiActivityRecord, 'executed_at'>) => {
    lastAiActivity.value = {
      ...payload,
      warnings: [...payload.warnings],
      executed_at: new Date().toISOString(),
    }
  }

  const refreshAiRuntimeStatus = async (showMessage = false): Promise<AppLlmConfigSnapshot | null> => {
    aiStatusLoading.value = true
    try {
      const activeResponse = await getActiveLlmConfig()
      const activeConfig = activeResponse.data
      if (!activeConfig?.id) {
        activeLlmSnapshot.value = null
        resetAiStatus()
        aiStatus.checked_at = new Date().toISOString()
        if (showMessage) {
          Message.info('当前没有激活的 LLM 配置，APP AI 会回退到规则规划。')
        }
        return null
      }

      const detailResponse = await getLlmConfigDetails(activeConfig.id)
      const detail = detailResponse.data || activeConfig
      const snapshot: AppLlmConfigSnapshot | null =
        detail?.name && detail?.api_url
          ? {
              config_name: detail.config_name,
              provider: detail.provider,
              name: detail.name,
              api_url: detail.api_url,
              api_key: detail.api_key,
              system_prompt: detail.system_prompt,
              supports_vision: detail.supports_vision,
            }
          : null

      Object.assign(aiStatus, {
        has_config: true,
        ready: Boolean(snapshot),
        config_name: detail?.config_name || '',
        provider: detail?.provider || '',
        model: detail?.name || '',
        api_url: detail?.api_url || '',
        supports_vision: Boolean(detail?.supports_vision),
        checked_at: new Date().toISOString(),
        error: snapshot ? '' : '激活的 LLM 配置缺少模型名称或接口地址，当前会回退到规则规划。',
      })

      activeLlmSnapshot.value = snapshot

      if (!snapshot) {
        if (showMessage) {
          Message.warning(aiStatus.error || 'AI 状态已刷新')
        }
        return null
      }

      if (showMessage) {
        Message.success('AI 模型状态已刷新')
      }

      return snapshot
    } catch (error: any) {
      activeLlmSnapshot.value = null
      resetAiStatus()
      aiStatus.checked_at = new Date().toISOString()
      aiStatus.error = normalizeErrorMessage(error, '加载激活 LLM 配置失败，当前会回退到规则规划。')
      if (showMessage) {
        Message.error(aiStatus.error)
      }
      return null
    } finally {
      aiStatusLoading.value = false
    }
  }

  const buildLlmConfigSnapshot = async (): Promise<AppLlmConfigSnapshot | null> => {
    if (activeLlmSnapshot.value?.name && activeLlmSnapshot.value?.api_url) {
      return activeLlmSnapshot.value
    }
    return refreshAiRuntimeStatus()
  }

  const openLlmConfigManagement = async () => {
    await router.push({ name: 'LlmConfigManagement' })
  }

  return {
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
  }
}
