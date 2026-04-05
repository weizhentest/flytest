<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再进行 APP 场景编排" />
    </div>
    <template v-else>
      <div class="page-header">
        <div>
          <h3>场景编排</h3>
          <p>补齐 APP 自动化场景编排能力，支持拖拽步骤、自定义组件与子步骤维护。</p>
        </div>
        <a-space>
          <a-button @click="loadData" :loading="loading">刷新</a-button>
          <a-button @click="resetDraft">新建草稿</a-button>
          <a-button :disabled="!steps.length" @click="openCreateCustomComponent">另存为自定义组件</a-button>
          <a-button type="primary" :loading="saving" @click="saveDraft">保存用例</a-button>
        </a-space>
      </div>

      <a-card class="form-card">
        <a-form :model="draft" layout="vertical">
          <a-row :gutter="12">
            <a-col :span="8">
              <a-form-item field="caseId" label="加载已有用例">
                <a-select
                  v-model="selectedCaseId"
                  allow-clear
                  placeholder="选择已有用例"
                  @change="handleCaseChange"
                >
                  <a-option v-for="item in testCases" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </a-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item field="name" label="用例名称">
                <a-input v-model="draft.name" placeholder="例如：登录并进入首页" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item field="package_id" label="应用包">
                <a-select v-model="draft.package_id" allow-clear placeholder="可选">
                  <a-option v-for="item in packages" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </a-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item field="description" label="描述">
                <a-textarea
                  v-model="draft.description"
                  :auto-size="{ minRows: 3, maxRows: 5 }"
                  placeholder="补充该场景的业务说明或前置条件"
                />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item field="timeout" label="超时时间（秒）">
                <a-input-number v-model="draft.timeout" :min="1" :max="7200" />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item field="retry_count" label="失败重试">
                <a-input-number v-model="draft.retry_count" :min="0" :max="10" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item label="场景变量">
            <div class="variable-list">
              <div v-if="variableItems.length" class="variable-items">
                <div v-for="(item, index) in variableItems" :key="`variable-${index}`" class="variable-row">
                  <a-input v-model="item.name" placeholder="变量名" />
                  <a-select v-model="item.scope" placeholder="作用域">
                    <a-option value="local">local</a-option>
                    <a-option value="global">global</a-option>
                  </a-select>
                  <a-select v-model="item.type" placeholder="类型">
                    <a-option value="string">string</a-option>
                    <a-option value="number">number</a-option>
                    <a-option value="boolean">boolean</a-option>
                    <a-option value="array">array</a-option>
                    <a-option value="object">object</a-option>
                  </a-select>
                  <a-input v-model="item.valueText" placeholder="默认值" />
                  <a-input v-model="item.description" placeholder="说明" />
                  <a-button status="danger" @click="removeVariable(index)">删除</a-button>
                </div>
              </div>
              <a-empty v-else description="暂未配置场景变量" />
            </div>
            <div class="variable-actions">
              <a-button type="outline" size="small" @click="addVariable">添加变量</a-button>
            </div>
          </a-form-item>
        </a-form>
      </a-card>

      <div class="builder-grid">
        <a-card class="panel-card library-panel">
          <template #title>步骤组件库</template>
          <a-input-search
            v-model="componentSearch"
            class="component-search"
            allow-clear
            placeholder="搜索组件名称或类型"
          />
          <a-tabs v-model:active-key="paletteTab" lazy-load>
            <a-tab-pane key="base" title="基础组件">
              <div v-if="filteredComponents.length" class="component-grid">
                <div
                  v-for="item in filteredComponents"
                  :key="item.id"
                  class="component-item"
                  @click="appendBaseComponent(item)"
                >
                  <div class="component-copy">
                    <span class="component-name">{{ item.name }}</span>
                    <span class="component-meta">{{ item.type }}</span>
                  </div>
                  <span class="component-tag">{{ item.category || 'base' }}</span>
                </div>
              </div>
              <a-empty v-else description="没有匹配的基础组件" />
            </a-tab-pane>

            <a-tab-pane key="custom" title="自定义组件">
              <div v-if="filteredCustomComponents.length" class="component-grid">
                <div
                  v-for="item in filteredCustomComponents"
                  :key="item.id"
                  class="component-item component-item-custom"
                  @click="appendCustomComponent(item)"
                >
                  <div class="component-copy">
                    <span class="component-name">{{ item.name }}</span>
                    <span class="component-meta">
                      {{ item.type }} · {{ item.steps?.length || 0 }} 个子步骤
                    </span>
                  </div>
                  <div class="component-actions">
                    <a-button type="text" size="mini" @click.stop="openEditCustomComponent(item)">编辑</a-button>
                    <a-button type="text" size="mini" status="danger" @click.stop="deleteCustomComponent(item)">
                      删除
                    </a-button>
                  </div>
                </div>
              </div>
              <a-empty v-else description="暂无自定义组件" />
            </a-tab-pane>
          </a-tabs>
        </a-card>

        <a-card class="panel-card canvas-panel">
          <template #title>场景步骤</template>
          <template #extra>
            <a-space>
              <span class="step-counter">共 {{ steps.length }} 步</span>
              <a-button size="mini" status="danger" :disabled="!steps.length" @click="clearSteps">清空</a-button>
            </a-space>
          </template>

          <div v-if="steps.length" class="step-list">
            <draggable
              v-model="steps"
              item-key="id"
              handle=".drag-handle"
              class="draggable-root"
              :animation="180"
            >
              <template #item="{ element, index }">
                <div class="step-item-wrapper">
                  <div
                    class="step-item"
                    :class="{ active: selectedStepIndex === index && selectedSubStepIndex === null }"
                    @click="selectStep(index)"
                  >
                    <div class="step-main">
                      <span class="drag-handle">⋮⋮</span>
                      <span class="step-index">{{ index + 1 }}</span>
                      <div class="step-copy">
                        <strong>{{ element.name || resolveStepTitle(element) }}</strong>
                        <span>{{ resolveStepMeta(element) }}</span>
                      </div>
                      <a-tag v-if="isCustomStep(element)" size="small">自定义组件</a-tag>
                    </div>
                    <a-space>
                      <a-button
                        v-if="isCustomStep(element)"
                        size="mini"
                        type="text"
                        @click.stop="toggleExpand(index)"
                      >
                        {{ element._expanded ? '收起' : '展开' }}
                      </a-button>
                      <a-button size="mini" type="text" @click.stop="duplicateStep(index)">复制</a-button>
                      <a-button size="mini" type="text" status="danger" @click.stop="removeStep(index)">删除</a-button>
                    </a-space>
                  </div>

                  <div v-if="isCustomStep(element) && element._expanded" class="sub-step-shell">
                    <div class="sub-step-toolbar">
                      <a-select
                        v-model="subStepSelections[getNodeKey(element)]"
                        allow-search
                        placeholder="选择基础组件后添加为子步骤"
                      >
                        <a-option v-for="item in components" :key="item.id" :value="item.type">
                          {{ item.name }}
                        </a-option>
                      </a-select>
                      <a-button size="mini" type="primary" @click.stop="addSubStep(index)">添加子步骤</a-button>
                    </div>

                    <draggable
                      v-model="element.steps"
                      item-key="id"
                      handle=".drag-handle"
                      class="sub-step-list"
                      :animation="160"
                    >
                      <template #item="{ element: subStep, index: subIndex }">
                        <div
                          class="sub-step-item"
                          :class="{ active: selectedStepIndex === index && selectedSubStepIndex === subIndex }"
                          @click.stop="selectSubStep(index, subIndex)"
                        >
                          <div class="step-main">
                            <span class="drag-handle">⋮⋮</span>
                            <span class="step-index sub-index">{{ index + 1 }}.{{ subIndex + 1 }}</span>
                            <div class="step-copy">
                              <strong>{{ subStep.name || resolveStepTitle(subStep) }}</strong>
                              <span>{{ resolveStepMeta(subStep) }}</span>
                            </div>
                          </div>
                          <a-space>
                            <a-button size="mini" type="text" @click.stop="duplicateSubStep(index, subIndex)">复制</a-button>
                            <a-button size="mini" type="text" status="danger" @click.stop="removeSubStep(index, subIndex)">
                              删除
                            </a-button>
                          </a-space>
                        </div>
                      </template>
                    </draggable>

                    <a-empty
                      v-if="!element.steps?.length"
                      description="当前自定义组件还没有子步骤"
                    />
                  </div>
                </div>
              </template>
            </draggable>
          </div>
          <a-empty v-else description="从左侧添加步骤，快速搭建 APP 自动化场景" />
        </a-card>

        <a-card class="panel-card config-panel">
          <template #title>步骤配置</template>
          <div v-if="!selectedSceneStep" class="config-empty">请选择一个步骤进行配置</div>

          <div
            v-else-if="selectedParentStep && isCustomStep(selectedParentStep) && selectedSubStepIndex === null"
            class="config-summary"
          >
            <a-form layout="vertical">
              <a-form-item label="组件名称">
                <a-input v-model="selectedParentStep.name" />
              </a-form-item>
              <a-form-item label="组件类型">
                <a-input :model-value="selectedParentStep.component_type || selectedParentStep.type || 'custom'" disabled />
              </a-form-item>
              <a-form-item label="子步骤数量">
                <a-input :model-value="String(selectedParentStep.steps?.length || 0)" disabled />
              </a-form-item>
            </a-form>
            <a-alert>
              当前选中的是自定义组件父步骤，请展开后编辑子步骤配置；这里可以直接修改组件在当前场景中的显示名称。
            </a-alert>
          </div>

          <div v-else class="config-form">
            <a-form layout="vertical">
              <a-form-item label="步骤名称">
                <a-input v-model="selectedSceneStep.name" placeholder="请输入步骤名称" />
              </a-form-item>
              <a-form-item label="步骤类型">
                <a-input :model-value="resolveStepMeta(selectedSceneStep)" disabled />
              </a-form-item>
              <a-form-item label="配置字段">
                <div class="config-keys">
                  <a-tag v-for="item in configKeys" :key="item" size="small">{{ item }}</a-tag>
                  <span v-if="!configKeys.length" class="config-empty-text">当前步骤还没有配置字段</span>
                </div>
              </a-form-item>
              <a-form-item label="配置 JSON">
                <a-textarea
                  v-model="stepConfigText"
                  :auto-size="{ minRows: 10, maxRows: 18 }"
                  placeholder="请输入步骤配置 JSON"
                />
              </a-form-item>
            </a-form>

            <div class="config-actions">
              <a-button @click="resetSelectedStepConfig">恢复默认配置</a-button>
              <a-button type="primary" @click="applyStepConfig">应用到当前步骤</a-button>
            </div>
          </div>
        </a-card>
      </div>

      <a-modal v-model:visible="customComponentVisible" width="760px" :footer="false">
        <template #title>
          {{ customComponentMode === 'create' ? '保存为自定义组件' : '编辑自定义组件' }}
        </template>

        <a-form :model="customComponentForm" layout="vertical">
          <a-alert class="custom-dialog-alert">
            {{
              customComponentMode === 'create'
                ? '当前会将场景中的基础步骤保存为新的自定义组件，暂不支持嵌套自定义组件。'
                : '这里可以维护组件名称、类型与步骤 JSON，保存后会同步到组件库。'
            }}
          </a-alert>

          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item field="name" label="组件名称">
                <a-input v-model="customComponentForm.name" placeholder="请输入组件名称" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item field="type" label="组件类型">
                <a-input v-model="customComponentForm.type" placeholder="例如：login_flow_component" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item field="description" label="组件描述">
            <a-textarea
              v-model="customComponentForm.description"
              :auto-size="{ minRows: 3, maxRows: 5 }"
              placeholder="说明该自定义组件的用途"
            />
          </a-form-item>

          <a-form-item field="stepsText" label="步骤 JSON">
            <a-textarea
              v-model="customComponentForm.stepsText"
              :auto-size="{ minRows: 12, maxRows: 20 }"
              placeholder="请填写组件步骤 JSON 数组"
            />
          </a-form-item>
        </a-form>

        <template #footer>
          <a-space>
            <a-button @click="customComponentVisible = false">取消</a-button>
            <a-button type="primary" :loading="customComponentSaving" @click="saveCustomComponent">
              保存组件
            </a-button>
          </a-space>
        </template>
      </a-modal>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import draggable from 'vuedraggable'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppComponent, AppCustomComponent, AppPackage, AppSceneStep, AppTestCase } from '../types'

