import type { AppSceneStep } from '../../types'

export type StepChildGroupKey = 'steps' | 'else_steps' | 'catch_steps' | 'finally_steps'

export interface SceneVariableDraft {
  name: string
  scope: string
  type: string
  valueText: string
  description: string
}

export interface StepChildGroup {
  key: StepChildGroupKey
  label: string
}

export interface SceneDraftOptions {
  resolveComponentName?: (componentType: string) => string | undefined
}

const FLOW_CONTAINER_TYPES = new Set(['sequence', 'if', 'loop', 'try'])

const STEP_META_KEYS = new Set([
  'id',
  'name',
  'kind',
  'type',
  'action',
  'component_type',
  'component_name',
  'steps',
  'then_steps',
  'try_steps',
  'else_steps',
  'catch_steps',
  'finally_steps',
  '_expanded',
])

const FLOW_CHILD_GROUPS: Record<string, StepChildGroup[]> = {
  sequence: [{ key: 'steps', label: '子步骤' }],
  if: [
    { key: 'steps', label: 'Then 分支' },
    { key: 'else_steps', label: 'Else 分支' },
  ],
  loop: [{ key: 'steps', label: '循环体' }],
  try: [
    { key: 'steps', label: 'Try 分支' },
    { key: 'catch_steps', label: 'Catch 分支' },
    { key: 'finally_steps', label: 'Finally 分支' },
  ],
}

let stepSeed = 0

const getResolveComponentName = (options?: SceneDraftOptions) => options?.resolveComponentName || (() => undefined)

export const clone = <T>(value: T): T => (value === undefined ? value : JSON.parse(JSON.stringify(value)))

export const clearRecord = (record: Record<string, unknown>) => {
  Object.keys(record).forEach(key => {
    delete record[key]
  })
}

export const isObjectValue = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const generateStepId = () => `scene-step-${Date.now()}-${stepSeed++}`

export const toComponentType = (value: string) => {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')

  return normalized || `component_${Date.now()}`
}

export const inferVariableType = (value: unknown) => {
  if (Array.isArray(value)) return 'array'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (isObjectValue(value)) return 'object'
  return 'string'
}

export const formatVariableValue = (value: unknown, type: string) => {
  if (type === 'object' || type === 'array') {
    return JSON.stringify(value ?? (type === 'array' ? [] : {}), null, 2)
  }
  if (value === null || value === undefined) {
    return ''
  }
  return String(value)
}

export const getNodeKey = (step: AppSceneStep) => String(step.id ?? '')

export const getStepType = (step?: Partial<AppSceneStep> | null) =>
  String(step?.component_type || step?.type || step?.action || '')
    .trim()
    .toLowerCase()

export const isFlowContainerType = (value?: string | null) => FLOW_CONTAINER_TYPES.has(String(value || '').trim().toLowerCase())

export const isCustomStep = (step?: Partial<AppSceneStep> | null) => Boolean(step && step.kind === 'custom')

export const isFlowContainerStep = (step?: Partial<AppSceneStep> | null) => Boolean(step && isFlowContainerType(getStepType(step)))

export const isContainerStep = (step?: Partial<AppSceneStep> | null) => Boolean(step && (isCustomStep(step) || isFlowContainerStep(step)))

const findStepList = (source: Record<string, unknown>, keys: readonly string[]) => {
  for (const key of keys) {
    const value = source[key]
    if (Array.isArray(value)) {
      return {
        found: true,
        steps: value as AppSceneStep[],
      }
    }
  }

  return {
    found: false,
    steps: [] as AppSceneStep[],
  }
}

const pickStepList = (primary: Record<string, unknown>, fallback: Record<string, unknown>, keys: readonly string[]) => {
  const direct = findStepList(primary, keys)
  if (direct.found) {
    return direct.steps
  }
  return findStepList(fallback, keys).steps
}

export const stripNestedStepKeys = (record: Record<string, unknown>) => {
  const next = clone(record)
  ;['steps', 'then_steps', 'try_steps', 'else_steps', 'catch_steps', 'finally_steps'].forEach(key => {
    delete next[key]
  })
  return next
}

export const getStepChildGroups = (step?: Partial<AppSceneStep> | null): StepChildGroup[] => {
  if (!step) {
    return []
  }
  if (isCustomStep(step)) {
    return [{ key: 'steps', label: '子步骤' }]
  }
  return FLOW_CHILD_GROUPS[getStepType(step)] || []
}

