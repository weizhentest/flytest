import { computed, ref } from 'vue'

import type {
  ApiEnvironmentForm,
  ApiEnvironmentSuggestions,
  ApiImportResult,
  ApiRequest,
  ApiRequestForm,
} from '../types'

export type ApiRequestDraft = {
  label: string
  form: ApiRequestForm
}

const requestDrafts = ref<ApiRequestDraft[]>([])
const environmentDraft = ref<ApiEnvironmentForm | null>(null)
const environmentSuggestions = ref<ApiEnvironmentSuggestions | null>(null)
const draftSummary = ref('')

const PLACEHOLDER_PATTERN = /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value))

const getRequestLabel = (request: ApiRequest) => `${request.method} · ${request.name}`

const tryParseUrl = (value: string) => {
  try {
    return new URL(value)
  } catch {
    return null
  }
}

const getCommonBaseUrl = (requests: ApiRequest[]) => {
  const urls = requests.map(item => tryParseUrl(item.url)).filter((item): item is URL => !!item)
  if (!urls.length || urls.length !== requests.length) return ''
  const origin = urls[0].origin
  if (!urls.every(item => item.origin === origin)) return ''
  return origin
}

const normalizeRequestUrl = (value: string, baseUrl: string) => {
  if (!baseUrl) return value
  if (!value.startsWith(baseUrl)) return value
  const normalized = value.slice(baseUrl.length)
  return normalized.startsWith('/') ? normalized : `/${normalized}`
}

const getCommonHeaders = (requests: ApiRequest[]) => {
  if (!requests.length) return {}
  const [first, ...rest] = requests
  const common: Record<string, any> = {}
  for (const [key, value] of Object.entries(first.headers || {})) {
    if (rest.every(item => (item.headers || {})[key] === value)) {
      common[key] = value
    }
  }
  return common
}

const collectPlaceholders = (value: unknown, found: Set<string>) => {
  if (typeof value === 'string') {
    for (const match of value.matchAll(PLACEHOLDER_PATTERN)) {
      found.add(match[1])
    }
    return
  }
  if (Array.isArray(value)) {
    value.forEach(item => collectPlaceholders(item, found))
    return
  }
  if (value && typeof value === 'object') {
    Object.values(value as Record<string, unknown>).forEach(item => collectPlaceholders(item, found))
  }
}

const buildVariables = (requests: ApiRequest[]) => {
  const placeholders = new Set<string>()
  requests.forEach(item => {
    collectPlaceholders(item.url, placeholders)
    collectPlaceholders(item.headers, placeholders)
    collectPlaceholders(item.params, placeholders)
    collectPlaceholders(item.body, placeholders)
  })

  const variables: Record<string, string> = {}
  placeholders.forEach(key => {
    if (key === 'base_url') return
    variables[key] = ''
  })
  return variables
}

const buildRequestDrafts = (requests: ApiRequest[], collectionId: number, baseUrl: string) => {
  return requests.map<ApiRequestDraft>(item => ({
    label: getRequestLabel(item),
    form: {
      collection: collectionId,
      name: item.name,
      description: item.description || '',
      method: item.method,
      url: normalizeRequestUrl(item.url, baseUrl),
      headers: clone(item.headers || {}),
      params: clone(item.params || {}),
      body_type: item.body_type,
      body: clone(item.body),
      assertions: clone(item.assertions || []),
      timeout_ms: item.timeout_ms || 30000,
      order: item.order || 0,
    },
  }))
}

const buildFallbackEnvironmentDraft = (requests: ApiRequest[], projectId: number, baseUrl: string): ApiEnvironmentForm => {
  const commonHeaders = getCommonHeaders(requests)
  const variables = buildVariables(requests)
  return {
    project: projectId,
    name: '文档解析环境草稿',
    base_url: baseUrl,
    common_headers: commonHeaders,
    variables,
    environment_specs: {
      headers: Object.entries(commonHeaders).map(([name, value], index) => ({
        name,
        value,
        enabled: true,
        order: index,
      })),
      variables: Object.entries(variables).map(([name, value], index) => ({
        name,
        value,
        enabled: true,
        is_secret: false,
        order: index,
      })),
      cookies: [],
    },
    timeout_ms: Math.max(...requests.map(item => item.timeout_ms || 30000), 30000),
    is_default: false,
  }
}

export const useApiImportDrafts = () => {
  const hasRequestDrafts = computed(() => requestDrafts.value.length > 0)
  const hasEnvironmentDraft = computed(() => !!environmentDraft.value)
  const hasEnvironmentSuggestions = computed(() => !!environmentSuggestions.value)

  const clearDrafts = () => {
    requestDrafts.value = []
    environmentDraft.value = null
    environmentSuggestions.value = null
    draftSummary.value = ''
  }

  const saveDraftsFromImport = (result: ApiImportResult, projectId: number, collectionId: number) => {
    const requests = result.items || []
    if (!requests.length) {
      clearDrafts()
      return
    }

    const baseUrl = getCommonBaseUrl(requests)
    requestDrafts.value = buildRequestDrafts(requests, collectionId, baseUrl)

    const backendEnvironmentDraft = result.environment_draft
    environmentDraft.value = backendEnvironmentDraft
      ? {
          project: projectId,
          name: backendEnvironmentDraft.name || '文档解析环境草稿',
          base_url: backendEnvironmentDraft.base_url || '',
          common_headers: backendEnvironmentDraft.common_headers || {},
          variables: backendEnvironmentDraft.variables || {},
          environment_specs: backendEnvironmentDraft.environment_specs || undefined,
          timeout_ms: backendEnvironmentDraft.timeout_ms || 30000,
          is_default: backendEnvironmentDraft.is_default || false,
        }
      : buildFallbackEnvironmentDraft(requests, projectId, baseUrl)

    environmentSuggestions.value = result.environment_suggestions || null
    draftSummary.value = `已从最近一次文档解析中生成 ${requests.length} 个接口草稿`
  }

  const getRequestDraft = (index = 0) => {
    const draft = requestDrafts.value[index]
    return draft ? clone(draft) : null
  }

  const getEnvironmentDraft = () => {
    return environmentDraft.value ? clone(environmentDraft.value) : null
  }

  const getEnvironmentSuggestions = () => {
    return environmentSuggestions.value ? clone(environmentSuggestions.value) : null
  }

  return {
    requestDrafts,
    environmentDraft,
    environmentSuggestions,
    draftSummary,
    hasRequestDrafts,
    hasEnvironmentDraft,
    hasEnvironmentSuggestions,
    saveDraftsFromImport,
    getRequestDraft,
    getEnvironmentDraft,
    getEnvironmentSuggestions,
    clearDrafts,
  }
}