type PaletteTab = 'base' | 'custom'
type CustomComponentDialogMode = 'create' | 'edit'

interface SceneVariableDraft {
  name: string
  scope: string
  type: string
  valueText: string
  description: string
}

const STEP_META_KEYS = new Set([
  'id',
  'name',
  'kind',
  'type',
  'action',
  'component_type',
  'component_name',
  'steps',
  '_expanded',
])

const projectStore = useProjectStore()

const loading = ref(false)
const saving = ref(false)
const customComponentSaving = ref(false)
const selectedCaseId = ref<number | undefined>()
const selectedStepIndex = ref<number | null>(null)
const selectedSubStepIndex = ref<number | null>(null)
const componentSearch = ref('')
const stepConfigText = ref('{}')
const paletteTab = ref<PaletteTab>('base')
const customComponentVisible = ref(false)
const customComponentMode = ref<CustomComponentDialogMode>('create')
const editingCustomComponentId = ref<number | null>(null)

const components = ref<AppComponent[]>([])
const customComponents = ref<AppCustomComponent[]>([])
const packages = ref<AppPackage[]>([])
const testCases = ref<AppTestCase[]>([])
const steps = ref<AppSceneStep[]>([])
const variableItems = ref<SceneVariableDraft[]>([])

const subStepSelections = reactive<Record<string, string | undefined>>({})