export const getStepGroupSteps = (step: AppSceneStep, groupKey: StepChildGroupKey) => {
  const value = step[groupKey]
  return Array.isArray(value) ? (value as AppSceneStep[]) : []
}

export const getSubStepSelectionKey = (step: AppSceneStep, groupKey: StepChildGroupKey) => `${getNodeKey(step)}::${groupKey}`

export const countChildSteps = (step?: Partial<AppSceneStep> | null) => {
  if (!step || !isContainerStep(step)) {
    return 0
  }

  return getStepChildGroups(step).reduce((total, group) => {
    const value = step[group.key]
    return total + (Array.isArray(value) ? value.length : 0)
  }, 0)
}

export const resolveStepTitle = (step?: Partial<AppSceneStep>, options?: SceneDraftOptions) => {
  const componentType = getStepType(step)
  const componentName = getResolveComponentName(options)(componentType)
  return step?.name || componentName || componentType || '未命名步骤'
}

export const resolveStepMeta = (step?: Partial<AppSceneStep> | null, options?: SceneDraftOptions) => {
  const componentType = getStepType(step)
  if (isContainerStep(step)) {
    const branchCount = getStepChildGroups(step).length
    const branchLabel = branchCount > 1 ? ` · ${branchCount} 个分支` : ''
    return `${componentType || (isCustomStep(step) ? 'custom' : 'flow')} · ${countChildSteps(step)} 个子步骤${branchLabel}`
  }
  return componentType || 'base'
}

export const normalizeStep = (
  input: Partial<AppSceneStep>,
  forcedKind?: 'base' | 'custom',
  options?: SceneDraftOptions,
): AppSceneStep => {
  const raw = clone(input || {})
  const rawRecord = raw as Record<string, unknown>
  const type = getStepType(raw)
  const rawConfig = isObjectValue(raw.config) ? clone(raw.config) : {}
  const primaryKeys = type === 'if' ? ['then_steps', 'steps'] : type === 'try' ? ['try_steps', 'steps'] : ['steps']
  const derivedConfig =
    isObjectValue(raw.config)
      ? stripNestedStepKeys(rawConfig)
      : stripNestedStepKeys(
          Object.entries(raw).reduce<Record<string, unknown>>((accumulator, [key, value]) => {
            if (!STEP_META_KEYS.has(key)) {
              accumulator[key] = value
            }
            return accumulator
          }, {}),
        )

  const kind = forcedKind ?? (raw.kind === 'custom' ? 'custom' : 'base')
  const step: AppSceneStep = {
    ...raw,
    id: raw.id ?? generateStepId(),
    name: String(raw.name || resolveStepTitle(raw, options)),
    kind,
    type: type || undefined,
    action: type || undefined,
    component_type: type || undefined,
    config: clone(derivedConfig),
    _expanded: Boolean(raw._expanded),
  }

  if (kind === 'custom' || isFlowContainerType(type)) {
    step.steps = normalizeSteps(pickStepList(rawRecord, rawConfig, primaryKeys), forcedKind, options)
  }

  if (type === 'if') {
    step.else_steps = normalizeSteps(pickStepList(rawRecord, rawConfig, ['else_steps']), forcedKind, options)
  }

  if (type === 'try') {
    step.catch_steps = normalizeSteps(pickStepList(rawRecord, rawConfig, ['catch_steps']), forcedKind, options)
    step.finally_steps = normalizeSteps(pickStepList(rawRecord, rawConfig, ['finally_steps']), forcedKind, options)
  }

  return step
}

export const normalizeSteps = (items: unknown, forcedKind?: 'base' | 'custom', options?: SceneDraftOptions) => {
  if (!Array.isArray(items)) {
    return []
  }
  return items.map(item => normalizeStep(item as AppSceneStep, forcedKind, options))
}

export const sanitizeStep = (step: AppSceneStep, options?: SceneDraftOptions): AppSceneStep => {
  const componentType = getStepType(step)
  const payload: AppSceneStep = {
    name: step.name?.trim() || resolveStepTitle(step, options),
    kind: isCustomStep(step) ? 'custom' : 'base',
    type: componentType || undefined,
    action: componentType || undefined,
    component_type: componentType || undefined,
    config: clone(step.config || {}),
  }

  if (isCustomStep(step) || isFlowContainerStep(step)) {
    payload.steps = getStepGroupSteps(step, 'steps').map(item => sanitizeStep(item, options))
  }

  if (getStepType(step) === 'if') {
    payload.else_steps = getStepGroupSteps(step, 'else_steps').map(item => sanitizeStep(item, options))
  }

  if (getStepType(step) === 'try') {
    payload.catch_steps = getStepGroupSteps(step, 'catch_steps').map(item => sanitizeStep(item, options))
    payload.finally_steps = getStepGroupSteps(step, 'finally_steps').map(item => sanitizeStep(item, options))
  }

  return payload
}