const draft = reactive({
  name: '',
  description: '',
  package_id: undefined as number | undefined,
  timeout: 300,
  retry_count: 0,
})

const customComponentForm = reactive({
  name: '',
  type: '',
  description: '',
  stepsText: '[]',
})

let stepSeed = 0

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value))

const clearRecord = (record: Record<string, unknown>) => {
  Object.keys(record).forEach(key => {
    delete record[key]
  })
}

const isObjectValue = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const generateStepId = () => `scene-step-${Date.now()}-${stepSeed++}`

const toComponentType = (value: string) => {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')

  return normalized || `component_${Date.now()}`
}

const inferVariableType = (value: unknown) => {
  if (Array.isArray(value)) return 'array'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (isObjectValue(value)) return 'object'
  return 'string'
}

const formatVariableValue = (value: unknown, type: string) => {
  if (type === 'object' || type === 'array') {
    return JSON.stringify(value ?? (type === 'array' ? [] : {}), null, 2)
  }
  if (value === null || value === undefined) {
    return ''
  }
  return String(value)
}

const getNodeKey = (step: AppSceneStep) => String(step.id ?? '')

const componentMap = computed(() => new Map(components.value.map(item => [item.type, item])))
const customComponentMap = computed(() => new Map(customComponents.value.map(item => [item.type, item])))
const componentNameMap = computed(() => {
  const entries = [
    ...components.value.map(item => [item.type, item.name] as const),
    ...customComponents.value.map(item => [item.type, item.name] as const),
  ]
  return new Map(entries)
})

const isCustomStep = (step?: AppSceneStep | null) => Boolean(step && (step.kind === 'custom' || Array.isArray(step.steps)))

const resolveStepTitle = (step?: Partial<AppSceneStep>) => {
  const componentType = String(step?.component_type || step?.type || step?.action || '')
  return step?.name || componentNameMap.value.get(componentType) || componentType || '未命名步骤'
}

const resolveStepMeta = (step?: Partial<AppSceneStep>) => {
  const componentType = String(step?.component_type || step?.type || step?.action || '')
  if (isCustomStep(step as AppSceneStep)) {
    return `${componentType || 'custom'} · ${(step?.steps || []).length} 个子步骤`
  }
  return componentType || 'base'
}

const normalizeStep = (input: Partial<AppSceneStep>, forcedKind?: 'base' | 'custom'): AppSceneStep => {
  const raw = clone(input || {})
  const type = String(raw.component_type || raw.type || raw.action || '').trim()
  const rawChildren = Array.isArray(raw.steps) ? raw.steps : []
  const derivedConfig =
    isObjectValue(raw.config)
      ? clone(raw.config)
      : Object.entries(raw).reduce<Record<string, unknown>>((accumulator, [key, value]) => {
          if (!STEP_META_KEYS.has(key)) {
            accumulator[key] = value
          }
          return accumulator
        }, {})

  const kind = forcedKind ?? (raw.kind === 'custom' || rawChildren.length ? 'custom' : 'base')

  return {
    ...raw,
    id: raw.id ?? generateStepId(),
    name: String(raw.name || resolveStepTitle(raw)),
    kind,
    type: type || undefined,
    action: type || undefined,
    component_type: type || undefined,
    config: clone(derivedConfig),
    steps: kind === 'custom' ? rawChildren.map(item => normalizeStep(item, 'base')) : undefined,
    _expanded: Boolean(raw._expanded),
  }
}