export const containsCustomStep = (step: AppSceneStep): boolean => {
  if (isCustomStep(step)) {
    return true
  }

  return getStepChildGroups(step).some(group => getStepGroupSteps(step, group.key).some(item => containsCustomStep(item)))
}

export const buildStepEditorPayload = (step?: AppSceneStep | null, options?: SceneDraftOptions) => {
  if (!step) {
    return {}
  }

  const payload = clone(step.config || {})
  if (isFlowContainerStep(step)) {
    getStepChildGroups(step).forEach(group => {
      payload[group.key] = getStepGroupSteps(step, group.key).map(item => sanitizeStep(item, options))
    })
  }
  return payload
}

const setNormalizedGroupSteps = (step: AppSceneStep, groupKey: StepChildGroupKey, items: unknown, options?: SceneDraftOptions) => {
  step[groupKey] = normalizeSteps(items, undefined, options)
}

export const applyStepEditorPayload = (step: AppSceneStep, payload: Record<string, unknown>, options?: SceneDraftOptions) => {
  const next = clone(payload)

  if (isFlowContainerStep(step)) {
    getStepChildGroups(step).forEach(group => {
      if (Object.prototype.hasOwnProperty.call(next, group.key)) {
        setNormalizedGroupSteps(step, group.key, Array.isArray(next[group.key]) ? next[group.key] : [], options)
      }
      delete next[group.key]
    })
  }

  step.config = stripNestedStepKeys(next)
}

export const normalizeVariables = (items: unknown): SceneVariableDraft[] => {
  if (!Array.isArray(items)) {
    return []
  }

  return items.map(item => {
    const record = isObjectValue(item) ? item : {}
    const value = record.value
    const type = String(record.type || inferVariableType(value))

    return {
      name: String(record.name || ''),
      scope: String(record.scope || 'local'),
      type,
      valueText: formatVariableValue(value, type),
      description: String(record.description || ''),
    }
  })
}

export const buildVariablePayload = (variableItems: SceneVariableDraft[]) => {
  return variableItems
    .map(item => ({
      name: item.name.trim(),
      scope: item.scope,
      type: item.type,
      valueText: item.valueText,
      description: item.description.trim(),
    }))
    .filter(item => item.name || item.valueText || item.description)
    .map(item => {
      let parsedValue: unknown = item.valueText

      if (item.type === 'number') {
        parsedValue = item.valueText === '' ? 0 : Number(item.valueText)
        if (Number.isNaN(parsedValue)) {
          throw new Error(`变量 ${item.name || '(未命名)'} 的值不是有效数字`)
        }
      } else if (item.type === 'boolean') {
        const normalized = item.valueText.trim().toLowerCase()
        parsedValue = ['true', '1', 'yes'].includes(normalized)
      } else if (item.type === 'array') {
        parsedValue = JSON.parse(item.valueText || '[]')
        if (!Array.isArray(parsedValue)) {
          throw new Error(`变量 ${item.name || '(未命名)'} 必须是数组 JSON`)
        }
      } else if (item.type === 'object') {
        parsedValue = JSON.parse(item.valueText || '{}')
        if (!isObjectValue(parsedValue)) {
          throw new Error(`变量 ${item.name || '(未命名)'} 必须是对象 JSON`)
        }
      }

      return {
        name: item.name,
        scope: item.scope,
        type: item.type,
        value: parsedValue,
        description: item.description,
      }
    })
}

export const mergeVariableDrafts = (currentItems: SceneVariableDraft[], incomingItems: SceneVariableDraft[]) => {
  const merged = new Map<string, SceneVariableDraft>()

  currentItems.forEach(item => {
    const key = item.name.trim().toLowerCase() || `current-${merged.size}`
    merged.set(key, item)
  })

  incomingItems.forEach(item => {
    const key = item.name.trim().toLowerCase() || `incoming-${merged.size}`
    merged.set(key, item)
  })

  return Array.from(merged.values())
}