const normalizeSteps = (items: unknown, forcedKind?: 'base' | 'custom') => {
  if (!Array.isArray(items)) {
    return []
  }
  return items.map(item => normalizeStep(item as AppSceneStep, forcedKind))
}

const sanitizeStep = (step: AppSceneStep): AppSceneStep => {
  const componentType = String(step.component_type || step.type || step.action || '').trim()
  const payload: AppSceneStep = {
    name: step.name?.trim() || resolveStepTitle(step),
    kind: isCustomStep(step) ? 'custom' : 'base',
    type: componentType || undefined,
    action: componentType || undefined,
    component_type: componentType || undefined,
    config: clone(step.config || {}),
  }

  if (isCustomStep(step)) {
    payload.steps = (step.steps || []).map(item => sanitizeStep(item))
  }

  return payload
}

const normalizeVariables = (items: unknown): SceneVariableDraft[] => {
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

const buildVariablePayload = () => {
  return variableItems.value
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
  return parentStep.steps?.[selectedSubStepIndex.value] || null
})

const configKeys = computed(() => Object.keys(selectedSceneStep.value?.config || {}))

const syncStepEditor = () => {
  const step = selectedSceneStep.value
  if (!step || (selectedSubStepIndex.value === null && isCustomStep(step))) {
    stepConfigText.value = '{}'
    return
  }
  stepConfigText.value = JSON.stringify(step.config || {}, null, 2)
}

const buildBaseStep = (component: AppComponent) =>
  normalizeStep(
    {
      name: component.name,
      kind: 'base',
      type: component.type,
      action: component.type,
      component_type: component.type,
      config: clone(component.default_config || {}),
    },
    'base',
  )

const buildCustomStep = (component: AppCustomComponent) =>
  normalizeStep(
    {
      name: component.name,
      kind: 'custom',
      type: component.type,
      action: component.type,
      component_type: component.type,
      config: clone(component.default_config || {}),
      steps: normalizeSteps(component.steps || [], 'base'),
      _expanded: true,
    },
    'custom',
  )

const cloneSceneStep = (step: AppSceneStep) => {
  const duplicated = normalizeStep(clone(step), isCustomStep(step) ? 'custom' : 'base')
  duplicated.name = `${step.name || resolveStepTitle(step)} 副本`
  return duplicated
}

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

const resetDraft = () => {
  selectedCaseId.value = undefined
  selectedStepIndex.value = null
  selectedSubStepIndex.value = null
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
  clearRecord(subStepSelections)
  syncStepEditor()
}

const loadData = async () => {
  if (!projectStore.currentProjectId) {
    components.value = []
    customComponents.value = []
    packages.value = []
    testCases.value = []
    resetDraft()
    return
  }

  loading.value = true
  try {
    const [baseComponents, userComponents, packageList, caseList] = await Promise.all([
      AppAutomationService.getComponents(),
      AppAutomationService.getCustomComponents(),
      AppAutomationService.getPackages(projectStore.currentProjectId),
      AppAutomationService.getTestCases(projectStore.currentProjectId),
    ])

    components.value = baseComponents
    customComponents.value = userComponents
    packages.value = packageList
    testCases.value = caseList

    if (selectedCaseId.value) {
      const current = caseList.find(item => item.id === selectedCaseId.value)
      if (current) {
        applyCase(current)
      }
    }
  } catch (error: any) {
    Message.error(error.message || '加载场景编排数据失败')
  } finally {
    loading.value = false
  }
}

const handleCaseChange = (value?: number) => {
  const record = testCases.value.find(item => item.id === value)
  applyCase(record)
}

const appendBaseComponent = (component: AppComponent) => {
  steps.value.push(buildBaseStep(component))
  selectedStepIndex.value = steps.value.length - 1
  selectedSubStepIndex.value = null
}

const appendCustomComponent = (component: AppCustomComponent) => {
  steps.value.push(buildCustomStep(component))
  selectedStepIndex.value = steps.value.length - 1
  selectedSubStepIndex.value = null
  paletteTab.value = 'custom'
}

const selectStep = (index: number) => {
  selectedStepIndex.value = index
  selectedSubStepIndex.value = null
}

const selectSubStep = (parentIndex: number, subIndex: number) => {
  selectedStepIndex.value = parentIndex
  selectedSubStepIndex.value = subIndex
}

const toggleExpand = (index: number) => {
  const step = steps.value[index]
  if (!isCustomStep(step)) {
    return
  }

  step._expanded = !step._expanded
  if (!step._expanded && selectedStepIndex.value === index && selectedSubStepIndex.value !== null) {
    selectedSubStepIndex.value = null
  }
}

const duplicateStep = (index: number) => {
  const source = steps.value[index]
  if (!source) {
    return
  }

  steps.value.splice(index + 1, 0, cloneSceneStep(source))
  selectedStepIndex.value = index + 1
  selectedSubStepIndex.value = null
}

const removeStep = (index: number) => {
  steps.value.splice(index, 1)

  if (!steps.value.length) {
    selectedStepIndex.value = null
    selectedSubStepIndex.value = null
    return
  }

  if (selectedStepIndex.value === index) {
    selectedStepIndex.value = Math.min(index, steps.value.length - 1)
    selectedSubStepIndex.value = null
  } else if (selectedStepIndex.value !== null && selectedStepIndex.value > index) {
    selectedStepIndex.value -= 1
  }
}

const clearSteps = () => {
  steps.value = []
  selectedStepIndex.value = null
  selectedSubStepIndex.value = null
  clearRecord(subStepSelections)
  syncStepEditor()
}

const addSubStep = (parentIndex: number) => {
  const parentStep = steps.value[parentIndex]
  if (!isCustomStep(parentStep)) {
    return
  }

  const selectedType = subStepSelections[getNodeKey(parentStep)]
  if (!selectedType) {
    Message.warning('请先选择一个基础组件')
    return
  }

  const component = componentMap.value.get(selectedType)
  if (!component) {
    Message.warning('未找到对应的基础组件')
    return
  }

  parentStep.steps = parentStep.steps || []
  parentStep.steps.push(buildBaseStep(component))
  parentStep._expanded = true
  selectSubStep(parentIndex, parentStep.steps.length - 1)
}

const duplicateSubStep = (parentIndex: number, subIndex: number) => {
  const parentStep = steps.value[parentIndex]
  const source = parentStep?.steps?.[subIndex]
  if (!parentStep || !source || !Array.isArray(parentStep.steps)) {
    return
  }

  parentStep.steps.splice(subIndex + 1, 0, cloneSceneStep(source))
  selectSubStep(parentIndex, subIndex + 1)
}

const removeSubStep = (parentIndex: number, subIndex: number) => {
  const parentStep = steps.value[parentIndex]
  if (!parentStep || !Array.isArray(parentStep.steps)) {
    return
  }

  parentStep.steps.splice(subIndex, 1)

  if (selectedStepIndex.value === parentIndex && selectedSubStepIndex.value !== null) {
    if (!parentStep.steps.length) {
      selectedSubStepIndex.value = null
    } else if (selectedSubStepIndex.value === subIndex) {
      selectedSubStepIndex.value = Math.min(subIndex, parentStep.steps.length - 1)
    } else if (selectedSubStepIndex.value > subIndex) {
      selectedSubStepIndex.value -= 1
    }
  }
}

const applyStepConfig = () => {
  const step = selectedSceneStep.value
  if (!step || (selectedSubStepIndex.value === null && isCustomStep(step))) {
    return
  }

  try {
    const parsed = JSON.parse(stepConfigText.value || '{}')
    if (!isObjectValue(parsed)) {
      throw new Error('配置 JSON 必须是对象')
    }
    step.config = clone(parsed)
    Message.success('当前步骤配置已更新')
  } catch (error: any) {
    Message.error(error.message || '步骤配置 JSON 格式不正确')
  }
}

const resetSelectedStepConfig = () => {
  const step = selectedSceneStep.value
  if (!step || (selectedSubStepIndex.value === null && isCustomStep(step))) {
    return
  }

  const componentType = String(step.component_type || step.type || step.action || '')
  const template = componentMap.value.get(componentType)
  step.config = clone(template?.default_config || {})
  syncStepEditor()
  Message.success('已恢复默认配置')
}

const openCreateCustomComponent = () => {
  if (!steps.value.length) {
    Message.warning('请先添加场景步骤')
    return
  }

  if (steps.value.some(item => isCustomStep(item))) {
    Message.warning('自定义组件中暂不支持嵌套自定义组件')
    return
  }

  customComponentMode.value = 'create'
  editingCustomComponentId.value = null
  customComponentForm.name = ''
  customComponentForm.type = `scene_component_${customComponents.value.length + 1}`
  customComponentForm.description = ''
  customComponentForm.stepsText = JSON.stringify(steps.value.map(item => sanitizeStep(item)), null, 2)
  customComponentVisible.value = true
}

const openEditCustomComponent = (component: AppCustomComponent) => {
  customComponentMode.value = 'edit'
  editingCustomComponentId.value = component.id
  customComponentForm.name = component.name
  customComponentForm.type = component.type
  customComponentForm.description = component.description
  customComponentForm.stepsText = JSON.stringify(normalizeSteps(component.steps || [], 'base').map(item => sanitizeStep(item)), null, 2)
  customComponentVisible.value = true
}

const buildCustomComponentSteps = () => {
  let parsed: unknown

  try {
    parsed = JSON.parse(customComponentForm.stepsText || '[]')
  } catch {
    throw new Error('组件步骤 JSON 格式不正确')
  }

  if (!Array.isArray(parsed)) {
    throw new Error('组件步骤 JSON 必须是数组')
  }

  const nestedCustom = parsed.some(item => {
    const record = item as AppSceneStep
    return record?.kind === 'custom' || (Array.isArray(record?.steps) && record.steps.length > 0)
  })

  if (nestedCustom) {
    throw new Error('自定义组件中不支持嵌套自定义组件')
  }

  return normalizeSteps(parsed, 'base').map(item => sanitizeStep(item))
}

const saveCustomComponent = async () => {
  const name = customComponentForm.name.trim()
  const type = toComponentType(customComponentForm.type || customComponentForm.name)

  if (!name) {
    Message.warning('请输入组件名称')
    return
  }

  customComponentSaving.value = true
  try {
    const payload = {
      name,
      type,
      description: customComponentForm.description.trim(),
      schema: {},
      default_config: {},
      steps: buildCustomComponentSteps(),
      enabled: true,
      sort_order: customComponents.value.length + 1,
    }

    if (!payload.steps.length) {
      Message.warning('请至少保留一个组件步骤')
      return
    }

    if (customComponentMode.value === 'edit' && editingCustomComponentId.value) {
      const current = customComponents.value.find(item => item.id === editingCustomComponentId.value)
      await AppAutomationService.updateCustomComponent(editingCustomComponentId.value, {
        ...payload,
        enabled: current?.enabled ?? true,
        sort_order: current?.sort_order ?? payload.sort_order,
      })
      Message.success('自定义组件已更新')
    } else {
      await AppAutomationService.createCustomComponent(payload)
      Message.success('自定义组件已创建')
    }

    customComponentVisible.value = false
    await loadData()
    paletteTab.value = 'custom'
  } catch (error: any) {
    Message.error(error.message || '保存自定义组件失败')
  } finally {
    customComponentSaving.value = false
  }
}

const deleteCustomComponent = (component: AppCustomComponent) => {
  Modal.confirm({
    title: '删除自定义组件',
    content: `确认删除自定义组件 “${component.name}” 吗？`,
    onOk: async () => {
      await AppAutomationService.deleteCustomComponent(component.id)
      Message.success('自定义组件已删除')
      await loadData()
    },
  })
}

const saveDraft = async () => {
  if (!projectStore.currentProjectId) {
    return
  }

  if (!draft.name.trim()) {
    Message.warning('请输入用例名称')
    return
  }

  if (!steps.value.length) {
    Message.warning('请至少添加一个步骤')
    return
  }

  saving.value = true
  try {
    const payload = {
      project_id: projectStore.currentProjectId,
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
    }

    if (selectedCaseId.value) {
      await AppAutomationService.updateTestCase(selectedCaseId.value, payload)
      Message.success('测试用例已更新')
    } else {
      const created = await AppAutomationService.createTestCase(payload)
      selectedCaseId.value = created.id
      Message.success('测试用例已创建')
    }

    await loadData()
  } catch (error: any) {
    Message.error(error.message || '保存测试用例失败')
  } finally {
    saving.value = false
  }
}

watch(
  () => projectStore.currentProjectId,
  () => {
    resetDraft()
    void loadData()
  },
  { immediate: true },
)

watch([selectedStepIndex, selectedSubStepIndex], () => {
  syncStepEditor()
})
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-shell {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

.form-card,
.panel-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.variable-list {
  border: 1px dashed rgba(var(--theme-accent-rgb), 0.24);
  border-radius: 14px;
  padding: 14px;
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.variable-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.variable-row {
  display: grid;
  grid-template-columns: 1.1fr 120px 120px 1.2fr 1.1fr auto;
  gap: 10px;
  align-items: center;
}

.variable-actions {
  margin-top: 10px;
}

.builder-grid {
  display: grid;
  grid-template-columns: 1.05fr 1.2fr 0.95fr;
  gap: 16px;
  min-height: 560px;
}

.library-panel,
.canvas-panel,
.config-panel {
  min-height: 560px;
}

.component-search {
  margin-bottom: 14px;
}

.component-grid {
  display: grid;
  gap: 10px;
}

.component-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.06);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.component-item:hover {
  transform: translateY(-1px);
  border-color: rgba(var(--theme-accent-rgb), 0.34);
  background: rgba(var(--theme-accent-rgb), 0.09);
}

.component-item-custom {
  background: rgba(var(--theme-accent-rgb), 0.1);
}

.component-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.component-name {
  font-weight: 700;
  color: var(--theme-text);
}

.component-meta,
.component-tag {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.component-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.step-list,
.draggable-root,
.sub-step-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step-item-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-item,
.sub-step-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
  cursor: pointer;
}

.step-item.active,
.sub-step-item.active {
  border-color: rgba(var(--theme-accent-rgb), 0.42);
  box-shadow: 0 12px 28px rgba(var(--theme-accent-rgb), 0.12);
}

.step-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.drag-handle {
  color: var(--theme-text-secondary);
  cursor: move;
  user-select: none;
}

.step-index {
  min-width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(var(--theme-accent-rgb), 0.14);
  color: var(--theme-accent);
  font-weight: 700;
}

.sub-index {
  background: rgba(var(--theme-accent-rgb), 0.22);
}

.step-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.step-copy strong {
  color: var(--theme-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-copy span,
.step-counter {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.sub-step-shell {
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  border-radius: 14px;
  background: rgba(var(--theme-accent-rgb), 0.05);
  padding: 12px;
}

.sub-step-toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  margin-bottom: 12px;
}

.config-empty,
.config-empty-text {
  color: var(--theme-text-secondary);
}

.config-summary,
.config-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.config-keys {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.custom-dialog-alert {
  margin-bottom: 14px;
}

@media (max-width: 1480px) {
  .builder-grid {
    grid-template-columns: 1fr;
  }

  .variable-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .variable-row {
    grid-template-columns: 1fr;
  }

  .sub-step-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
